"""Lectura y comprobación de artefactos locales ya procesados."""

import csv
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .config import ErrorValidacion, huella, identidad

PROCESADOS = (
    "leads.csv",
    "consultas_leads.csv",
    "asesores.csv",
    "catalogo_motos.csv",
    "historico_cierres.csv",
    "trazabilidad_leads.csv",
    "conversaciones.json",
    "extracciones_conversaciones_ia.json",
    "extracciones_conversaciones_descartadas.json",
    "conversaciones_utilizables_ia.json",
    "priorizacion_leads.json",
    "priorizacion_leads.csv",
    "contexto_priorizacion.json",
    "incidencias_datos.json",
    "incidencias_extraccion_ia.json",
    "incidencias_modelado.json",
    "manifest.json",
    "manifest_extraccion_ia.json",
    "manifest_clasificacion.json",
)
ARTEFACTOS = (
    "ficha_modelo.json",
    "modelo_experimental.joblib",
    "desbalance_v2/manifest_desbalance.json",
    "desbalance_v2/revision_resultados.json",
    "desbalance_v2/modelo_sin_pesos.joblib",
    "desbalance_v2/modelo_balanced.joblib",
)


def leer_json(path: Path) -> object:
    """Lee JSON estricto y evita valores no finitos no portables."""

    def rechazar_constante(_: str) -> None:
        raise ErrorValidacion(f"JSON no finito en {path.name}.")

    return json.loads(
        path.read_text(encoding="utf-8-sig"),
        parse_constant=rechazar_constante,
    )


def objeto(valor: object) -> dict:
    """Exige un objeto JSON para no aceptar silenciosamente otro contrato."""
    if not isinstance(valor, dict):
        raise ErrorValidacion("Se esperaba un objeto JSON.")
    return valor


def registros(valor: object) -> list[dict]:
    """Exige una lista de objetos JSON."""
    if not isinstance(valor, list) or not all(
        isinstance(item, dict) for item in valor
    ):
        raise ErrorValidacion("Se esperaba una lista de objetos JSON.")
    return valor


def leer_csv(path: Path) -> list[dict]:
    """Conserva teléfonos e IDs como texto, sin inferir tipos con pandas."""
    with path.open(encoding="utf-8-sig", newline="") as entrada:
        return list(csv.DictReader(entrada))


def opcional(valor: object) -> object:
    """Convierte solo cadenas vacías a desconocido; cero se conserva."""
    return None if valor is None or valor == "" else valor


def numero(valor: object) -> Decimal | None:
    """Convierte importes de salida normalizada, sin cambiar separadores."""
    if opcional(valor) is None:
        return None
    try:
        resultado = Decimal(str(valor))
    except InvalidOperation as error:
        raise ErrorValidacion("Número procesado inválido.") from error
    if not resultado.is_finite():
        raise ErrorValidacion("Número procesado no finito.")
    return resultado


def entero(valor: object) -> int | None:
    """Convierte un entero sin truncar fracciones accidentalmente."""
    decimal = numero(valor)
    if decimal is None:
        return None
    if decimal != decimal.to_integral_value():
        raise ErrorValidacion("Se esperaba un entero sin fracciones.")
    return int(decimal)


def booleano(valor: object) -> bool | None:
    """Lee booleanos del CSV sin interpretar 'False' como verdadero."""
    if opcional(valor) is None:
        return None
    if valor is True or str(valor).lower() in {"true", "si"}:
        return True
    if valor is False or str(valor).lower() in {"false", "no"}:
        return False
    raise ErrorValidacion("Booleano procesado inválido.")


def temporal(nombre: str, valor: object, precision: str | None = None) -> dict:
    """Separa día y hora para no convertir una fecha en medianoche real.

    Args:
        nombre: Prefijo de las columnas destino.
        valor: Fecha ISO normalizada; nunca interpreta formato mes-día-año.
        precision: Precisión explícita de la fuente, si está disponible.

    Returns:
        Fecha, hora opcional y precisión. Un faltante no recibe hora.

    Raises:
        ErrorValidacion: Si un valor normalizado no es ISO o tiene zona.
    """
    if opcional(valor) is None:
        return {
            nombre: None,
            nombre + "_hora": None,
            nombre + "_precision": None,
        }
    texto = str(valor)
    try:
        if len(texto) == 10:
            dia, hora = date.fromisoformat(texto), None
        else:
            fecha = datetime.fromisoformat(texto)
            if fecha.tzinfo is not None:
                raise ValueError(
                    "La fuente requiere decisión de zona horaria."
                )
            dia, hora = fecha.date(), fecha.time()
    except ValueError as error:
        raise ErrorValidacion("Fecha normalizada incompatible.") from error
    if precision == "fecha":
        hora = None
    return {
        nombre: dia,
        nombre + "_hora": hora,
        nombre + "_precision": "fecha_hora" if hora else "fecha",
    }


