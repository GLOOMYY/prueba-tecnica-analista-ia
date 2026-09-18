"""Ejecuta pruebas unitarias aisladas sin usar la conexión comercial."""

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Separa las pruebas locales de los harness explícitos de PostgreSQL."""
    raiz = Path(__file__).resolve().parents[1]
    entorno = {
        **os.environ,
        "DJANGO_DATABASE_URL": "",
        "DJANGO_ENV": "development",
        "DJANGO_DEBUG": "False",
        "DJANGO_SECRET_KEY": "solo-pruebas-locales-no-usar-en-servidores",
        "DJANGO_SECURE_SSL_REDIRECT": "False",
    }
    for argumentos in (
        ["-m", "unittest", "discover", "-s", "tests"],
        ["-m", "unittest", "discover", "-s", "auto-inicio-datos/tests"],
        ["plataforma/manage.py", "test", "cuentas", "crm", "--noinput"],
    ):
        resultado = subprocess.run(
            [sys.executable, *argumentos], cwd=raiz, env=entorno, check=False
        )
        if resultado.returncode:
            return resultado.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
