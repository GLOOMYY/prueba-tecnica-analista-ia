"""Arbitraje de prioridades cuando las fuentes no tienen secuencia."""

from cuentas.acceso import alcance_empresa
from cuentas.models import RolMembresia
from django.core.exceptions import PermissionDenied
from django.db import connection

from crm.historico import _consultar
from crm.models import EventoAuditoria
from crm.services.extraccion_ia import _bloquear_ingestion


def listar_conflictos() -> list[dict]:
    """Lista propuestas únicamente dentro del contexto empresarial activo."""
    return _consultar(
        "SELECT v.lead_consolidado_id,v.priorizacion_id,v.propuesta_lote_id, "
        "p.score_prioridad AS score_actual,n.score_prioridad AS score_nuevo, "
        "p.explicacion AS motivo_actual,n.explicacion AS motivo_nuevo "
        "FROM prioridades_publicadas v "
        "JOIN priorizaciones p ON p.priorizacion_id=v.priorizacion_id "
        "JOIN priorizaciones n ON n.priorizacion_id=v.propuesta_lote_id "
        "WHERE v.conflicto_lote ORDER BY v.lead_consolidado_id",
        [],
    )


def resolver_conflicto(
    *,
    usuario,
    empresa_id: str,
    lead_id: str,
    propuesta_id: str,
    accion: str,
    nota: str,
) -> dict:
    """Adopta o conserva con comparación de propuesta, bloqueo y auditoría.

    La hora de procesamiento no determina qué declaración es más reciente.
    Solo un supervisor puede decidir después de comparar ambas prioridades.
    Una nueva captura invalida la propuesta anterior; nunca se acepta a ciegas.
    """
    if (
        accion not in {"adoptar", "conservar"}
        or not 1 <= len(nota.strip()) <= 500
    ):
        raise ValueError(
            "Indique una decisión y un motivo de hasta 500 letras."
        )
    with alcance_empresa(usuario, empresa_id) as miembro:
        if miembro.rol != RolMembresia.SUPERVISOR:
            raise PermissionDenied("Se requiere un supervisor de la empresa.")
        _bloquear_ingestion()
        decision = {
            "propuesta_id": propuesta_id,
            "accion": accion,
            "nota": nota,
        }
        anterior = EventoAuditoria.objects.filter(
            empresa_id=empresa_id,
            tipo_entidad="conflicto_lote",
            entidad_id=lead_id,
            detalle=decision,
        ).exists()
        if anterior:
            return {"resuelto": True, "repetido": True}
        filas = _consultar(
            "SELECT * FROM prioridades_publicadas WHERE empresa_id=%s "
            "AND lead_consolidado_id=%s FOR UPDATE",
            [empresa_id, lead_id],
        )
        if (
            not filas
            or not filas[0]["conflicto_lote"]
            or (filas[0]["propuesta_lote_id"] != propuesta_id)
        ):
            raise ValueError("La propuesta cambió o ya no está pendiente.")
        vigente = filas[0]
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE prioridades_publicadas SET priorizacion_id=%s, "
                "revision_entrada=revision_entrada+1,origen=%s, "
                "conflicto_lote=false,propuesta_lote_id=NULL "
                "WHERE empresa_id=%s AND lead_consolidado_id=%s",
                [
                    propuesta_id
                    if accion == "adoptar"
                    else vigente["priorizacion_id"],
                    "revision_supervisada",
                    empresa_id,
                    lead_id,
                ],
            )
        EventoAuditoria.objects.create(
            empresa_id=empresa_id,
            actor=usuario,
            accion="resolver_lote",
            tipo_entidad="conflicto_lote",
            entidad_id=lead_id,
            detalle=decision,
        )
        return {"resuelto": True, "repetido": False}
