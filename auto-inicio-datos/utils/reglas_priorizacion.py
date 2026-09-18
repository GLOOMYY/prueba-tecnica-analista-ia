"""Reglas de priorización sin lectura de archivos al importar."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from dominio.prioridad import PrioridadEntrada, calcular_prioridad


def sha(path):
    """Calcula la huella del archivo para comprobar trazabilidad."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preparar_historico(df):
    """Construye solo las variables comerciales aprobadas."""
    x = df[
        [
            "canal",
            "modelo_sku",
            "manifesto_cuota_inicial",
            "forma_pago_declarada",
        ]
    ].copy()
    x["cita_observada"] = np.where(
        df.pidio_cita.eq("SI"), "SI", "NO_OBSERVADA"
    )
    return x.fillna("DESCONOCIDO").astype(str)


def score_reglas(x):
    """Pondera señales explícitas y devuelve puntos sobre 90."""
    columnas = [
        "modelo_sku",
        "manifesto_cuota_inicial",
        "forma_pago_declarada",
        "cita_observada",
    ]
    return np.array(
        [
            float(
                calcular_prioridad(
                    PrioridadEntrada(
                        modelo_sku=fila.modelo_sku,
                        cuota_inicial_positiva=(
                            fila.manifesto_cuota_inicial == "SI"
                        ),
                        forma_pago=fila.forma_pago_declarada,
                        cliente_pidio_cita=fila.cita_observada == "SI",
                    )
                ).score
                / 100
            )
            for fila in x[columnas].itertuples(index=False)
        ]
    )


def elegir_ultima(fechas):
    """Elige contexto reciente solo si el orden temporal es verificable."""
    parsed = pd.to_datetime(pd.Series(fechas), format="mixed", errors="coerce")
    if parsed.isna().any():
        return (None, "fecha_invalida")
    dia = parsed.dt.normalize()
    candidatos = np.flatnonzero(dia.eq(dia.max()))
    if len(candidatos) == 1:
        return (int(candidatos[0]), None)
    if any(len(str(fechas[i])) <= 10 for i in candidatos):
        return (None, "orden_intradia_desconocido")
    ix = np.flatnonzero(parsed.eq(parsed.max()))
    return (int(ix[0]), None) if len(ix) == 1 else (None, "empate_fecha")


def inicial_de_extraccion(ex):
    """Distingue inicial positiva, cero explícito y ausencia de evidencia."""
    d = ex["dinero"]["cuota_inicial"]
    if not d["evidencias"]:
        return "NO_INFORMA"
    if d["valor"] is not None:
        return (
            "SI"
            if d["valor"] > 0
            else "NO"
            if d["valor"] == 0
            else "NO_INFORMA"
        )
    if d["minimo"] is not None and d["minimo"] > 0:
        return "SI"
    return "NO_INFORMA"


def explicar_reglas(r):
    """Explica cada contribución del score sin llamarlo probabilidad."""
    prioridad = calcular_prioridad(
        PrioridadEntrada(
            modelo_sku=r.modelo_sku,
            cuota_inicial_positiva=r.manifesto_cuota_inicial == "SI",
            forma_pago=r.forma_pago_declarada,
            cliente_pidio_cita=r.cita_observada == "SI",
        )
    )
    motivos = " ".join(item.explicacion for item in prioridad.contribuciones)
    return motivos + (
        " Escala: puntos/90*100; no es probabilidad. Ause"
        "ncia de señal no es rechazo."
    )


def registros(df):
    """Convierte un DataFrame en registros JSON con nulos portables."""
    return json.loads(df.to_json(orient="records", force_ascii=False))
