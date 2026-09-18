"""Asignación diaria limitada por capacidad real y propiedad de cartera."""

from cuentas.acceso import alcance_empresa
from cuentas.models import MembresiaEmpresa
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.utils import timezone

from crm.historico import _consultar
from crm.models import AsignacionDiaria, EstadoOperativoLead, EventoAuditoria


def generar_asignaciones(*, usuario, empresa_id: str) -> dict:
    """Asigna una vez por día, respetando sede, estado y cupos consumidos.

    PostgreSQL serializa la empresa y el cargador con el mismo advisory lock.
    La prueba real de concurrencia requiere PostgreSQL; SQLite no la garantiza.
    """
    with alcance_empresa(usuario, empresa_id) as supervisor:
        if supervisor.rol != "supervisor":
            raise PermissionDenied("Se requiere un supervisor.")
        if connection.vendor == "postgresql":
            _consultar(
                "SELECT pg_advisory_xact_lock(hashtext("
                "'prueba_ia_05_' || current_schema())) AS bloqueo",
                [],
            )
        miembros = list(
            MembresiaEmpresa.objects.select_for_update()
            .filter(
                empresa_id=empresa_id,
                activa=True,
                usuario__is_active=True,
                rol="asesor",
            )
            .order_by("pk")
        )
        asesores = {
            fila["asesor_id"]: fila
            for fila in _consultar(
                "SELECT asesor_id, punto_venta_id, capacidad_diaria_leads "
                "FROM asesores WHERE empresa_id = %s AND activo = true",
                [empresa_id],
            )
        }
        hoy, ahora = timezone.localdate(), timezone.now()
        cargas = {
            m.pk: AsignacionDiaria.objects.filter(
                empresa_id=empresa_id, asesor=m, fecha_operativa=hoy
            ).count()
            for m in miembros
        }
        candidatos = _consultar(
            "SELECT p.lead_consolidado_id, p.score_prioridad, p.cola, "
            "q.punto_venta_id, l.primera_fecha_registro "
            "FROM v_prioridad_vigente p JOIN leads l "
            "ON l.lead_consolidado_id = p.lead_consolidado_id "
            "AND l.empresa_id = p.empresa_id "
            "LEFT JOIN consultas q ON q.lead_id_origen = p.lead_id_contexto "
            "AND q.empresa_id = p.empresa_id "
            "WHERE p.empresa_id = %s "
            "ORDER BY p.score_prioridad DESC, "
            "l.primera_fecha_registro ASC NULLS LAST, p.lead_consolidado_id",
            [empresa_id],
        )
        estados = {
            e.lead_consolidado_id: e
            for e in EstadoOperativoLead.objects.filter(empresa_id=empresa_id)
        }
        candidatos.sort(key=lambda fila: _orden(fila, estados, ahora))
        creadas, pendientes = 0, {}
        for fila in candidatos:
            lead = fila["lead_consolidado_id"]
            if AsignacionDiaria.objects.filter(
                empresa_id=empresa_id,
                fecha_operativa=hoy,
                lead_consolidado_id=lead,
            ).exists():
                continue
            estado = estados.get(lead)
            motivo = _motivo_exclusion(fila, estado, ahora)
            if motivo:
                pendientes[motivo] = pendientes.get(motivo, 0) + 1
                continue
            elegibles = []
            for miembro in miembros:
                asesor = asesores.get(miembro.asesor_id)
                if (
                    not asesor
                    or asesor["punto_venta_id"] != fila["punto_venta_id"]
                ):
                    continue
                capacidad = asesor["capacidad_diaria_leads"] or 0
                if cargas[miembro.pk] >= capacidad:
                    continue
                if estado and estado.asesor_responsable_id not in (
                    None,
                    miembro.pk,
                ):
                    continue
                elegibles.append((capacidad - cargas[miembro.pk], miembro))
            if not elegibles:
                pendientes["sin_cupo_o_asesor"] = (
                    pendientes.get("sin_cupo_o_asesor", 0) + 1
                )
                continue
            elegibles.sort(key=lambda item: (-item[0], item[1].pk))
            miembro = elegibles[0][1]
            if estado is None:
                estado = EstadoOperativoLead.objects.create(
                    empresa_id=empresa_id, lead_consolidado_id=lead
                )
            estado.asesor_responsable = miembro
            estado.save(update_fields=["asesor_responsable", "actualizado_en"])
            cargas[miembro.pk] += 1
            AsignacionDiaria.objects.create(
                empresa_id=empresa_id,
                lead_consolidado_id=lead,
                asesor=miembro,
                fecha_operativa=hoy,
                posicion_inicial=cargas[miembro.pk],
                motivo="Seguimiento o prioridad vigente, según capacidad.",
            )
            creadas += 1
        respuesta = {
            "fecha": hoy.isoformat(),
            "creadas": creadas,
            "pendientes_por_motivo": pendientes,
        }
        EventoAuditoria.objects.create(
            empresa_id=empresa_id,
            actor=usuario,
            accion="asignacion_diaria",
            tipo_entidad="empresa",
            entidad_id=empresa_id,
            detalle=respuesta,
        )
        return respuesta


def _orden(fila, estados, ahora):
    """Antecede seguimientos vencidos sin modificar el orden de score."""
    estado = estados.get(fila["lead_consolidado_id"])
    fecha = estado.proxima_accion_en if estado else None
    return (0, fecha) if fecha and fecha <= ahora else (1, ahora)


def _motivo_exclusion(fila, estado, ahora):
    """Explica por qué un lead no participa en la asignación automática."""
    if str(fila["cola"]).startswith("revision"):
        return "revision"
    if not fila["punto_venta_id"]:
        return "sin_sede_verificable"
    if estado:
        if estado.estado != "abierto" or estado.requiere_revision:
            return "estado_no_elegible"
        if estado.proxima_accion_en and estado.proxima_accion_en > ahora:
            return "seguimiento_futuro"
    return None
