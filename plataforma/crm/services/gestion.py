"""Registro transaccional de gestiones con reintentos idempotentes."""

import hashlib
import json
from datetime import datetime

from cuentas.acceso import alcance_empresa
from django.shortcuts import get_object_or_404
from django.utils import timezone

from crm.models import (
    AsignacionDiaria,
    EventoAuditoria,
    GestionComercial,
    SolicitudIdempotente,
)
from crm.selectores import estados_visibles

RESULTADOS = (
    "contactado",
    "sin_respuesta",
    "seguimiento_programado",
    "cerrado",
    "perdido",
    "descartado",
)


class ConflictoIdempotencia(ValueError):
    """La misma clave ya identifica otro contenido o una operación en curso."""


def registrar_gestion(
    *,
    usuario,
    empresa_id: str,
    lead_id: str,
    clave: str,
    resultado: str,
    nota: str = "",
    proxima_accion_en: datetime | None = None,
    confirmar_cierre: bool = False,
) -> tuple[dict, bool]:
    """Guarda evento, estado, asignación y auditoría en la misma transacción.

    Returns:
        Respuesta persistida y si corresponde a un reintento ya completado.

    Raises:
        ValueError: Si los datos comerciales son inválidos.
        ConflictoIdempotencia: Si se reutiliza una clave con otro cuerpo.
    """
    if not clave.strip() or len(clave) > 255:
        raise ValueError(
            "Se requiere una clave de envío de hasta 255 caracteres."
        )
    if resultado not in RESULTADOS or len(nota) > 2000:
        raise ValueError("Resultado inválido o nota mayor de 2000 caracteres.")
    if resultado in {"perdido", "descartado"} and not nota.strip():
        raise ValueError("Indique el motivo de pérdida o descarte.")
    if resultado == "cerrado" and not confirmar_cierre:
        raise ValueError("Confirme explícitamente el cierre.")
    if proxima_accion_en is not None and timezone.is_naive(proxima_accion_en):
        raise ValueError("La próxima acción requiere zona horaria.")
    if resultado == "seguimiento_programado" and proxima_accion_en is None:
        raise ValueError("El seguimiento requiere una fecha futura.")
    if resultado != "seguimiento_programado" and proxima_accion_en is not None:
        raise ValueError("La fecha corresponde a seguimiento programado.")
    cuerpo = {
        "lead": lead_id,
        "resultado": resultado,
        "nota": nota,
        "proxima_accion_en": (
            proxima_accion_en.isoformat() if proxima_accion_en else None
        ),
        "confirmar_cierre": confirmar_cierre,
    }
    huella = hashlib.sha256(
        json.dumps(cuerpo, sort_keys=True).encode()
    ).hexdigest()
    with alcance_empresa(usuario, empresa_id) as membresia:
        estado = get_object_or_404(
            estados_visibles(membresia).select_for_update(),
            lead_consolidado_id=lead_id,
        )
        solicitud, creada = SolicitudIdempotente.objects.get_or_create(
            empresa_id=membresia.empresa_id,
            actor=usuario,
            operacion="registrar_gestion",
            clave=clave,
            defaults={"huella_cuerpo": huella},
        )
        if not creada:
            if solicitud.huella_cuerpo != huella:
                raise ConflictoIdempotencia("Clave usada con otros datos.")
            if solicitud.estado != "completada":
                raise ConflictoIdempotencia("El envío sigue en proceso.")
            return solicitud.respuesta, True
        if proxima_accion_en and proxima_accion_en <= timezone.now():
            raise ValueError("La próxima acción debe ser futura.")
        gestion = GestionComercial.objects.create(
            empresa_id=membresia.empresa_id,
            lead_consolidado_id=lead_id,
            actor=usuario,
            resultado=resultado,
            nota=nota,
            proxima_accion_en=proxima_accion_en,
        )
        if resultado in {"cerrado", "perdido", "descartado"}:
            estado.estado = resultado
        estado.proxima_accion_en = proxima_accion_en
        estado.save(
            update_fields=["estado", "proxima_accion_en", "actualizado_en"]
        )
        AsignacionDiaria.objects.filter(
            empresa_id=membresia.empresa_id,
            lead_consolidado_id=lead_id,
            fecha_operativa=timezone.localdate(),
        ).update(estado="completada")
        EventoAuditoria.objects.create(
            empresa_id=membresia.empresa_id,
            actor=usuario,
            accion="registrar_gestion",
            tipo_entidad="gestion",
            entidad_id=str(gestion.pk),
            detalle={"resultado": resultado},
        )
        respuesta = {"gestion_id": str(gestion.pk), "estado": estado.estado}
        solicitud.estado = "completada"
        solicitud.respuesta = respuesta
        solicitud.finalizada_en = timezone.now()
        solicitud.save()
        return respuesta, False
