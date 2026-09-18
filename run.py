"""Punto de entrada único del flujo, independiente del directorio actual."""

import sys
from pathlib import Path

AUTO = Path(__file__).resolve().parent / "auto-inicio-datos"
sys.path.insert(0, str(AUTO))

from utils.flujo import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
