"""Alta manual atómica sobre el esquema histórico y tablas operativas."""

import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime, time
from decimal import Decimal
from uuid import uuid4

from cuentas.acceso import alcance_empresa
from django.db import connection
from django.utils import timezone

from crm.historico import _consultar
from crm.models import (
    CapturaEstructurada,
    CapturaRevision,
    EstadoOperativoLead,
    EventoAuditoria,
    SolicitudIdempotente,
)
from crm.selectores import estados_visibles
from crm.services.gestion import ConflictoIdempotencia
from dominio.alta import EntradaAlta, preparar_alta
from dominio.identidad import nombres_compatibles
from dominio.prioridad import clasificar_cola


def crear_lead(*, usuario, empresa_id: str, clave: str, datos: dict) -> tuple:
    """Guarda una captura atribuida, con score e identidad conservadora.

    El llamador valida tipos con AltaForm. Se serializa el mismo bloqueo de
    carga del lote para impedir escrituras simultáneas sobre sus identidades.
    """
    if not clave or len(clave) > 255:
        raise ValueError("Se requiere una clave de envío válida.")
    originales = json.loads(json.dumps(datos, default=str))
    huella = hashlib.sha256(
        json.dumps(originales, sort_keys=True).encode()
    ).hexdigest()
    with alcance_empresa(usuario, empresa_id) as miembro:
        visibles = estados_visibles(miembro)
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    [
                        "prueba_ia_05_"
                        + _consultar("SELECT current_schema() AS esquema", [])[
                            0
                        ]["esquema"]
                    ],
                )
        solicitud, nueva = SolicitudIdempotente.objects.get_or_create(
            empresa_id=miembro.empresa_id,
            actor=usuario,
            operacion="crear_lead",
            clave=clave,
            defaults={"huella_cuerpo": huella},
        )
        if not nueva:
            if solicitud.estado != "completada":
                raise ConflictoIdempotencia("El envío sigue en proceso.")
            if solicitud.huella_cuerpo != huella:
                raise ConflictoIdempotencia("Clave usada con otros datos.")
            respuesta = solicitud.respuesta
            if (
                respuesta.get("lead_consolidado_id")
                and not visibles.filter(
                    lead_consolidado_id=respuesta["lead_consolidado_id"]
                ).exists()
            ):
                raise ValueError("El resultado ya no está en su cartera.")
            codigo = {"identidad_ambigua": 409, "revision_requerida": 202}.get(
                respuesta.get("estado"), 200
            )
            return respuesta, codigo
        sede = _consultar(
            "SELECT punto_venta_id FROM puntos_venta "
            "WHERE empresa_id = %s AND punto_venta_id = %s",
            [miembro.empresa_id, datos["sede_id"]],
        )
        if not sede:
            raise ValueError("Sede no autorizada.")
        sku = datos.get("modelo_sku") or None
        if sku and not _consultar(
            "SELECT sku FROM modelos_moto WHERE sku = %s", [sku]
        ):
            raise ValueError("SKU no reconocido; conserve la mención textual.")
        preparada = preparar_alta(
            EntradaAlta(
                empresa_id=miembro.empresa_id,
                nombre_cliente=datos["nombre_cliente"],
                telefono=datos.get("telefono"),
                correo=datos.get("correo"),
                modelo_sku=sku,
                cuota_inicial=datos.get("cuota_inicial"),
                forma_pago=datos.get("forma_pago"),
                cliente_pidio_cita=datos.get("cliente_pidio_cita") is True,
            )
        )
        candidatos = []
        if preparada.telefono.valor:
            candidatos = _consultar(
                "SELECT DISTINCT l.lead_consolidado_id, "
                "l.nombre_presentacion FROM leads l JOIN consultas c "
                "ON c.lead_consolidado_id = l.lead_consolidado_id "
                "AND c.empresa_id = l.empresa_id "
                "WHERE l.empresa_id = %s AND c.telefono = %s",
                [miembro.empresa_id, preparada.telefono.valor],
            )
        motivo = None
        if candidatos:
            if len(candidatos) != 1 or not nombres_compatibles(
                preparada.nombre_cliente, candidatos[0]["nombre_presentacion"]
            ):
                motivo = "identidad_ambigua"
            elif (
                miembro.rol != "supervisor"
                and not visibles.filter(
                    lead_consolidado_id=candidatos[0]["lead_consolidado_id"]
                ).exists()
            ):
                motivo = "revision_requerida"
        if motivo:
            revision = CapturaRevision.objects.create(
                empresa_id=miembro.empresa_id,
                solicitante=usuario,
                datos_propuestos=originales,
                motivo=motivo,
            )
            respuesta = {"revision_id": str(revision.pk), "estado": motivo}
            codigo = 409 if motivo == "identidad_ambigua" else 202
        else:
            respuesta = _persistir(
                miembro, preparada, datos, originales, candidatos
            )
            codigo = 201
        solicitud.estado = "completada"
        solicitud.respuesta = respuesta
        solicitud.finalizada_en = timezone.now()
        solicitud.save()
        return respuesta, codigo


