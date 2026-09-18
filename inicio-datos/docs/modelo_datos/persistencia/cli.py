"""Entradas CLI del punto 05 con errores sanitizados y validación local."""

import argparse
import json
import logging
from collections.abc import Callable

import psycopg

from .config import ROOT, Configuracion, ErrorValidacion, guardar_json, huella
from .db import archivos_migracion, cargar_lote, crear_esquema
from .plan import preparar_lote

LOGGER = logging.getLogger(__name__)


def ejecutar(operacion: Callable[[], dict]) -> int:
    """Traduce fallos a códigos CLI sin filtrar parámetros o datos de filas."""
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s: %(message)s"
    )
    try:
        resultado = operacion()
    except ErrorValidacion as error:
        LOGGER.error("Validación: %s", error)
        return 2
    except psycopg.Error as error:
        # El driver puede incluir credenciales o valores privados de filas.
        estado = error.sqlstate or "sin_sqlstate"
        LOGGER.error(
            "Operación SQL fallida (%s, %s). No se confirmó la transacción. "
            "Revisar configuración, conexión y esquema; no se imprime el DSN.",
            type(error).__name__,
            estado,
        )
        guardar_json(
            ROOT / "outputs/persistencia_05/ultimo_error.json",
            {
                "estado": "fallo_sql",
                "clase": type(error).__name__,
                "sqlstate": estado,
                "mensaje_driver_omitido": True,
            },
        )
        return 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        LOGGER.error(
            "Contrato o archivo incompatible (%s). "
            "Revisar fuentes y permisos. "
            "No se muestran valores privados.",
            type(error).__name__,
        )
        return 2
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


def crear_main() -> int:
    """Procesa argumentos para crear el esquema o validar migraciones."""
    parser = argparse.ArgumentParser(description="05: esquema SQL de Supabase")
    parser.add_argument(
        "--validar",
        action="store_true",
        help="Inspecciona archivos/configuración sin conectar.",
    )
    args = parser.parse_args()

    def operacion() -> dict:
        config = Configuracion.leer()
        if args.validar:
            return {
                "estado": "archivos_revisados_sin_conexion",
                "schema": config.schema,
                "url_configurada": bool(config.url),
                "migraciones": {
                    p.name: huella(p) for p in archivos_migracion()
                },
                "nota": "No valida ejecución SQL; requiere PostgreSQL.",
            }
        resultado = crear_esquema(config)
        guardar_json(ROOT / "outputs/persistencia_05/esquema.json", resultado)
        return resultado

    return ejecutar(operacion)


def cargar_main() -> int:
    """Prepara fuentes y permite validar sin credenciales ni acceso remoto."""
    parser = argparse.ArgumentParser(description="05: carga SQL de procesados")
    parser.add_argument(
        "--validar",
        action="store_true",
        help="Valida el lote y exporta revisión; no escribe SQL.",
    )
    args = parser.parse_args()

    def operacion() -> dict:
        config = Configuracion.leer()
        lote = preparar_lote(ROOT)
        carpeta = ROOT / "outputs/persistencia_05" / lote.ejecucion_id
        guardar_json(
            carpeta / "revision_fuera_db.json",
            {
                "ejecucion_id": lote.ejecucion_id,
                "politica": "Sin vínculo: conservar fuera de la DB.",
                "registros": lote.revision,
            },
        )
        if args.validar:
            resultado = {
                **lote.resumen(),
                "estado": "validado_localmente_sin_conexion",
            }
        else:
            resultado = cargar_lote(config, lote)
        guardar_json(carpeta / "resumen.json", resultado)
        return resultado

    return ejecutar(operacion)
