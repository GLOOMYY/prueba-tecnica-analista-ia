"""Lee todas las fuentes sin modificar los originales."""

from pathlib import Path


def ejecutar(root: Path) -> dict:
    """Lee todas las fuentes sin modificar los originales.

    Args:
        root: Directorio de trabajo con data y outputs.

    Returns:
        Resumen verificable de la etapa.
    """
    import json

    import pandas as pd

    ruta_datos = root / "data/raw"
    leads = pd.read_csv(
        ruta_datos / "leads.csv",
        encoding="utf-8",
        dtype={"telefono": "string"},
    )
    catalogo_motos = pd.read_csv(
        ruta_datos / "catalogo_motos.csv", encoding="utf-8"
    )
    asesores = pd.read_csv(ruta_datos / "asesores.csv", encoding="utf-8")
    historico_cierres = pd.read_csv(
        ruta_datos / "historico_cierres.csv", encoding="utf-8"
    )
    with (ruta_datos / "conversaciones.json").open(
        encoding="utf-8"
    ) as archivo:
        conversaciones = json.load(archivo)
    return {
        "leads": leads,
        "catalogo_motos": catalogo_motos,
        "asesores": asesores,
        "historico_cierres": historico_cierres,
        "conversaciones": conversaciones,
    }
