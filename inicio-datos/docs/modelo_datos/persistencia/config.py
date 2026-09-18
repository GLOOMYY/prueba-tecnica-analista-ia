"""Configuración y utilidades comunes sin revelar credenciales."""

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]
MIGRACIONES = Path(__file__).resolve().parents[1] / "migrations"
VERSION = "05-v1"


class ErrorValidacion(ValueError):
    """Indica una entrada incompatible con el contrato de carga."""


@dataclass(frozen=True)
class Configuracion:
    """Opciones SQL; la URI se excluye de su representación.

    Attributes:
        url: Cadena de conexión SQL privada.
        schema: Esquema exclusivo de esta aplicación.
        sslmode: Modo SSL permitido, sin degradación automática.
        connect_timeout: Límite de conexión en segundos.
        statement_timeout: Límite de consulta en milisegundos.
    """

    url: str = field(repr=False)
    schema: str = "crm"
    sslmode: str = "require"
    connect_timeout: int = 15
    statement_timeout: int = 120000

    @classmethod
    def leer(cls, root: Path = ROOT) -> "Configuracion":
        """Lee el entorno con prioridad sobre .env, sin imprimir valores."""
        valores = {**dotenv_values(root.parent / ".env"), **os.environ}
        schema = valores.get("SUPABASE_DB_SCHEMA", "crm")
        if not schema or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema):
            raise ErrorValidacion("SUPABASE_DB_SCHEMA no es válido.")
        if schema in {"public", "auth", "storage", "information_schema"}:
            raise ErrorValidacion("Usar un esquema propio, por ejemplo crm.")
        if schema.startswith("pg_"):
            raise ErrorValidacion("No usar esquemas reservados de PostgreSQL.")
        sslmode = valores.get("SUPABASE_DB_SSLMODE", "require")
        if sslmode not in {"require", "verify-ca", "verify-full"}:
            raise ErrorValidacion("SUPABASE_DB_SSLMODE debe exigir SSL.")
        try:
            timeout = int(valores.get("SUPABASE_DB_CONNECT_TIMEOUT", "15"))
            statement = int(
                valores.get("SUPABASE_DB_STATEMENT_TIMEOUT_MS", "120000")
            )
        except (ValueError, TypeError) as error:
            raise ErrorValidacion(
                "Los límites SQL deben ser enteros."
            ) from error
        if not 1 <= timeout <= 300 or not 1 <= statement <= 3600000:
            raise ErrorValidacion("Límites SQL fuera del rango permitido.")
        return cls(
            url=valores.get("SUPABASE_DB_URL") or "",
            schema=schema,
            sslmode=sslmode,
            connect_timeout=timeout,
            statement_timeout=statement,
        )

    def exigir_url(self) -> None:
        """Rechaza la conexión si falta una URI PostgreSQL."""
        if not self.url.startswith(("postgresql://", "postgres://")):
            raise ErrorValidacion(
                "Completar SUPABASE_DB_URL con la URI SQL de Supabase."
            )


def huella(path: Path) -> str:
    """Calcula SHA-256 sin modificar el archivo."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identidad(*partes: object) -> str:
    """Genera una clave estable a partir de contenido serializable."""
    texto = json.dumps(
        partes, ensure_ascii=False, sort_keys=True, allow_nan=False
    )
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def guardar_json(path: Path, valor: object) -> None:
    """Escribe un JSON completo mediante reemplazo atómico local."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporal = path.with_suffix(path.suffix + ".tmp")
    temporal.write_text(
        json.dumps(valor, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    temporal.replace(path)
