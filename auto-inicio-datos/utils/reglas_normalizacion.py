"""Reglas de normalización sin lectura de archivos al importar."""

import calendar
import json
import math
import re
from datetime import datetime

import pandas as pd

from dominio.identidad import (
    clave_texto as clave_texto_dominio,
)
from dominio.identidad import id_consolidado as id_consolidado_dominio
from dominio.identidad import limpiar_texto as limpiar_texto_dominio
from dominio.identidad import (
    nombres_compatibles as nombres_compatibles_dominio,
)
from dominio.identidad import normalizar_telefono_colombia


def limpiar_texto(valor):
    """Quita espacios sobrantes y conserva ausentes como pd.NA."""
    if pd.isna(valor):
        return pd.NA
    texto = limpiar_texto_dominio(valor)
    return texto if texto is not None else pd.NA


def clave_texto(valor):
    """Construye una clave comparable sin tildes ni mayúsculas."""
    if pd.isna(valor):
        return None
    return clave_texto_dominio(valor)


def normalizar_telefono(valor):
    """Acepta móviles colombianos y marca el resto sin inventar números."""
    if pd.isna(valor):
        return (pd.NA, "faltante")
    resultado = normalizar_telefono_colombia(valor)
    telefono = resultado.valor if resultado.valor is not None else pd.NA
    return (telefono, resultado.estado)


def normalizar_fecha(valor, orden_entrada="DMY"):
    """Interpreta un orden explícito y explica fechas imposibles."""
    texto = limpiar_texto(valor)
    if pd.isna(texto):
        return (
            pd.NaT,
            "faltante",
            pd.NA,
            "La fuente no informa una fecha; no se imputa un valor.",
        )
    inicio = re.fullmatch(
        (
            "(\\d{4})([-/])(\\d{1,2})\\2(\\d{1,2})(?:[ T](\\d{2}):"
            "(\\d{2})(?::(\\d{2}))?)?"
        ),
        texto,
    )
    final = re.fullmatch(
        (
            "(\\d{1,2})([-/])(\\d{1,2})\\2(\\d{4})(?:[ T](\\d{2}):"
            "(\\d{2})(?::(\\d{2}))?)?"
        ),
        texto,
    )
    match = inicio or final
    if not match:
        return (
            pd.NaT,
            "invalida",
            pd.NA,
            (
                "Formato no admitido: se requiere AAAA-MM-DD o DD"
                "-MM-AAAA (también con barras), con hora HH:MM[:S"
                "S] opcional."
            ),
        )
    if inicio:
        anio, mes, dia = (int(match[1]), int(match[3]), int(match[4]))
        orden = "año-mes-día"
    else:
        primero, segundo, anio = (int(match[1]), int(match[3]), int(match[4]))
        dia, mes = (
            (segundo, primero)
            if orden_entrada == "MDY"
            else (primero, segundo)
        )
        orden = (
            "mes-día-año de origen, corregida a ISO"
            if orden_entrada == "MDY"
            else "día-mes-año"
        )
    precision = "fecha_hora" if match[5] is not None else "fecha"
    if not 1 <= anio <= 9999:
        return (
            pd.NaT,
            "invalida",
            precision,
            f"Año {anio} fuera del intervalo admitido (1–9999).",
        )
    if not 1 <= mes <= 12:
        return (
            pd.NaT,
            "invalida",
            precision,
            f"Interpretación {orden}: el mes sería {mes}, fuera de 1–12. "
            "El orden se evalúa junto con las otras fechas del mismo lead.",
        )
    maximo = calendar.monthrange(anio, mes)[1]
    if not 1 <= dia <= maximo:
        return (
            pd.NaT,
            "invalida",
            precision,
            f"Interpretación {orden}: día {dia} imposible; "
            f"el mes {mes:02d} de {anio} tiene {maximo} días.",
        )
    hora, minuto, segundo = [int(match[i] or 0) for i in (5, 6, 7)]
    if hora > 23 or minuto > 59 or segundo > 59:
        return (
            pd.NaT,
            "invalida",
            precision,
            f"Hora inválida {hora:02d}:{minuto:02d}:{segundo:02d}; "
            "se requiere 00–23:00–59:00–59.",
        )
    valor_normalizado = pd.Timestamp(
        datetime(anio, mes, dia, hora, minuto, segundo)
    )
    comentario = f"Interpretada como {orden}: {anio:04d}-{mes:02d}-{dia:02d}."
    if precision == "fecha":
        comentario += (
            " La fuente no informa hora; no usar 00:00 como hora real."
        )
    return (valor_normalizado, "valida", precision, comentario)


