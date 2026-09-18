"""Configuración segura de la conexión web a PostgreSQL."""

import re
from collections.abc import Mapping
from urllib.parse import parse_qs, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

_ESQUEMA_VALIDO = re.compile(r"[a-z][a-z0-9_]{0,62}\Z")
_SSL_PERMITIDO = frozenset({"require", "verify-ca", "verify-full"})


def configurar_base_datos(valores: Mapping[str, str | None]) -> dict:
    """Construye la configuración Django sin exponer secretos de la URL.

    Si no existe ``DJANGO_DATABASE_URL``, devuelve SQLite para desarrollo
    local.
    El backend web no toma ``SUPABASE_DB_URL`` como respaldo: debe usar una
    credencial distinta y de privilegio mínimo en producción.

    Args:
        valores: Entorno ya combinado con los valores de ``.env``.

    Returns:
        Configuración de la base por defecto para Django.

    Raises:
        ImproperlyConfigured: Si una URL configurada es insegura o inválida.
    """
    url = valores.get("DJANGO_DATABASE_URL")
    if not url:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": valores.get("DJANGO_SQLITE_PATH") or "db.sqlite3",
        }

    partes = urlsplit(url)
    if partes.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DJANGO_DATABASE_URL debe usar PostgreSQL.")
    if not partes.hostname or not partes.path or partes.path == "/":
        raise ImproperlyConfigured("DJANGO_DATABASE_URL no tiene host o base.")

    esquema = valores.get("DJANGO_DB_SCHEMA") or "crm"
    if not _ESQUEMA_VALIDO.fullmatch(esquema):
        raise ImproperlyConfigured("DJANGO_DB_SCHEMA no es válido.")
    if esquema in {"auth", "public", "storage", "information_schema"}:
        raise ImproperlyConfigured(
            "DJANGO_DB_SCHEMA debe ser un esquema privado."
        )

    consulta = parse_qs(partes.query)
    sslmode = (consulta.get("sslmode") or ["require"])[0]
    if sslmode not in _SSL_PERMITIDO:
        raise ImproperlyConfigured("La conexión web debe exigir SSL.")
    timeout = _entero_positivo(
        valores.get("DJANGO_DB_CONNECT_TIMEOUT"),
        nombre="DJANGO_DB_CONNECT_TIMEOUT",
        predeterminado=15,
        maximo=300,
    )
    statement_timeout = _entero_positivo(
        valores.get("DJANGO_DB_STATEMENT_TIMEOUT_MS"),
        nombre="DJANGO_DB_STATEMENT_TIMEOUT_MS",
        predeterminado=120000,
        maximo=3600000,
    )
    opciones = (
        f"-c search_path={esquema},public "
        f"-c statement_timeout={statement_timeout}"
    )
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(partes.path.lstrip("/")),
        "USER": unquote(partes.username or ""),
        "PASSWORD": unquote(partes.password or ""),
        "HOST": partes.hostname,
        "PORT": str(partes.port or 5432),
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "connect_timeout": timeout,
            "sslmode": sslmode,
            "options": opciones,
        },
    }


def _entero_positivo(
    valor: str | None,
    *,
    nombre: str,
    predeterminado: int,
    maximo: int,
) -> int:
    """Valida un límite de conexión sin incluir datos sensibles en errores."""
    try:
        resultado = int(valor) if valor is not None else predeterminado
    except ValueError as error:
        raise ImproperlyConfigured(f"{nombre} debe ser un entero.") from error
    if not 1 <= resultado <= maximo:
        raise ImproperlyConfigured(f"{nombre} está fuera del rango permitido.")
    return resultado
