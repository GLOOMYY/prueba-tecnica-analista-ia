"""Validación y resolución pura para la primera captura de un lead."""

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from .identidad import (
    TelefonoNormalizado,
    limpiar_texto,
    normalizar_telefono_colombia,
)
from .prioridad import PrioridadEntrada, PrioridadResultado, calcular_prioridad

_CORREO_PATRON = re.compile(
    r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    flags=re.ASCII,
)


class EstadoResolucionIdentidad(StrEnum):
    """Describe el resultado seguro de comparar candidatos de identidad."""

    NUEVA = "nueva"
    CONSULTA_EXISTENTE = "consulta_existente"
    REVISION_REQUERIDA = "revision_requerida"


@dataclass(frozen=True)
class EntradaAlta:
    """Representa los campos comerciales de una captura manual.

    Attributes:
        empresa_id: Empresa resuelta por autorización del servidor.
        nombre_cliente: Nombre declarado por quien realiza la captura.
        telefono: Teléfono original, que puede quedar como incidencia.
        correo: Correo opcional de contacto, sin prueba de titularidad.
        modelo_sku: SKU confirmado o ``None`` si el modelo no se verificó.
        cuota_inicial: Importe de inicial declarado por el cliente.
        forma_pago: Forma de pago declarada, si existe.
        cliente_pidio_cita: Solicitud explícita de cita.
    """

    empresa_id: str
    nombre_cliente: str
    telefono: str | None
    correo: str | None
    modelo_sku: str | None = None
    cuota_inicial: Decimal | None = None
    forma_pago: str | None = None
    cliente_pidio_cita: bool = False


@dataclass(frozen=True)
class AltaPreparada:
    """Contiene una entrada validada sin sustituir datos de origen.

    Attributes:
        empresa_id: Ámbito de negocio validado.
        nombre_cliente: Nombre sin espacios repetidos.
        telefono: Resultado de normalización del campo original.
        correo: Correo estructuralmente válido o ``None``.
        incidencias: Razones observables que deben persistirse con la captura.
        prioridad: Resultado explicable de las señales de la captura manual.
    """

    empresa_id: str
    nombre_cliente: str
    telefono: TelefonoNormalizado
    correo: str | None
    incidencias: tuple[str, ...]
    prioridad: PrioridadResultado


@dataclass(frozen=True)
class CandidatoIdentidad:
    """Candidato filtrado por teléfono y nombre por un adaptador."""

    empresa_id: str
    lead_consolidado_id: str
    visible_para_actor: bool


@dataclass(frozen=True)
class ResolucionIdentidad:
    """Indica si se crea un lead, una consulta o una revisión restringida."""

    estado: EstadoResolucionIdentidad
    lead_consolidado_id: str | None
    motivo: str | None


def preparar_alta(entrada: EntradaAlta) -> AltaPreparada:
    """Valida una alta y calcula solo su prioridad verificable.

    Args:
        entrada: Captura manual ya asociada a una empresa autorizada.

    Returns:
        Datos normalizados, incidencias y prioridad de reglas.

    Raises:
        ValueError: Si faltan datos obligatorios, no hay contacto útil o un
            importe declarado es negativo.
    """
    empresa_id = limpiar_texto(entrada.empresa_id)
    nombre_cliente = limpiar_texto(entrada.nombre_cliente)
    if empresa_id is None:
        raise ValueError("La empresa autorizada es obligatoria.")
    if nombre_cliente is None:
        raise ValueError("El nombre del cliente es obligatorio.")
    if len(nombre_cliente) > 200:
        raise ValueError("El nombre del cliente supera 200 caracteres.")

    telefono = normalizar_telefono_colombia(entrada.telefono)
    correo = _normalizar_correo(entrada.correo)
    if limpiar_texto(entrada.correo) is not None and correo is None:
        raise ValueError("El correo no tiene una estructura válida.")
    if telefono.valor is None and correo is None:
        raise ValueError("Se requiere un teléfono utilizable o correo válido.")
    if entrada.cuota_inicial is not None and entrada.cuota_inicial < 0:
        raise ValueError("La cuota inicial no puede ser negativa.")

    incidencias = ()
    if telefono.estado not in {"faltante", "valido"}:
        incidencias = (f"telefono:{telefono.estado}",)
    prioridad = calcular_prioridad(
        PrioridadEntrada(
            modelo_sku=entrada.modelo_sku,
            cuota_inicial_positiva=(entrada.cuota_inicial or Decimal(0)) > 0,
            forma_pago=entrada.forma_pago,
            cliente_pidio_cita=entrada.cliente_pidio_cita,
        )
    )
    return AltaPreparada(
        empresa_id=empresa_id,
        nombre_cliente=nombre_cliente,
        telefono=telefono,
        correo=correo,
        incidencias=incidencias,
        prioridad=prioridad,
    )


def resolver_identidad(
    empresa_id: str,
    candidatos: tuple[CandidatoIdentidad, ...],
) -> ResolucionIdentidad:
    """Resuelve candidatos de la empresa sin revelar una cartera ajena.

    Args:
        empresa_id: Empresa autorizada de la solicitud.
        candidatos: Coincidencias conservadoras halladas por un adaptador.

    Returns:
        Decisión de crear, agregar consulta o enviar a revisión restringida.

    Raises:
        ValueError: Si un adaptador entrega un candidato de otra empresa.
    """
    for candidato in candidatos:
        if candidato.empresa_id != empresa_id:
            raise ValueError("Un candidato no pertenece a la empresa activa.")
    if not candidatos:
        return ResolucionIdentidad(EstadoResolucionIdentidad.NUEVA, None, None)
    if len(candidatos) > 1:
        return ResolucionIdentidad(
            EstadoResolucionIdentidad.REVISION_REQUERIDA,
            None,
            "identidad_ambigua",
        )

    candidato = candidatos[0]
    if not candidato.visible_para_actor:
        return ResolucionIdentidad(
            EstadoResolucionIdentidad.REVISION_REQUERIDA,
            None,
            "coincidencia_fuera_de_cartera",
        )
    return ResolucionIdentidad(
        EstadoResolucionIdentidad.CONSULTA_EXISTENTE,
        candidato.lead_consolidado_id,
        None,
    )


def _normalizar_correo(valor: str | None) -> str | None:
    """Devuelve un correo estructuralmente válido sin afirmar titularidad."""
    correo = limpiar_texto(valor)
    if correo is None:
        return None
    if not _CORREO_PATRON.fullmatch(correo):
        return None
    return correo.casefold()