def _insertar(tabla: str, fila: dict) -> None:
    """Inserta valores parametrizados con identificadores internos fijos."""
    quote = connection.ops.quote_name
    columnas = ", ".join(quote(campo) for campo in fila)
    marcas = ", ".join(["%s"] * len(fila))
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO {quote(tabla)} ({columnas}) VALUES ({marcas})",
            [
                valor.isoformat()
                if isinstance(valor, (date, datetime, time))
                else str(valor)
                if isinstance(valor, Decimal)
                else valor
                for valor in fila.values()
            ],
        )


def _persistir(miembro, preparada, datos, originales, candidatos) -> dict:
    """Persiste historia y estado operativo sin llamadas externas."""
    ahora = timezone.localtime()
    empresa = miembro.empresa_id
    lead = (
        candidatos[0]["lead_consolidado_id"]
        if candidatos
        else "WEB-" + uuid4().hex
    )
    consulta, ejecucion, prioridad = ["WEB-" + uuid4().hex for _ in range(3)]
    origen = json.dumps(originales, ensure_ascii=False)
    if not candidatos:
        _insertar(
            "leads",
            {
                "lead_consolidado_id": lead,
                "empresa_id": empresa,
                "nombre_presentacion": preparada.nombre_cliente,
                "primera_fecha_registro": ahora.date(),
                "primera_fecha_registro_hora": ahora.time().replace(
                    tzinfo=None
                ),
                "primera_fecha_registro_precision": "fecha_hora",
                "ultima_fecha_registro": ahora.date(),
                "ultima_fecha_registro_hora": ahora.time().replace(
                    tzinfo=None
                ),
                "ultima_fecha_registro_precision": "fecha_hora",
                "reglas_identidad": "[]",
                "datos_originales": origen,
                "origen_registro": "web",
            },
        )
    _insertar(
        "consultas",
        {
            "lead_id_origen": consulta,
            "lead_consolidado_id": lead,
            "empresa_id": empresa,
            "punto_venta_id": datos["sede_id"],
            "nombre_declarado": preparada.nombre_cliente,
            "telefono": preparada.telefono.valor,
            "email": preparada.correo,
            "ciudad": datos.get("ciudad") or None,
            "modelo_declarado": datos.get("modelos_interes") or None,
            "modelo_sku": datos.get("modelo_sku") or None,
            "fecha_registro": ahora.date(),
            "fecha_registro_hora": ahora.time().replace(tzinfo=None),
            "fecha_registro_precision": "fecha_hora",
            "calidad": json.dumps(preparada.incidencias),
            "datos_originales": origen,
            "origen_registro": "web",
        },
    )
    estado, nuevo = EstadoOperativoLead.objects.get_or_create(
        empresa_id=empresa, lead_consolidado_id=lead
    )
    if not nuevo:
        estado.revision_entrada += 1
    captura = CapturaEstructurada.objects.create(
        empresa_id=empresa,
        lead_consolidado_id=lead,
        lead_id_origen=consulta,
        autor=miembro.usuario,
        declaracion=originales,
        incidencias=list(preparada.incidencias),
        revision_entrada=estado.revision_entrada,
    )
    _insertar(
        "ejecuciones",
        {
            "ejecucion_id": ejecucion,
            "etapa": "prioridad_manual",
            "version_codigo": "captura_manual_v1",
            "huella_entrada": str(captura.pk),
            "importada": False,
            "inicio": ahora,
            "fin": ahora,
            "estado": "completada",
            "configuracion": "{}",
            "conteos": "{}",
            "errores": "[]",
        },
    )
    resultado = preparada.prioridad
    cola, accion = clasificar_cola(resultado.temperatura, False, "valido")
    _insertar(
        "priorizaciones",
        {
            "priorizacion_id": prioridad,
            "lead_consolidado_id": lead,
            "empresa_id": empresa,
            "ejecucion_id": ejecucion,
            "lead_id_contexto": consulta,
            "score_prioridad": resultado.score,
            "temperatura": resultado.temperatura,
            "cola": cola,
            "explicacion": "; ".join(
                item.explicacion for item in resultado.contribuciones
            )
            or "Sin señales declaradas suficientes.",
            "accion_sugerida": accion,
            "version_reglas": "reglas_evidencia_v1",
            "contexto": json.dumps({"captura_id": str(captura.pk)}),
            "datos_originales": origen,
        },
    )
    estado.priorizacion_vigente_id = prioridad
    estado.save()
    EventoAuditoria.objects.create(
        empresa_id=empresa,
        actor=miembro.usuario,
        accion="capturar_lead",
        tipo_entidad="lead",
        entidad_id=lead,
        detalle={"consulta_id": consulta},
    )
    return {
        "lead_consolidado_id": lead,
        "consulta_id": consulta,
        "lead_creado": not candidatos,
        "revision_entrada": estado.revision_entrada,
        "prioridad": json.loads(json.dumps(asdict(resultado), default=str)),
        "incidencias": list(preparada.incidencias),
        "asignacion": {"estado": "pendiente"},
    }
