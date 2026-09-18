"""Archivos de control atómicos y huellas reproducibles."""

import hashlib
import json
from pathlib import Path


def huella(path: Path) -> str:
    """Calcula SHA-256 del contenido de un archivo."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def guardar_json(path: Path, valor: object) -> None:
    """Publica un JSON completo mediante reemplazo atómico."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporal = path.with_suffix(path.suffix + ".tmp")
    temporal.write_text(
        json.dumps(valor, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    temporal.replace(path)
