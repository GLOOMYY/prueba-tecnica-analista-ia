"""Límites transaccionales para aplicar el ámbito de empresa en PostgreSQL."""

from collections.abc import Iterator
from contextlib import contextmanager

from django.db import connection, transaction


@contextmanager
def transaccion_empresa(empresa_id: str) -> Iterator[None]:
    """Abre una transacción con contexto local de empresa para RLS.

    La ruta que invoca este contexto debe haber obtenido ``empresa_id`` de una
    membresía autorizada, nunca de un campo enviado por navegador o API. El uso
    de ``set_config(..., true)`` limita el valor a esta transacción y evita que
    un pool reutilice el ámbito de una solicitud anterior.

    Args:
        empresa_id: Identificador autorizado y no vacío de una empresa.

    Yields:
        Control mientras el contexto SQL de la empresa está activo.

    Raises:
        ValueError: Si falta el ámbito de empresa.
    """
    if not empresa_id or not empresa_id.strip():
        raise ValueError("Se requiere una empresa autorizada.")
    with transaction.atomic():
        anterior = None
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_setting('app.empresa_id', true)"
                )
                anterior = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT set_config('app.empresa_id', %s, true)",
                    [empresa_id],
                )
        completado = False
        try:
            yield
            completado = True
        finally:
            if (
                connection.vendor == "postgresql"
                and completado
                and not connection.needs_rollback
            ):
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.empresa_id', %s, true)",
                        [anterior or ""],
                    )
