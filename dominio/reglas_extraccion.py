"""Reglas reutilizables de extraccion; sin lectura de archivos al importar."""

import re
import unicodedata
from collections import defaultdict
from decimal import Decimal


def entrada(grupo):
    """Numera mensajes y conserva el emisor dentro del contrato de Gemini."""
    return [
        {
            "conversacion_id": c["conversacion_id"],
            "mensajes": [
                {"numero": i, "emisor": m["emisor"], "texto": m["texto"]}
                for i, m in enumerate(c["mensajes"], 1)
            ],
        }
        for c in grupo
    ]


def simple(s):
    """Normaliza texto para comparaciones locales sin inferir significado."""
    return (
        unicodedata.normalize("NFKD", s)
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )


def convertir_numero(s, unidad):
    """Aplica la unidad monetaria explícita usando Decimal."""
    if re.fullmatch("\\d{1,3}(?:\\.\\d{3})+(?:,\\d{1,2})?", s):
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch("\\d+(?:,\\d{1,2})?", s):
        s = s.replace(",", ".")
    elif re.fullmatch("\\d+\\.\\d{1,2}", s):
        pass
    else:
        raise ValueError("Separadores numéricos ambiguos")
    factor = (
        1000000
        if unidad and unidad != "mil"
        else 1000
        if unidad == "mil"
        else 1
    )
    return float(Decimal(s) * factor)


def normalizar_nombre(s):
    """Construye la clave de una mención para consulta del catálogo."""
    return re.sub("[^a-z0-9]", "", simple(s))


def agrupar(cs):
    """Agrupa hasta cinco conversaciones de la misma empresa."""
    empresas = defaultdict(list)
    grupos = []
    for c in cs:
        if c["empresa_id"] is None:
            grupos.append([c])
        else:
            empresas[c["empresa_id"]].append(c)
    for grupo in empresas.values():
        grupos.extend(grupo[i : i + 5] for i in range(0, len(grupo), 5))
    return grupos


def errores_tecnicos(r):
    """Cuenta pendientes técnicos sin confundirlos con contradicciones."""
    return sum(
        i["estado"] == "pendiente_revision"
        and i["tipo"] != "importes_contradictorios"
        for i in r["incidencias"]
    )
