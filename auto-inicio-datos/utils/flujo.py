"""Orquestación por instantáneas, checkpoints y eventos de archivos."""

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .archivos import guardar_json, huella

AUTO = Path(__file__).resolve().parents[1]
PROYECTO = AUTO.parent
ETAPAS = (
    "01_ingerir.py",
    "02_normalizar.py",
    "03_extraer_ia.py",
    "04_priorizar.py",
    "05_persistir.py",
)
FUENTES = (
    "leads.csv",
    "catalogo_motos.csv",
    "asesores.csv",
    "historico_cierres.csv",
    "conversaciones.json",
)
LOGGER = logging.getLogger(__name__)


def entradas(origen: Path) -> dict:
    """Identifica el conjunto completo, código y entorno de ejecución."""
    import importlib.metadata as metadata

    return {
        "fuentes": {n: huella(origen / n) for n in FUENTES},
        "codigo": {
            p.relative_to(PROYECTO).as_posix(): huella(p)
            for p in sorted(
                [
                    *AUTO.glob("*.py"),
                    *AUTO.joinpath("utils").rglob("*.py"),
                    *AUTO.joinpath("utils").rglob("*.sql"),
                    *PROYECTO.joinpath("dominio").rglob("*.py"),
                ]
            )
        },
        "paquetes": {
            p: metadata.version(p)
            for p in (
                "pandas",
                "numpy",
                "scikit-learn",
                "joblib",
                "pydantic",
                "google-genai",
                "psycopg",
            )
        },
        "python": sys.version.split()[0],
    }


