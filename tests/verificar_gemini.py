"""Prueba optativa de una petición real con contenido exclusivamente sintético.

Ejecutar con --consumir-cuota. No participa en unittest ni en CI.
"""

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> None:
    """Verifica contrato y evidencia con una petición al modelo configurado."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consumir-cuota", action="store_true", required=True)
    parser.parse_args()
    raiz = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(raiz / "plataforma"), str(raiz)]
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plataforma.settings")
    import django

    django.setup()
    from crm.services.extraccion_ia import (
        MODELO_PREDETERMINADO,
        VERSION_PROMPT,
        ErrorProveedor,
        generar_con_gemini,
    )

    conversacion = {
        "conversacion_id": "SINTETICA",
        "mensajes": [
            {
                "posicion": 1,
                "emisor": "cliente",
                "texto": "Quiero cotizar una moto. Mi presupuesto es de "
                "10000000 "
                "COP. Tengo 2000000 COP para la cuota inicial. Quiero pagar "
                "a crédito.",
            },
            {
                "posicion": 2,
                "emisor": "asesor",
                "texto": "Podemos ofrecer crédito.",
            },
        ],
    }
    try:
        respuesta = generar_con_gemini(
            conversacion,
            {
                "modelo": MODELO_PREDETERMINADO,
                "version_prompt": VERSION_PROMPT,
            },
        )
    except ErrorProveedor as error:
        raise SystemExit(f"Proveedor: {error.categoria}") from None
    evidencia = raiz / "local-private" / "gemini_sintetico.json"
    evidencia.parent.mkdir(exist_ok=True)
    evidencia.write_text(
        json.dumps(respuesta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    from dominio.extraccion_individual import normalizar_individual

    resultado = normalizar_individual(
        respuesta, conversacion, [], MODELO_PREDETERMINADO
    )
    assert resultado["presupuesto"] == 10000000
    assert resultado["cuota_inicial"] == 2000000
    assert resultado["forma_pago"] == "credito"
    assert resultado["asesor_ofrecio_credito"] is True
    print(
        f"OK: una extracción sintética validada con {MODELO_PREDETERMINADO}."
    )


if __name__ == "__main__":
    main()
