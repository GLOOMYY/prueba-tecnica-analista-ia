"""Verifica pg_dump/pg_restore solo sobre fixtures de concurrencia aisladas."""

import os
import re
import subprocess
from pathlib import Path

from psycopg import sql
from psycopg.conninfo import conninfo_to_dict


def probar_respaldo(conn, esquema: str, url: str, binarios: Path) -> None:
    """Restaura una copia sin sobrescribir datos ni usar claves en argumentos.

    La fuente debe ser un esquema aleatorio del harness de pruebas. Después
    del dump se renombra a ``_original``; pg_restore recrea el nombre libre.
    El harness elimina ambos esquemas en su bloque finally. No se admite el
    esquema comercial ni un archivo suministrado por un tercero.
    """
    if not re.fullmatch(r"carrera_[0-9a-f]{32}", esquema):
        raise ValueError("El respaldo de prueba exige un esquema sintético.")
    sufijo_binario = ".exe" if os.name == "nt" else ""
    parametros = conninfo_to_dict(url)
    entorno = dict(os.environ)
    for origen, destino in {
        "host": "PGHOST",
        "port": "PGPORT",
        "dbname": "PGDATABASE",
        "user": "PGUSER",
        "password": "PGPASSWORD",
        "sslmode": "PGSSLMODE",
    }.items():
        if origen in parametros:
            entorno[destino] = parametros[origen]
    entorno.setdefault("PGSSLMODE", "require")
    entorno["PGCONNECT_TIMEOUT"] = "15"
    archivo = (
        Path(__file__).resolve().parents[1]
        / "local-private"
        / (esquema + ".dump")
    )
    archivo.parent.mkdir(exist_ok=True)
    with conn.cursor() as cursor:
        cursor.execute("RESET ROLE")
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname=%s "
            "ORDER BY tablename",
            [esquema],
        )
        tablas = [r[0] for r in cursor.fetchall()]
    firmas = {t: _firma(conn, esquema, t) for t in tablas}
    _ejecutar(
        [
            str(binarios / ("pg_dump" + sufijo_binario)),
            "--format=custom",
            "--no-owner",
            "--no-acl",
            "--schema=" + esquema,
            "--file=" + str(archivo),
        ],
        entorno,
    )
    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL("ALTER SCHEMA {} RENAME TO {}").format(
                sql.Identifier(esquema), sql.Identifier(esquema + "_original")
            )
        )
    _ejecutar(
        [
            str(binarios / ("pg_restore" + sufijo_binario)),
            "--exit-on-error",
            "--no-owner",
            "--no-acl",
            "--dbname=" + parametros.get("dbname", "postgres"),
            str(archivo),
        ],
        entorno,
    )
    for tabla in tablas:
        if _firma(conn, esquema, tabla) != firmas[tabla]:
            raise RuntimeError(
                "El respaldo restaurado no coincide con la fuente."
            )
    print(
        f"OK: backup/restauración; contenido idéntico en {len(tablas)} tablas."
    )


def _firma(conn, esquema, tabla):
    """Compara filas completas, incluidos JSON y nulos, sin imprimirlas."""
    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                "SELECT count(*),md5(string_agg(row_to_json(t)::text,'' "
                'ORDER BY row_to_json(t)::text COLLATE "C")) FROM {} t'
            ).format(sql.Identifier(esquema, tabla))
        )
        return cursor.fetchone()


def _ejecutar(comando, entorno):
    """Mantiene fuera del log tanto credenciales como errores con datos."""
    resultado = subprocess.run(
        comando, env=entorno, capture_output=True, timeout=120, check=False
    )
    if resultado.returncode:
        raise RuntimeError(
            f"Falló {Path(comando[0]).name}; código {resultado.returncode}."
        )