@contextmanager
def bloqueo(path: Path):
    """Mantiene un bloqueo del sistema operativo, liberado incluso al morir.

    Args:
        path: Archivo local compartido por todas las ejecuciones.

    Yields:
        Control mientras el proceso posee el bloqueo exclusivo.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def productos(root: Path) -> dict:
    """Obtiene huellas de salidas para detectar checkpoints incompletos."""
    archivos = [root / "ingestion.json"]
    for directorio in ("data/processed", "outputs"):
        archivos.extend((root / directorio).rglob("*"))
    return {
        p.relative_to(root).as_posix(): huella(p)
        for p in archivos
        if p.is_file() and p.suffix != ".tmp"
    }


def checkpoint_valido(root: Path, registro: dict) -> bool:
    """Exige todas las salidas y huellas de una etapa completada."""
    archivos = registro.get("productos", {})
    return bool(archivos) and all(
        (root / n).is_file() and huella(root / n) == digest
        for n, digest in archivos.items()
    )


def ejecutar(origen: Path, sin_api: bool, sin_db: bool) -> dict:
    """Ejecuta 1–5 sobre fuentes inmóviles, reanudando etapas verificadas.

    Args:
        origen: Carpeta con el conjunto completo de archivos fuente.
        sin_api: Prohíbe nuevas peticiones a Gemini.
        sin_db: Solo prepara y valida el lote SQL.

    Returns:
        Manifiesto del intento, con estado y duración por etapa.
    """
    identidad = entradas(origen)
    digest = hashlib.sha256(
        json.dumps(identidad, sort_keys=True).encode()
    ).hexdigest()
    root = AUTO / "ejecuciones" / digest
    raw = root / "data/raw"
    raw.mkdir(parents=True, exist_ok=True)
    for nombre in FUENTES:
        destino = raw / nombre
        if (
            not destino.exists()
            or huella(destino) != identidad["fuentes"][nombre]
        ):
            shutil.copyfile(origen / nombre, destino)
        if huella(destino) != identidad["fuentes"][nombre]:
            raise ValueError("La fuente cambió durante la copia; reintentar.")
    if entradas(origen) != identidad:
        raise ValueError(
            "Las fuentes cambiaron; se requiere otra instantánea."
        )
    ruta = root / "ejecucion.json"
    intento = root / "intentos" / f"{uuid4().hex}.json"
    previo = (
        json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    )
    estado = {
        "id": digest,
        "inicio": datetime.now(UTC).isoformat(),
        "estado": "en_curso",
        "entradas": identidad,
        "sin_api": sin_api,
        "sin_db": sin_db,
        "etapas": {},
    }

    def guardar_estado() -> None:
        """Conserva cada intento y actualiza el índice para reanudar."""
        guardar_json(intento, estado)
        guardar_json(ruta, estado)

    guardar_estado()
    invalidado = False
    for script in ETAPAS:
        etapa = script[:2]
        anterior = previo.get("etapas", {}).get(etapa, {})
        if (
            etapa != "05"
            and not invalidado
            and checkpoint_valido(root, anterior)
        ):
            estado["etapas"][etapa] = {**anterior, "reutilizada": True}
            LOGGER.info("Etapa %s: checkpoint verificado.", etapa)
            continue
        invalidado = True
        LOGGER.info("Etapa %s: iniciando.", etapa)
        inicio = time.monotonic()
        cmd = [sys.executable, str(AUTO / script), "--trabajo", str(root)]
        if sin_api:
            cmd.append("--sin-api")
        if sin_db:
            cmd.append("--sin-db")
        # Salida de cada CLI sanitizada; no volcar DataFrames ni respuestas IA.
        proceso = subprocess.run(cmd, check=False)
        registro = {
            "segundos": round(time.monotonic() - inicio, 3),
            "codigo_salida": proceso.returncode,
            "reutilizada": False,
        }
        estado["etapas"][etapa] = registro
        if proceso.returncode:
            estado.update(estado="fallida", etapa_fallida=etapa)
            guardar_estado()
            return estado
        registro["productos"] = productos(root)
        guardar_estado()
    estado.update(
        estado="validada_sin_db" if sin_db else "completada",
        fin=datetime.now(UTC).isoformat(),
    )
    guardar_estado()
    if not sin_db:
        guardar_json(
            AUTO / "ultima_exitosa.json",
            {
                "id": digest,
                "ruta": root.relative_to(AUTO).as_posix(),
                "fin": estado["fin"],
                "intento": intento.relative_to(AUTO).as_posix(),
            },
        )
    return estado


def main() -> int:
    """Ejecuta una vez o vigila cambios en las fuentes con espera estable."""
    parser = argparse.ArgumentParser(description="Flujo automático 01–05")
    parser.add_argument("--fuentes", type=Path, default=AUTO / "data/raw")
    parser.add_argument("--sin-api", action="store_true")
    parser.add_argument("--sin-db", action="store_true")
    parser.add_argument(
        "--watch", action="store_true", help="Vigilar cambios."
    )
    parser.add_argument("--intervalo", type=int, default=60)
    args = parser.parse_args()
    if args.intervalo < 5:
        parser.error("--intervalo debe ser de al menos 5 segundos.")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    try:
        with bloqueo(AUTO / ".run.lock"):
            ultima = None
            pendiente = None
            while True:
                try:
                    actual = entradas(args.fuentes)
                    # Esperar dos observaciones iguales antes de copiar.
                    estable = not args.watch or actual == pendiente
                    pendiente = actual
                    if estable and actual != ultima:
                        resultado = ejecutar(
                            args.fuentes, args.sin_api, args.sin_db
                        )
                        LOGGER.info(
                            "Flujo: %s (%s).",
                            resultado["estado"],
                            resultado["id"][:12],
                        )
                        if resultado["estado"] != "fallida":
                            ultima = actual
                        if not args.watch:
                            return int(resultado["estado"] == "fallida")
                except Exception as error:
                    LOGGER.error(
                        "Flujo detenido: %s. Sin publicar éxito.",
                        type(error).__name__,
                    )
                    if not args.watch:
                        return 1
                if args.watch:
                    time.sleep(args.intervalo)
    except KeyboardInterrupt:
        LOGGER.info("Vigilancia detenida.")
        return 130
    except OSError:
        LOGGER.error("No se pudo adquirir el bloqueo; revisar otro proceso.")
        return 1
