"""Conciliación de atención histórica y gestiones de la plataforma."""

from django.db import connection
from django.utils import timezone

from crm.historico import _consultar
from dominio.sla import resumir_sla


def sla_cartera(empresa_id, ids) -> dict:
    """Calcula el SLA de la cartera autorizada sobre PostgreSQL histórico."""
    if connection.vendor != "postgresql":
        return {"disponible": False}
    consulta_ids, parametros = ids.order_by().query.sql_with_params()
    filas = _consultar(
        "SELECT CASE WHEN l.primera_fecha_registro_precision = 'fecha_hora' "
        "THEN (l.primera_fecha_registro + l.primera_fecha_registro_hora) "
        "AT TIME ZONE 'America/Bogota' END AS inicio, "
        "LEAST(h.contacto, g.contacto) AS contacto, "
        "COALESCE(h.impreciso, false) AS contacto_impreciso "
        "FROM leads l LEFT JOIN LATERAL ("
        "SELECT min((q.fecha_primer_contacto + q.fecha_primer_contacto_hora) "
        "AT TIME ZONE 'America/Bogota') FILTER "
        "(WHERE q.fecha_primer_contacto_precision = 'fecha_hora') "
        "AS contacto, "
        "bool_or(q.fecha_primer_contacto IS NOT NULL AND "
        "(q.fecha_primer_contacto_precision IS DISTINCT FROM 'fecha_hora' "
        "OR q.fecha_primer_contacto_hora IS NULL)) AS impreciso "
        "FROM consultas q WHERE q.empresa_id = l.empresa_id "
        "AND q.lead_consolidado_id = l.lead_consolidado_id) h ON true "
        "LEFT JOIN LATERAL (SELECT min(registrada_en) AS contacto "
        "FROM crm_gestioncomercial g WHERE g.empresa_id = l.empresa_id "
        "AND g.lead_consolidado_id = l.lead_consolidado_id "
        "AND g.resultado = 'contactado') g ON true "
        "WHERE l.empresa_id = %s "
        f"AND l.lead_consolidado_id IN ({consulta_ids})",
        [empresa_id, *parametros],
    )
    return resumir_sla(filas, timezone.now())
