"""Busca secretos locales en archivos candidatos a Git sin imprimir valores."""

import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parents[1]


def verificar() -> None:
    """Comprueba exclusiones, secretos conocidos y salidas de notebooks.

    Es una defensa adicional: no sustituye revisar el diff ni detecta todas
    las credenciales posibles. Solo informa rutas y categorías de hallazgo.
    """
    git = ["git", "-c", f"safe.directory={RAIZ.as_posix()}"]
    rutas = (
        subprocess.check_output(
            [
                *git,
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            cwd=RAIZ,
        )
        .decode()
        .split("\0")
    )
    secretos = set()
    for nombre, valor in dotenv_values(RAIZ / ".env").items():
        if not valor:
            continue
        if any(p in nombre for p in ("SECRET", "PASSWORD", "TOKEN", "KEY")):
            if len(valor) >= 8:
                secretos.add(valor)
        if valor.startswith(("postgres://", "postgresql://")):
            password = unquote(urlsplit(valor).password or "")
            if password:
                secretos.add(password)
            secretos.add(valor)
    accesos = RAIZ / "local-private/usuarios.md"
    if accesos.exists():
        secretos.update(re.findall(r"`([^`]+)`", accesos.read_text("utf-8")))
    fallos = []
    for nombre in sorted(set(rutas) - {""}):
        path = RAIZ / nombre
        if not path.is_file():
            continue
        if path.name == ".env" or nombre.startswith("local-private/"):
            fallos.append((nombre, "archivo privado versionable"))
        texto = path.read_text(encoding="utf-8", errors="replace")
        if any(secreto in texto for secreto in secretos):
            fallos.append((nombre, "secreto configurado"))
        if path.suffix == ".ipynb":
            notebook = json.loads(texto)
            if any(
                c.get("outputs") or c.get("execution_count") is not None
                for c in notebook.get("cells", [])
                if c.get("cell_type") == "code"
            ):
                fallos.append((nombre, "salidas de notebook"))
    if fallos:
        for nombre, categoria in fallos:
            print(f"{nombre}: {categoria}")
        raise SystemExit(1)
    print(
        f"OK: {len(set(rutas) - {''})} archivos; "
        "sin secretos conocidos ni salidas."
    )


if __name__ == "__main__":
    verificar()
