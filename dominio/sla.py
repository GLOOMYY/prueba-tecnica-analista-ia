"""Mide atención documentada en 24 horas sin inventar precisión temporal."""

from datetime import timedelta


def resumir_sla(filas: list[dict], ahora) -> dict:
    """Clasifica leads visibles con registro y primer contacto verificables.

    Args:
        filas: Registros con inicio, contacto y contacto_impreciso.
        ahora: Instante de corte con zona horaria.

    Returns:
        Conteos de cumplimiento, vencimiento, plazo abierto y no medibles.
        El porcentaje excluye plazos abiertos y fechas imprecisas.
    """
    resumen = {"cumplen": 0, "vencidos": 0, "en_plazo": 0, "no_medibles": 0}
    for fila in filas:
        inicio, contacto = fila["inicio"], fila["contacto"]
        if (
            inicio is None
            or inicio > ahora
            or fila["contacto_impreciso"]
            or (
                contacto is not None
                and (contacto < inicio or contacto > ahora)
            )
        ):
            resumen["no_medibles"] += 1
            continue
        limite = inicio + timedelta(hours=24)
        if contacto is not None:
            categoria = "cumplen" if contacto <= limite else "vencidos"
        else:
            categoria = "en_plazo" if ahora < limite else "vencidos"
        resumen[categoria] += 1
    denominador = resumen["cumplen"] + resumen["vencidos"]
    return {
        **resumen,
        "disponible": True,
        "denominador": denominador,
        "porcentaje": round(100 * resumen["cumplen"] / denominador, 2)
        if denominador
        else None,
        "criterio": "Primer contacto registrado en 24 horas; toda la cartera "
        "visible. Excluye fechas imprecisas y plazos todavía abiertos.",
    }
