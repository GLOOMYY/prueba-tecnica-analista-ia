"""Entrada de la etapa 03 del flujo automático."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.etapas import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main("03"))