def evidencia_orden(valor):
    """Detecta componentes que descartan un orden de día y mes."""
    if pd.isna(valor):
        return None
    m = re.match(
        "^(\\d{1,2})[-/](\\d{1,2})[-/]\\d{4}(?:\\D|$)", str(valor).strip()
    )
    if not m:
        return None
    a, b = map(int, m.groups())
    if 1 <= a <= 12 and 13 <= b <= 31:
        return "MDY"
    if 13 <= a <= 31 and 1 <= b <= 12:
        return "DMY"
    return None


def secuencia_posible(resultados):
    """Comprueba el orden temporal entre registro y contacto."""
    registro, contacto = resultados
    if pd.isna(registro[0]) or pd.isna(contacto[0]):
        return None
    if "fecha" in [registro[2], contacto[2]]:
        return registro[0].date() <= contacto[0].date()
    return registro[0] <= contacto[0]


def clave_modelo(valor):
    """Unifica grafías comparables sin elegir un modelo por intuición."""
    clave = clave_texto(valor)
    if clave is None:
        return None
    clave = re.sub("^a\\.k\\.t\\b", "akt", clave)
    for error, marca in {
        "hnda": "honda",
        "bajai": "bajaj",
        "suzuky": "suzuki",
        "heroo": "hero",
    }.items():
        clave = re.sub("^" + error + "\\b", marca, clave)
    return re.sub("\\s+20\\d{2}$", "", clave).strip()


def validar_numero(valor, entero, permite_cero):
    """Distingue ausentes, números inválidos y límites permitidos."""
    if pd.isna(valor) or not str(valor).strip():
        return (pd.NA, "faltante")
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero):
        return (pd.NA, "no_numerico")
    if not math.isfinite(float(numero)):
        return (pd.NA, "no_finito")
    if numero < 0:
        return (pd.NA, "negativo")
    if numero == 0 and (not permite_cero):
        return (pd.NA, "cero_no_permitido")
    if entero and numero % 1 != 0:
        return (pd.NA, "debe_ser_entero")
    return (numero, "valido")


def nombres_compatibles(nombre_a, nombre_b):
    """Compara nombres e iniciales para consolidación conservadora."""
    return nombres_compatibles_dominio(nombre_a, nombre_b)


def id_consolidado(empresa, referencia):
    """Genera una identidad estable que incluye la empresa."""
    return id_consolidado_dominio(empresa, referencia)


def valores_informados(serie):
    """Deduplica valores presentes sin completar los faltantes."""
    return sorted(set(str(v) for v in serie.dropna()))


def valor_json(valor):
    """Convierte nulos y tipos tabulares a valores JSON portables."""
    if isinstance(valor, dict):
        return {str(k): valor_json(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [valor_json(v) for v in valor]
    if valor is None or valor is pd.NA or valor is pd.NaT:
        return None
    if isinstance(valor, pd.Timestamp):
        return valor.isoformat(sep=" ")
    if hasattr(valor, "item"):
        return valor_json(valor.item())
    if isinstance(valor, float) and (not math.isfinite(valor)):
        return None
    return valor


def fecha_exportable(valor, precision=None):
    """Conserva la precisión de la fecha al generar texto ISO."""
    if pd.isna(valor):
        return None
    return pd.Timestamp(valor).strftime(
        "%Y-%m-%d" if precision == "fecha" else "%Y-%m-%d %H:%M:%S"
    )


def tabla_exportable(tabla, columnas_fuente):
    """Exporta valores normalizados junto con sus originales."""
    salida = pd.DataFrame(index=tabla.index)
    for campo in columnas_fuente:
        normalizado = campo + "_normalizado"
        if normalizado in tabla.columns:
            salida[campo + "_original"] = tabla[campo]
            if pd.api.types.is_datetime64_any_dtype(tabla[normalizado]):
                salida[campo] = [
                    fecha_exportable(v, precision)
                    for v, precision in zip(
                        tabla[normalizado],
                        tabla.get(
                            campo + "_precision",
                            pd.Series(None, index=tabla.index),
                        ),
                        strict=False,
                    )
                ]
            else:
                salida[campo] = tabla[normalizado]
        else:
            salida[campo] = tabla[campo]
    for campo in tabla.columns:
        if campo not in columnas_fuente and (
            not campo.endswith("_normalizado")
        ):
            salida[campo] = tabla[campo]
    return salida


def escribir_csv(tabla, ruta):
    """Serializa estructuras y fechas sin modificar el DataFrame recibido."""
    salida = tabla.copy(deep=True)
    for campo in salida.columns:
        if pd.api.types.is_datetime64_any_dtype(salida[campo]):
            salida[campo] = salida[campo].map(fecha_exportable)
        salida[campo] = salida[campo].map(
            lambda v: (
                json.dumps(valor_json(v), ensure_ascii=False, allow_nan=False)
                if isinstance(v, (list, tuple, dict, set))
                else v
            )
        )
    salida.to_csv(
        ruta, index=False, encoding="utf-8", lineterminator="\n", na_rep=""
    )
