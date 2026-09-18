"""Lecturas acotadas de tablas históricas sin duplicar su almacenamiento."""

from django.db import connection


def sedes(empresa_id: str) -> list[dict]:
    """Lee exclusivamente las sedes de la empresa autorizada."""
    return _consultar(
        "SELECT punto_venta_id, nombre, ubicacion FROM puntos_venta "
        "WHERE empresa_id = %s ORDER BY punto_venta_id",
        [empresa_id],
    )


def catalogo(empresa_id: str) -> list[dict]:
    """Conserva stock global, sin atribuir unidades a una sede."""
    return _consultar(
        "SELECT DISTINCT m.sku, b.nombre AS marca, m.linea, "
        "m.cilindraje, m.precio_lista, m.unidades_disponibles "
        "FROM modelos_moto m JOIN marcas b ON b.marca_id = m.marca_id "
        "JOIN disponibilidad_modelo d ON d.sku = m.sku "
        "JOIN puntos_venta s ON s.punto_venta_id = d.punto_venta_id "
        "WHERE s.empresa_id = %s ORDER BY m.sku",
        [empresa_id],
    )


def prioridades(empresa_id: str, lead_id: str) -> list[dict]:
    """Obtiene historia de prioridades ya finalizadas del lead autorizado."""
    return _consultar(
        "SELECT p.priorizacion_id, p.score_prioridad, p.temperatura, "
        "p.cola, p.explicacion, p.accion_sugerida, p.version_reglas "
        "FROM priorizaciones p JOIN ejecuciones e "
        "ON e.ejecucion_id = p.ejecucion_id "
        "WHERE p.empresa_id = %s AND p.lead_consolidado_id = %s "
        "AND e.estado = 'completada' "
        "ORDER BY e.registrada_en DESC LIMIT 100",
        [empresa_id, lead_id],
    )


def conversaciones(
    empresa_id: str,
    lead_id: str,
    incluir_descartadas: bool = False,
) -> list[dict]:
    """Lee conversaciones vinculadas, con descarte visible por permiso."""
    return _consultar(
        "SELECT conversacion_id, canal, fecha_inicio, descartada, "
        "motivos_descarte FROM conversaciones "
        "WHERE empresa_id = %s AND lead_consolidado_id = %s "
        "AND (NOT descartada OR %s) "
        "ORDER BY fecha_inicio DESC, conversacion_id LIMIT 100",
        [empresa_id, lead_id, incluir_descartadas],
    )


def _consultar(sentencia: str, parametros: list) -> list[dict]:
    """Ejecuta SQL fijo y materializa filas dentro del contexto autorizado."""
    with connection.cursor() as cursor:
        cursor.execute(sentencia, parametros)
        columnas = [columna[0] for columna in cursor.description]
        return [dict(zip(columnas, fila, strict=True)) for fila in cursor]
