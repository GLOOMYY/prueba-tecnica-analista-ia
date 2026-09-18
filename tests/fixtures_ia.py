"""Respuestas sintéticas del contrato completo, sin conversaciones reales."""


def respuesta_cita(conversacion_id="C1") -> dict:
    """Declara una cita y mantiene desconocidas las demás señales."""

    def senal():
        return {"estado": "no_mencionado", "evidencias": []}

    def evento():
        return {
            nombre: senal()
            for nombre in (
                "asesor_ofrecio",
                "cliente_solicito",
                "cliente_acepto",
                "cliente_rechazo",
            )
        }

    cita = evento()
    cita["cliente_solicito"] = {
        "estado": "si",
        "evidencias": [
            {"mensaje": 1, "emisor": "cliente", "texto": "Quiero una cita"}
        ],
    }
    return {
        "conversaciones": [
            {
                "conversacion_id": conversacion_id,
                "modelos_interes": [],
                "dinero": {
                    nombre: {"expresion_original": None, "evidencias": []}
                    for nombre in (
                        "presupuesto_total",
                        "cuota_inicial",
                        "cuota_mensual_maxima",
                    )
                },
                "credito": {**evento(), "cliente_declaro_contado": senal()},
                "forma_pago": {"valor": "desconocida", "evidencias": []},
                "intencion_declarada": {"valor": None, "evidencias": []},
                "objecion_principal": {"valor": None, "evidencias": []},
                "cita": cita,
                "cotizacion": evento(),
                "cambios_de_declaracion": [],
                "inconsistencias": [],
                "limitaciones": [],
            }
        ]
    }
