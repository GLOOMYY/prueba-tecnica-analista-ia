"""Reserva presupuesto de Gemini en PostgreSQL antes de enviar una petición."""

import os
import re
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict


def reservar_cuota(modelo: str) -> bool:
    """Aplica a lote y worker un tope común de 8/minuto y 240/24 horas.

    No hay respaldo local: sin PostgreSQL se detiene el consumo, conservando
    la caché. La reserva cuenta intentos, incluidos los fallidos.
    """
    valores = {
        **dotenv_values(Path(__file__).resolve().parents[1] / ".env"),
        **os.environ,
    }
    url = valores.get("DJANGO_DATABASE_URL") or valores.get("SUPABASE_DB_URL")
    esquema = valores.get("DJANGO_DB_SCHEMA") or valores.get(
        "SUPABASE_DB_SCHEMA", "crm"
    )
    if not url or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", esquema):
        raise RuntimeError("Configure PostgreSQL para reservar cuota Gemini.")
    sslmode = conninfo_to_dict(url).get("sslmode", "require")
    if sslmode not in {"require", "verify-ca", "verify-full"}:
        raise RuntimeError("La reserva de cuota requiere SSL.")
    with psycopg.connect(url, sslmode=sslmode, connect_timeout=15) as conn:
        return conn.execute(
            sql.SQL("SELECT {}.reservar_cuota_ia(%s)").format(
                sql.Identifier(esquema)
            ),
            [modelo],
        ).fetchone()[0]
