"""Adapta el contrato completo aprobado a las señales de la plataforma."""

from dominio.contrato_extraccion import Respuesta, crear_normalizador


def normalizar_individual(respuesta, conversacion, catalogo, modelo) -> dict:
    """Valida una única conversación sin cambiar las reglas del pipeline."""
    parsed = Respuesta.model_validate(respuesta)
    if len(parsed.conversaciones) != 1:
        raise ValueError("Se esperaba una sola conversación.")
    extraida = parsed.conversaciones[0]
    if extraida.conversacion_id != conversacion["conversacion_id"]:
        raise ValueError("La respuesta contiene otra conversación.")
    normalizar, _, _ = crear_normalizador(catalogo, modelo=modelo)
    normalizada = normalizar(extraida.model_dump(), conversacion)
    e = normalizada["extraccion"]
    if (
        normalizada["estado_extraccion"] == "requiere_revision"
        or e["inconsistencias"]
    ):
        raise ValueError("La extracción tiene inconsistencias verificables.")
    referencias = {
        "presupuesto": e["dinero"]["presupuesto_total"],
        "cuota_inicial": e["dinero"]["cuota_inicial"],
        "forma_pago": e["forma_pago"],
        "intencion_declarada": e["intencion_declarada"],
        "objecion_principal": e["objecion_principal"],
        "cliente_pidio_cita": e["cita"]["cliente_solicito"],
        "cliente_pidio_cotizacion": e["cotizacion"]["cliente_solicito"],
        "cliente_pidio_credito": e["credito"]["cliente_solicito"],
        "asesor_ofrecio_credito": e["credito"]["asesor_ofrecio"],
    }
    salida = {
        "modelos_interes": [
            m["valor"] for m in e["modelos_interes"] if m["valor"] is not None
        ]
    }
    evidencias = []
    for campo, objeto in referencias.items():
        if "estado" in objeto:
            valor = {"si": True, "no_explicito": False, "no_mencionado": None}[
                objeto["estado"]
            ]
        else:
            valor = objeto.get("valor")
        salida[campo] = None if valor == "desconocida" else valor
        for ev in objeto["evidencias"]:
            evidencias.append(
                {
                    "campo": campo,
                    "posicion": ev["mensaje"],
                    "cita": ev["texto"],
                }
            )
    for mencion in e["modelos_interes"]:
        for ev in mencion["evidencias"]:
            evidencias.append(
                {
                    "campo": "modelos_interes",
                    "posicion": ev["mensaje"],
                    "cita": ev["texto"],
                }
            )
    return {**salida, "evidencias": evidencias, "_normalizado": normalizada}
