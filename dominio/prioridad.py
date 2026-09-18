"""Prioridad comercial basada exclusivamente en señales verificables."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

MAXIMO_PUNTOS_PRIORIDAD = 90
"""Máximo de puntos de la política operacional vigente."""

MODELOS_SIN_IDENTIFICAR = frozenset({"", "DESCONOCIDO", "AMBIGUO"})
FORMAS_PAGO_CON_SENAL = frozenset({"credito", "contado"})


@dataclass(frozen=True)
class PrioridadEntrada:
    """Contiene únicamente las señales usadas por las reglas de prioridad.

    Args:
        modelo_sku: SKU identificado o un marcador de desconocido/ambigüedad.
        cuota_inicial_positiva: Indica una cuota positiva declarada de forma
            explícita.
        forma_pago: Forma de pago declarada por el cliente, si existe.
        cliente_pidio_cita: Indica una cita solicitada de forma explícita.
    """

    modelo_sku: str | None
    cuota_inicial_positiva: bool
    forma_pago: str | None
    cliente_pidio_cita: bool


@dataclass(frozen=True)
class ContribucionPrioridad:
    """Explica una señal que aportó puntos a la prioridad."""

    senal: str
    puntos: int
    explicacion: str


@dataclass(frozen=True)
class PrioridadResultado:
    """Representa el resultado operativo explicable de una calificación."""

    puntos: int
    score: Decimal
    temperatura: str
    contribuciones: tuple[ContribucionPrioridad, ...]


def calcular_prioridad(entrada: PrioridadEntrada) -> PrioridadResultado:
    """Calcula puntos, score y temperatura sin inferir datos ausentes.

    Args:
        entrada: Señales comerciales cuya procedencia ya fue validada.

    Returns:
        Resultado de reglas `reglas_evidencia_v1`. El score no es una
        probabilidad de compra.
    """
    contribuciones: list[ContribucionPrioridad] = []
    if _modelo_identificado(entrada.modelo_sku):
        contribuciones.append(
            ContribucionPrioridad(
                senal="modelo_identificado",
                puntos=10,
                explicacion="Modelo identificado: +10 puntos.",
            )
        )
    if entrada.cuota_inicial_positiva:
        contribuciones.append(
            ContribucionPrioridad(
                senal="inicial_positiva",
                puntos=30,
                explicacion="Inicial positiva declarada: +30 puntos.",
            )
        )
    if entrada.forma_pago in FORMAS_PAGO_CON_SENAL:
        contribuciones.append(
            ContribucionPrioridad(
                senal="forma_pago_declarada",
                puntos=10,
                explicacion="Forma de pago declarada: +10 puntos.",
            )
        )
    if entrada.cliente_pidio_cita:
        contribuciones.append(
            ContribucionPrioridad(
                senal="cita_solicitada",
                puntos=40,
                explicacion="Cliente pidió cita: +40 puntos.",
            )
        )

    puntos = sum(item.puntos for item in contribuciones)
    score = (
        Decimal(puntos * 100) / Decimal(MAXIMO_PUNTOS_PRIORIDAD)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return PrioridadResultado(
        puntos=puntos,
        score=score,
        temperatura=_temperatura(entrada),
        contribuciones=tuple(contribuciones),
    )


def clasificar_cola(
    temperatura: str,
    todas_consultas_descartadas: bool,
    estado_contexto: str,
) -> tuple[str, str]:
    """Selecciona una cola y acción sugerida sin alterar la prioridad.

    Args:
        temperatura: Temperatura calculada por las reglas operativas.
        todas_consultas_descartadas: Indica descarte CRM de todas las
            consultas.
        estado_contexto: Calidad temporal o semántica del contexto comercial.

    Returns:
        Par con el nombre de cola y una acción sugerida para el asesor.
    """
    if todas_consultas_descartadas:
        return (
            "revision_descartado_crm",
            "Revisar motivo del descarte en CRM antes de reactivar.",
        )
    if estado_contexto == "revision_orden":
        return (
            "revision_datos",
            "Revisar orden temporal antes de usar declaraciones.",
        )
    if temperatura == "sin_informacion_suficiente":
        return (
            "primer_contacto_o_ampliar_informacion",
            "Confirmar interés y completar información; no asumir desinterés.",
        )
    if temperatura == "caliente":
        return (
            "seguimiento_comercial",
            "Confirmar disponibilidad y estado de la cita solicitada; "
            "no asumir que sigue pendiente.",
        )
    return (
        "seguimiento_comercial",
        "Retomar la conversación y responder a lo solicitado por el cliente.",
    )


def _modelo_identificado(modelo_sku: str | None) -> bool:
    """Indica si el valor contiene un SKU verificable."""
    texto = "" if modelo_sku is None else str(modelo_sku).strip()
    return texto not in MODELOS_SIN_IDENTIFICAR


def _temperatura(entrada: PrioridadEntrada) -> str:
    """Clasifica por señal explícita, sin aplicar umbrales al score."""
    if entrada.cliente_pidio_cita:
        return "caliente"
    if (
        entrada.cuota_inicial_positiva
        or entrada.forma_pago in FORMAS_PAGO_CON_SENAL
    ):
        return "tibio"
    return "sin_informacion_suficiente"
