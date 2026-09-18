"""Persistencia histórica de una extracción y su prioridad explicable."""

import json

from django.utils import timezone

from crm.historico import _consultar
from crm.services.alta import _insertar
from crm.services.vigencia import publicar_prioridad
from dominio.prioridad import (
    PrioridadEntrada,
    calcular_prioridad,
    clasificar_cola,
)


def guardar_historia_ia(trabajo, conversacion, resultado, captura) -> None:
    """Guarda extracción, menciones y score dentro de la transacción llamadora.

    Solo una mención que coincide exactamente con un SKU se identifica como
    catálogo. Las demás se conservan sin inventar una correspondencia.
    """
    identificador = f"IA-{trabajo.pk.hex}"
    ahora = timezone.now()
    normalizado = resultado.get("_normalizado")
    serializado = json.dumps(normalizado or resultado, ensure_ascii=False)
    _insertar(
        "ejecuciones",
        {
            "ejecucion_id": identificador,
            "etapa": "extraccion_individual",
            "empresa_id": trabajo.empresa_id,
            "version_codigo": trabajo.configuracion["version_prompt"],
            "huella_entrada": trabajo.huella_entrada,
            "importada": False,
            "inicio": trabajo.creado_en,
            "fin": ahora,
            "estado": "completada",
            "configuracion": json.dumps(trabajo.configuracion),
            "conteos": json.dumps({"conversaciones": 1}),
            "errores": "[]",
        },
    )
    _insertar(
        "extracciones_ia",
        {
            "extraccion_id": identificador,
            "conversacion_id": conversacion["conversacion_id"],
            "ejecucion_id": identificador,
            "proveedor": "gemini",
            "modelo_ia": trabajo.configuracion["modelo"],
            "version_prompt": trabajo.configuracion["version_prompt"],
            "version_normalizador": "2.5",
            "estado_validacion": "valido",
            "revision_semantica": "evidencia_literal_y_emisor_verificados",
            "huella_conversacion": trabajo.huella_entrada,
            "resultado": serializado,
            "datos_originales": serializado,
        },
    )
    identificados = []
    for posicion, texto in enumerate(resultado["modelos_interes"]):
        filas = (
            [
                {"sku": r["sku"]}
                for r in normalizado["catalogo"]
                if r["mencion"] == texto and r["sku"]
            ]
            if normalizado
            else _consultar(
                "SELECT sku FROM modelos_moto WHERE sku = %s", [texto]
            )
        )
        sku = filas[0]["sku"] if len(filas) == 1 else None
        if sku:
            identificados.append(sku)
        _insertar(
            "intereses_modelo",
            {
                "interes_id": f"{identificador}-{posicion}",
                "extraccion_id": identificador,
                "texto_mencionado": texto,
                "modelo_sku": sku,
                "estado_identificacion": "exacto"
                if sku
                else "no_identificado",
                "evidencias": json.dumps(
                    [
                        e
                        for e in resultado["evidencias"]
                        if e["campo"] == "modelos_interes"
                    ],
                    ensure_ascii=False,
                ),
            },
        )
    modelo_unico = (
        identificados[0]
        if len(set(identificados)) == 1
        and len(identificados) == len(resultado["modelos_interes"])
        else None
    )
    inicial_positiva = (resultado["cuota_inicial"] or 0) > 0
    if normalizado:
        inicial = normalizado["extraccion"]["dinero"]["cuota_inicial"]
        inicial_positiva = bool(inicial["evidencias"]) and (
            (inicial["valor"] or 0) > 0
            or (inicial["valor"] is None and (inicial["minimo"] or 0) > 0)
        )
    prioridad = calcular_prioridad(
        PrioridadEntrada(
            modelo_sku=modelo_unico,
            cuota_inicial_positiva=inicial_positiva,
            forma_pago=resultado["forma_pago"],
            cliente_pidio_cita=resultado["cliente_pidio_cita"] is True,
        )
    )
    cola, accion = clasificar_cola(prioridad.temperatura, False, "valido")
    _insertar(
        "priorizaciones",
        {
            "priorizacion_id": identificador,
            "lead_consolidado_id": conversacion["lead_consolidado_id"],
            "empresa_id": trabajo.empresa_id,
            "ejecucion_id": identificador,
            "lead_id_contexto": conversacion.get("lead_id_origen"),
            "conversacion_id_contexto": conversacion["conversacion_id"],
            "score_prioridad": prioridad.score,
            "temperatura": prioridad.temperatura,
            "cola": cola,
            "explicacion": "; ".join(
                c.explicacion for c in prioridad.contribuciones
            )
            or "Sin señales explícitas suficientes.",
            "accion_sugerida": accion,
            "version_reglas": "reglas_evidencia_v1",
            "contexto": json.dumps(
                {
                    "captura_id": str(captura.pk),
                    "revision_entrada": trabajo.revision_entrada,
                }
            ),
            "datos_originales": serializado,
        },
    )
    if not publicar_prioridad(
        empresa_id=trabajo.empresa_id,
        lead_id=conversacion["lead_consolidado_id"],
        revision_entrada=trabajo.revision_entrada,
        priorizacion_id=identificador,
        origen="gemini",
    ):
        raise RuntimeError("La revisión cambió dentro de la publicación.")
