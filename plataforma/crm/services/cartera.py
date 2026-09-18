"""Operaciones de cartera que preservan asignaciones y su auditoría."""

from cuentas.models import MembresiaEmpresa, RolMembresia
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.models import Max
from django.utils import timezone

from crm.contexto_empresa import transaccion_empresa
from crm.historico import _consultar
from crm.models import AsignacionDiaria, EstadoOperativoLead, EventoAuditoria


def transferir_responsable(
    *,
    empresa_id: str,
    lead_consolidado_id: str,
    supervisor: MembresiaEmpresa,
    nuevo_responsable: MembresiaEmpresa,
) -> EstadoOperativoLead:
    """Transfiere cartera y asignación diaria respetando sede y capacidad.

    Una asignación completada también consume el cupo del día: representa un
    lead que ya recibió atención y no debe desaparecer al mover su responsable.
    Si el lead no tiene asignación hoy, el cambio afecta solo a la cartera.
    """
    if (
        supervisor.empresa_id != empresa_id
        or not supervisor.activa
        or not supervisor.usuario.is_active
        or supervisor.rol != RolMembresia.SUPERVISOR
    ):
        raise PermissionDenied(
            "Solo un supervisor de la empresa puede transferir."
        )
    if (
        nuevo_responsable.empresa_id != empresa_id
        or nuevo_responsable.rol != RolMembresia.ASESOR
        or not nuevo_responsable.activa
        or not nuevo_responsable.usuario.is_active
    ):
        raise PermissionDenied("El responsable no es un asesor activo válido.")
    with transaccion_empresa(empresa_id):
        if connection.vendor == "postgresql":
            _consultar(
                "SELECT pg_advisory_xact_lock(hashtext("
                "'prueba_ia_05_' || current_schema())) AS bloqueo",
                [],
            )
        miembros = {
            m.pk: m
            for m in MembresiaEmpresa.objects.filter(
                pk__in=[supervisor.pk, nuevo_responsable.pk]
            ).order_by("pk")
        }
        supervisor = miembros.get(supervisor.pk)
        nuevo_responsable = miembros.get(nuevo_responsable.pk)
        if (
            supervisor is None
            or nuevo_responsable is None
            or not supervisor.activa
            or not nuevo_responsable.activa
            or not supervisor.usuario.is_active
            or not nuevo_responsable.usuario.is_active
            or supervisor.rol != RolMembresia.SUPERVISOR
            or nuevo_responsable.rol != RolMembresia.ASESOR
            or supervisor.empresa_id != empresa_id
            or nuevo_responsable.empresa_id != empresa_id
        ):
            raise PermissionDenied("Las membresías dejaron de ser válidas.")
        estado = EstadoOperativoLead.objects.select_for_update().get(
            empresa_id=empresa_id,
            lead_consolidado_id=lead_consolidado_id,
        )
        if estado.asesor_responsable_id == nuevo_responsable.pk:
            return estado
        capacidad = _validar_sede(
            empresa_id, estado.priorizacion_vigente_id, nuevo_responsable
        )
        asignacion = (
            AsignacionDiaria.objects.select_for_update()
            .filter(
                empresa_id=empresa_id,
                lead_consolidado_id=lead_consolidado_id,
                fecha_operativa=timezone.localdate(),
            )
            .first()
        )
        if asignacion is not None and asignacion.estado != "completada":
            _transferir_asignacion(
                asignacion=asignacion,
                empresa_id=empresa_id,
                lead_id=lead_consolidado_id,
                nuevo_responsable=nuevo_responsable,
                capacidad=capacidad,
            )
        anterior = estado.asesor_responsable_id
        estado.asesor_responsable = nuevo_responsable
        estado.save(update_fields=["asesor_responsable", "actualizado_en"])
        EventoAuditoria.objects.create(
            empresa_id=empresa_id,
            actor=supervisor.usuario,
            accion="transferir_responsable",
            tipo_entidad="lead",
            entidad_id=lead_consolidado_id,
            detalle={
                "responsable_anterior_id": anterior,
                "responsable_nuevo_id": nuevo_responsable.id,
            },
        )
    return estado


def _transferir_asignacion(
    *,
    asignacion: AsignacionDiaria,
    empresa_id: str,
    lead_id: str,
    nuevo_responsable: MembresiaEmpresa,
    capacidad: int,
) -> None:
    """Mueve una asignación diaria solo hacia un asesor elegible con cupo."""
    if asignacion.asesor_id == nuevo_responsable.pk:
        return
    carga = AsignacionDiaria.objects.filter(
        empresa_id=empresa_id,
        asesor__asesor_id=nuevo_responsable.asesor_id,
        fecha_operativa=asignacion.fecha_operativa,
    ).count()
    if carga >= capacidad:
        raise ValueError("El asesor destino no tiene cupo disponible hoy.")
    posicion = (
        AsignacionDiaria.objects.filter(
            empresa_id=empresa_id,
            asesor=nuevo_responsable,
            fecha_operativa=asignacion.fecha_operativa,
        ).aggregate(maxima=Max("posicion_inicial"))["maxima"]
        or 0
    )
    asignacion.asesor = nuevo_responsable
    asignacion.posicion_inicial = posicion + 1
    asignacion.save(
        update_fields=["asesor", "posicion_inicial", "actualizado_en"]
    )


def _validar_sede(empresa_id, prioridad_id, nuevo_responsable) -> int:
    """Usa la consulta de la prioridad publicada para comprobar la sede."""
    if not nuevo_responsable.asesor_id:
        raise ValueError("El destino no tiene un asesor operativo asociado.")
    consultas = _consultar(
        "SELECT c.punto_venta_id FROM consultas c JOIN priorizaciones p "
        "ON p.lead_id_contexto = c.lead_id_origen "
        "AND p.empresa_id = c.empresa_id "
        "WHERE p.empresa_id = %s AND p.priorizacion_id = %s",
        [empresa_id, prioridad_id],
    )
    if len(consultas) != 1 or not consultas[0]["punto_venta_id"]:
        raise ValueError(
            "El lead no tiene una sede verificable para transferir."
        )
    asesores = _consultar(
        "SELECT punto_venta_id, capacidad_diaria_leads FROM asesores "
        "WHERE empresa_id = %s AND asesor_id = %s AND activo = true",
        [empresa_id, nuevo_responsable.asesor_id],
    )
    if len(asesores) != 1 or (
        asesores[0]["punto_venta_id"] != consultas[0]["punto_venta_id"]
    ):
        raise ValueError(
            "El asesor destino no corresponde a la sede del lead."
        )
    return asesores[0]["capacidad_diaria_leads"] or 0
