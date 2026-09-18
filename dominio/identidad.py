"""Reglas puras de identidad para leads dentro de una empresa.

Estas reglas no hacen consultas ni deciden por sí solas que dos personas se
fusionan. Solo normalizan valores y entregan comparaciones conservadoras para
que los bordes web y de lote apliquen la misma política.
"""

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class TelefonoNormalizado:
    """Representa el resultado verificable de normalizar un teléfono.

    Attributes:
        valor: Móvil E.164 o ``None`` si no es utilizable.
        estado: Motivo de aceptación, ausencia o rechazo del valor de origen.
    """

    valor: str | None
    estado: str


def limpiar_texto(valor: object) -> str | None:
    """Quita espacios sin convertir ausencias en texto.

    Args:
        valor: Valor recibido desde una fuente o formulario.

    Returns:
        Texto sin espacios repetidos, o ``None`` si falta o queda vacío.
    """
    if valor is None or _es_nan(valor):
        return None
    texto = re.sub(r"\s+", " ", str(valor)).strip()
    return texto or None


def clave_texto(valor: object) -> str | None:
    """Construye una clave comparable sin tildes ni diferencia de mayúsculas.

    Args:
        valor: Texto recibido desde una fuente o formulario.

    Returns:
        Texto comparable o ``None`` cuando falta un valor.
    """
    texto = limpiar_texto(valor)
    if texto is None:
        return None
    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto.casefold())
        if unicodedata.category(caracter) != "Mn"
    )


def normalizar_telefono_colombia(valor: object) -> TelefonoNormalizado:
    """Normaliza solo móviles colombianos con evidencia suficiente.

    Args:
        valor: Teléfono de entrada en cualquiera de los formatos admitidos.

    Returns:
        Resultado con el teléfono E.164 o ``None`` y una razón explícita.
    """
    texto = limpiar_texto(valor)
    if texto is None:
        return TelefonoNormalizado(None, "faltante")
    if not re.fullmatch(r"\+?[0-9\s().-]+", texto):
        return TelefonoNormalizado(None, "caracteres_no_permitidos")

    digitos = re.sub(r"\D", "", texto)
    if len(digitos) == 12 and digitos.startswith("57"):
        digitos = digitos[2:]
    if len(digitos) != 10:
        return TelefonoNormalizado(None, "longitud_invalida")
    if not digitos.startswith("3"):
        return TelefonoNormalizado(None, "revisar_prefijo_movil")
    return TelefonoNormalizado(f"+57{digitos}", "valido")


def nombres_compatibles(nombre_a: object, nombre_b: object) -> bool:
    """Compara nombres e iniciales con una política conservadora.

    La compatibilidad no equivale a una fusión: requiere además una señal de
    contacto compartida y la misma empresa en quien llame esta función.
    """
    clave_a, clave_b = clave_texto(nombre_a), clave_texto(nombre_b)
    if not clave_a or not clave_b:
        return False

    partes_a = [termino.strip(".") for termino in clave_a.split()]
    partes_b = [termino.strip(".") for termino in clave_b.split()]
    if len(partes_a) < 2 or len(partes_b) < 2:
        return False
    if partes_a == partes_b:
        return all(len(termino) > 1 for termino in partes_a)

    corto, largo = sorted(
        [partes_a, partes_b],
        key=lambda partes: (len(partes), sum(map(len, partes))),
    )
    if any(len(termino) <= 1 for termino in largo):
        return False
    primero_coincide = corto[0] == largo[0] or (
        len(corto[0]) == 1 and largo[0].startswith(corto[0])
    )
    if not primero_coincide or not any(
        len(termino) > 1 for termino in corto[1:]
    ):
        return False

    posicion = 1
    for termino in corto[1:]:
        if len(termino) <= 1:
            return False
        while posicion < len(largo) and largo[posicion] != termino:
            posicion += 1
        if posicion == len(largo):
            return False
        posicion += 1
    return True


def id_consolidado(empresa_id: str, referencia: str) -> str:
    """Genera un ID estable cuyo contenido incluye la empresa.

    Args:
        empresa_id: Identificador de la comercializadora propietaria.
        referencia: Clave estable del origen o contacto de esa empresa.

    Returns:
        Identificador técnico determinista para el lead consolidado.
    """
    contenido = json.dumps([empresa_id, referencia], ensure_ascii=False)
    huella = hashlib.sha256(contenido.encode("utf-8")).hexdigest()
    return f"LC-{huella[:20]}"


def _es_nan(valor: object) -> bool:
    """Reconoce NaN sin depender de bibliotecas tabulares."""
    return isinstance(valor, float) and math.isnan(valor)
