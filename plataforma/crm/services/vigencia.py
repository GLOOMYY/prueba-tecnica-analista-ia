"""Reglas de vigencia compartidas entre captura, lote y trabajos diferidos."""

from django.db import connection, transaction

from crm.historico import _consultar
from crm.models import EstadoOperativoLead


def publicar_prioridad(
    *,
    empresa_id: str,
    lead_id: str,
    revision_entrada: int,
    priorizacion_id: str,
    origen: str,
) -> bool:
    """Publica una prioridad solo para la revisión vigente del lead.

    Args:
        empresa_id: Empresa propietaria del lead.
        lead_id: Identificador consolidado del lead.
        revision_entrada: Revisión exacta usada para calcular la prioridad.
        priorizacion_id: Identificador histórico de la prioridad calculada.
        origen: Procedencia trazable, como ``captura_manual`` o ``lote``.

    Returns:
        ``True`` si la prioridad se volvió vigente. ``False`` si la entrada ya
        cambió y el resultado queda únicamente en la historia.

    Raises:
        ValueError: Si falta un identificador o la revisión no es positiva.
    """
    identificadores = [
        empresa_id.strip(),
        lead_id.strip(),
        priorizacion_id.strip(),
        origen.strip(),
    ]
    if not all(identificadores):
        raise ValueError(
            "La prioridad requiere empresa, lead, origen e identificador."
        )
    if revision_entrada < 1:
        raise ValueError("La revisión de prioridad debe ser positiva.")
    with transaction.atomic():
        estado = EstadoOperativoLead.objects.select_for_update().get(
            empresa_id=empresa_id,
            lead_consolidado_id=lead_id,
        )
        if estado.revision_entrada != revision_entrada:
            return False
        prioridad = _consultar(
            "SELECT p.priorizacion_id FROM priorizaciones p "
            "JOIN ejecuciones e ON e.ejecucion_id = p.ejecucion_id "
            "WHERE p.empresa_id = %s AND p.lead_consolidado_id = %s "
            "AND p.priorizacion_id = %s AND e.estado = 'completada'",
            [empresa_id, lead_id, priorizacion_id],
        )
        if not prioridad:
            raise ValueError("Prioridad ajena al lead o incompleta.")
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO prioridades_publicadas "
                "(empresa_id,lead_consolidado_id,priorizacion_id,"
                "revision_entrada,origen,conflicto_lote) "
                "VALUES (%s,%s,%s,%s,%s,false) "
                "ON CONFLICT (empresa_id,lead_consolidado_id) DO UPDATE SET "
                "priorizacion_id = EXCLUDED.priorizacion_id, "
                "revision_entrada = EXCLUDED.revision_entrada, "
                "origen = EXCLUDED.origen, conflicto_lote = false",
                [
                    empresa_id,
                    lead_id,
                    priorizacion_id,
                    revision_entrada,
                    origen,
                ],
            )
        estado.priorizacion_vigente_id = priorizacion_id
        estado.priorizacion_revision_entrada = revision_entrada
        estado.priorizacion_origen = origen
        estado.save(
            update_fields=[
                "priorizacion_vigente_id",
                "priorizacion_revision_entrada",
                "priorizacion_origen",
                "actualizado_en",
            ]
        )
        return True
