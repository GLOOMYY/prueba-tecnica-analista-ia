"""Entradas por etapa, sin efectos al importar los módulos."""

import argparse
import json
import logging
import time
import traceback
from pathlib import Path

import psycopg

from .archivos import guardar_json
from .persistencia.config import Configuracion
from .persistencia.db import cargar_lote, crear_esquema
from .persistencia.plan import preparar_lote


def persistir(root: Path, sin_db: bool) -> dict:
    """Valida el lote y confirma la carga solo tras conciliar SQL.

    Args:
        root: Instantánea de ejecución con fuentes y resultados.
        sin_db: Valida localmente sin abrir conexión.

    Returns:
        Resultado real de carga o validación local.
    """
    lote = preparar_lote(root)
    destino = root / "outputs/persistencia_05"
    guardar_json(destino / "revision_fuera_db.json", lote.revision)
    if sin_db:
        resultado = {**lote.resumen(), "estado": "validado_sin_db"}
    else:
        config = Configuracion.leer()
        for intento in range(3):
            try:
                esquema = crear_esquema(config)
                guardar_json(destino / "esquema.json", esquema)
                resultado = cargar_lote(config, lote)
                break
            except psycopg.OperationalError:
                if intento == 2:
                    raise
                time.sleep(2**intento)
    guardar_json(destino / "resumen.json", resultado)
    return resultado


def main(etapa: str) -> int:
    """Ejecuta una etapa y evita imprimir datos personales o secretos."""
    parser = argparse.ArgumentParser(description=f"Etapa {etapa}")
    parser.add_argument("--trabajo", type=Path, required=True)
    parser.add_argument("--sin-api", action="store_true")
    parser.add_argument("--sin-db", action="store_true")
    args = parser.parse_args()
    root = args.trabajo.resolve()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if etapa == "01":
            from .ingestion import ejecutar

            datos = ejecutar(root)
            resultado = {k: len(v) for k, v in datos.items()}
            guardar_json(root / "ingestion.json", resultado)
        elif etapa == "02":
            from .normalizacion import ejecutar

            resultado = ejecutar(root)
        elif etapa == "03":
            from .extraccion import ejecutar

            resultado = ejecutar(root, permitir_api=not args.sin_api)
        elif etapa == "04":
            from .priorizacion import ejecutar

            resultado = ejecutar(root)
        elif etapa == "05":
            resultado = persistir(root, args.sin_db)
        else:
            raise ValueError("Etapa desconocida.")
        guardar_json(root / f"resultado_{etapa}.json", resultado)
    except Exception as error:
        # El límite CLI no muestra mensajes de librerías con filas o secretos.
        diagnostico = {
            "etapa": etapa,
            "estado": "fallida",
            "tipo": type(error).__name__,
            "sqlstate": getattr(error, "sqlstate", None),
            "ubicacion": [
                {"archivo": Path(f.filename).name, "linea": f.lineno}
                for f in traceback.extract_tb(error.__traceback__)
            ],
            "nombre_faltante": error.name
            if isinstance(error, NameError)
            else None,
        }
        guardar_json(root / f"error_{etapa}.json", diagnostico)
        logging.error("%s", json.dumps(diagnostico))
        return 1
    logging.info("Etapa %s completada.", etapa)
    return 0