def indice(filas: list[dict], campo: str) -> dict[str, dict]:
    """Construye un índice y rechaza claves ausentes o duplicadas."""
    resultado = {}
    for fila in filas:
        clave = fila.get(campo)
        if not isinstance(clave, str) or not clave or clave in resultado:
            raise ErrorValidacion(f"Clave inválida o repetida: {campo}.")
        resultado[clave] = fila
    return resultado


class Fuentes:
    """Carga artefactos y verifica sus manifiestos antes de tocar la DB."""

    def __init__(self, root: Path):
        """Lee los procesados y metadatos; no deserializa archivos joblib."""
        self.root = root
        self.data = root / "data/processed"
        self.out = root / "outputs/clasificacion_04"
        self.paths = [self.data / n for n in PROCESADOS]
        self.paths += [self.out / n for n in ARTEFACTOS]
        self.valores = {}
        self.hashes = {}
        for path in self.paths:
            if not path.is_file():
                raise ErrorValidacion(f"Falta entrada: {path.name}.")
            self.hashes[str(path.relative_to(root)).replace("\\", "/")] = (
                huella(path)
            )
            if path.suffix == ".csv":
                self.valores[path.name] = leer_csv(path)
            elif path.suffix == ".json":
                self.valores[path.name] = leer_json(path)
        self.verificar_manifiestos()

    def lista(self, nombre: str) -> list[dict]:
        """Devuelve registros de un archivo de lista validando su tipo."""
        return registros(self.valores[nombre])

    def objeto(self, nombre: str) -> dict:
        """Devuelve un manifiesto u objeto validando su tipo."""
        return objeto(self.valores[nombre])

    def comprobar(self, path: Path, esperado: str) -> None:
        """Verifica un archivo acotado al proyecto contra su huella."""
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise ErrorValidacion("Ruta de manifiesto fuera del proyecto.")
        if not path.is_file() or huella(path) != esperado:
            raise ErrorValidacion(f"Huella inconsistente: {path.name}.")

    def verificar_manifiestos(self) -> None:
        """Comprueba entradas, salidas y artefactos de las etapas previas."""
        for name, detalle in self.objeto("manifest.json")["archivos"].items():
            self.comprobar(self.data / name, detalle["sha256"])
        ia = self.objeto("manifest_extraccion_ia.json")
        for name, campo in {
            "conversaciones.json": "fuente_sha256",
            "extracciones_conversaciones_ia.json": "resultados_sha256",
            "incidencias_extraccion_ia.json": "incidencias_sha256",
            "extracciones_conversaciones_descartadas.json": (
                "descartadas_sha256"
            ),
            "conversaciones_utilizables_ia.json": (
                "conversaciones_utilizables_sha256"
            ),
        }.items():
            self.comprobar(self.data / name, ia[campo])
        clasificacion = self.objeto("manifest_clasificacion.json")
        for grupo in ["hashes_entrada", "hashes_salida"]:
            for name, digest in clasificacion[grupo].items():
                self.comprobar(self.data / name, digest)
        self.comprobar(
            self.out / "modelo_experimental.joblib",
            clasificacion["modelo_sha256"],
        )
        revision = self.objeto("revision_resultados.json")
        self.comprobar(
            self.out / "desbalance_v2/manifest_desbalance.json",
            revision["manifest_ejecucion_sha256"],
        )
        manifiesto = self.objeto("manifest_desbalance.json")
        self.comprobar(
            self.root / manifiesto["fuente"], manifiesto["fuente_sha256"]
        )
        for name, digest in manifiesto["salidas_sha256"].items():
            self.comprobar(self.out / "desbalance_v2" / name, digest)

    def id_archivo(self, nombre: str) -> str:
        """Identifica un archivo procesado por ruta y contenido."""
        path = "data/processed/" + nombre
        return identidad(path, self.hashes[path])
