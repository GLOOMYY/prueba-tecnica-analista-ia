"""Reglas de negocio compartidas entre la web y el flujo de datos.

Los módulos de este paquete no dependen de Django, pandas ni conexiones
externas. Así las mismas decisiones comerciales se pueden probar y reutilizar
en cada borde de la aplicación.
"""

from .alta import (
    AltaPreparada,
    CandidatoIdentidad,
    EntradaAlta,
    EstadoResolucionIdentidad,
    ResolucionIdentidad,
    preparar_alta,
    resolver_identidad,
)
from .identidad import (
    TelefonoNormalizado,
    clave_texto,
    id_consolidado,
    limpiar_texto,
    nombres_compatibles,
    normalizar_telefono_colombia,
)
from .prioridad import (
    MAXIMO_PUNTOS_PRIORIDAD,
    PrioridadEntrada,
    PrioridadResultado,
    calcular_prioridad,
    clasificar_cola,
)

__all__ = [
    "MAXIMO_PUNTOS_PRIORIDAD",
    "PrioridadEntrada",
    "PrioridadResultado",
    "calcular_prioridad",
    "clasificar_cola",
    "TelefonoNormalizado",
    "clave_texto",
    "id_consolidado",
    "limpiar_texto",
    "nombres_compatibles",
    "normalizar_telefono_colombia",
    "AltaPreparada",
    "CandidatoIdentidad",
    "EntradaAlta",
    "EstadoResolucionIdentidad",
    "ResolucionIdentidad",
    "preparar_alta",
    "resolver_identidad",
]
