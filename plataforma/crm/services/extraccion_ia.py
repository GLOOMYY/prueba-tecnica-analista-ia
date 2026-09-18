"""Extracción individual con Gemini y validación de evidencia por emisor."""

import hashlib
import json
import math
import os
from collections.abc import Callable
from pathlib import Path

from cuentas.acceso import alcance_empresa
from django.db import connection
from django.shortcuts import get_object_or_404
from dotenv import dotenv_values

from crm.contexto_empresa import transaccion_empresa
from crm.historico import _consultar
from crm.models import CapturaEstructurada, EstadoOperativoLead
from crm.selectores import estados_visibles
from crm.services.publicacion_ia import guardar_historia_ia
from crm.services.trabajos import (
    LeasePerdido,
    bloquear_trabajo,
    completar_trabajo,
    encolar_trabajo,
    reintentar_trabajo,
)
from dominio.contrato_extraccion import PROMPT, SCHEMA
from dominio.cuota_ia import reservar_cuota
from dominio.extraccion_individual import normalizar_individual
from dominio.reglas_extraccion import entrada

MODELO_PREDETERMINADO = "gemini-3.5-flash-lite"
VERSION_PROMPT = "2.0"
CAMPO_CLIENTE = {
    "modelos_interes",
    "presupuesto",
    "cuota_inicial",
    "forma_pago",
    "intencion_declarada",
    "objecion_principal",
    "cliente_pidio_cita",
    "cliente_pidio_cotizacion",
    "cliente_pidio_credito",
}
CAMPO_ASESOR = {"asesor_ofrecio_credito"}
CLAVES = CAMPO_CLIENTE | CAMPO_ASESOR


class ErrorExtraccion(ValueError):
    """La respuesta no satisface el contrato de evidencia verificable."""


class ErrorProveedor(RuntimeError):
    """Fallo externo categorizado sin conservar datos privados."""

    def __init__(self, categoria: str):
        """Guarda exclusivamente el código para la política de reintentos."""
        self.categoria = categoria
        super().__init__(categoria)


def esquema_resultado() -> dict:
    """Devuelve el contrato aprobado compartido con el pipeline."""
    return SCHEMA


def encolar_extraccion_conversacion(
    *,
    usuario,
    empresa_id: str,
    conversacion_id: str,
) -> tuple[dict, bool]:
    """Crea un trabajo de IA para una conversación visible del actor.

    Args:
        usuario: Asesor o supervisor autenticado.
        empresa_id: Empresa autorizada para la petición.
        conversacion_id: Conversación histórica utilizable.

    Returns:
        Identificador del trabajo y si se creó en esta petición.
    """
    with alcance_empresa(usuario, empresa_id) as miembro:
        _bloquear_ingestion()
        conversacion = cargar_conversacion(conversacion_id, miembro.empresa_id)
        estado = get_object_or_404(
            estados_visibles(miembro),
            lead_consolidado_id=conversacion["lead_consolidado_id"],
        )
        if estado.priorizacion_vigente_id:
            contexto = _consultar(
                "SELECT lead_id_contexto FROM priorizaciones "
                "WHERE empresa_id = %s AND priorizacion_id = %s",
                [miembro.empresa_id, estado.priorizacion_vigente_id],
            )
            if (
                not contexto
                or contexto[0]["lead_id_contexto"]
                != conversacion["lead_id_origen"]
            ):
                raise ErrorExtraccion(
                    "La conversación no pertenece a la consulta vigente."
                )
        configuracion = {
            "autor_id": usuario.pk,
            "lead_id": estado.lead_consolidado_id,
            "modelo": MODELO_PREDETERMINADO,
            "version_prompt": VERSION_PROMPT,
            "max_intentos": 3,
            "espera_segundos": 30,
        }
        huella = huella_conversacion(conversacion, configuracion)
        trabajo, creado = encolar_trabajo(
            empresa_id=miembro.empresa_id,
            tipo_entidad="conversacion",
            entidad_id=conversacion_id,
            tipo_trabajo="extraer_ia",
            revision_entrada=estado.revision_entrada,
            configuracion=configuracion,
            huella_entrada=huella,
        )
        respuesta = {"trabajo_id": str(trabajo.pk), "estado": trabajo.estado}
        return respuesta, creado


def cargar_conversacion(conversacion_id: str, empresa_id: str) -> dict:
    """Lee una conversación utilizable y sus mensajes del esquema histórico.

    Args:
        conversacion_id: Identificador histórico de la conversación.
        empresa_id: Ámbito de empresa del trabajo durable.

    Returns:
        Conversación, lead y mensajes ordenados.

    Raises:
        ErrorExtraccion: Si no pertenece al trabajo o fue descartada.
    """
    filas = _consultar(
        "SELECT conversacion_id, lead_consolidado_id, empresa_id, descartada, "
        "lead_id_origen "
        "FROM conversaciones WHERE conversacion_id = %s AND empresa_id = %s",
        [conversacion_id, empresa_id],
    )
    if len(filas) != 1 or filas[0]["descartada"]:
        raise ErrorExtraccion("Conversación no disponible para extracción.")
    mensajes = _consultar(
        "SELECT posicion, emisor, texto FROM mensajes "
        "WHERE conversacion_id = %s "
        "ORDER BY posicion",
        [conversacion_id],
    )
    if not mensajes:
        raise ErrorExtraccion("La conversación no tiene mensajes procesables.")
    return {**filas[0], "mensajes": mensajes}


def huella_conversacion(conversacion: dict, configuracion: dict) -> str:
    """Genera huella de contenido, modelo y versión sin guardar secretos."""
    entrada = {
        "empresa_id": conversacion.get("empresa_id"),
        "conversacion_id": conversacion.get("conversacion_id"),
        "mensajes": conversacion["mensajes"],
        "modelo": configuracion.get("modelo", MODELO_PREDETERMINADO),
        "version_prompt": configuracion.get("version_prompt", VERSION_PROMPT),
        "prompt": PROMPT,
        "schema": SCHEMA,
        "version_normalizador": "2.5",
    }
    return hashlib.sha256(
        json.dumps(entrada, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def validar_resultado(resultado: dict, mensajes: list[dict]) -> dict:
    """Valida esquema mínimo, emisor y posiciones antes de persistir.

    Args:
        resultado: JSON retornado por el proveedor de IA.
        mensajes: Mensajes originales con posición y emisor.

    Returns:
        Resultado normalizado con desconocidos explícitos.

    Raises:
        ErrorExtraccion: Si falta una clave o una evidencia es inválida, o cita
            atribuir un hecho a un emisor incorrecto.
    """
    claves_esperadas = CLAVES | {"evidencias"}
    if not isinstance(resultado, dict) or set(resultado) != claves_esperadas:
        raise ErrorExtraccion("La respuesta no coincide con el contrato fijo.")
    if not isinstance(resultado["modelos_interes"], list):
        raise ErrorExtraccion("Los modelos deben ser una lista.")
    if any(
        not isinstance(modelo, str) or not modelo.strip()
        for modelo in resultado["modelos_interes"]
    ):
        raise ErrorExtraccion("Cada modelo debe contener texto explícito.")
    for campo in ("presupuesto", "cuota_inicial"):
        valor = resultado[campo]
        if valor is not None and (
            type(valor) not in (int, float)
            or not math.isfinite(valor)
            or valor < 0
        ):
            raise ErrorExtraccion("El importe debe ser finito y no negativo.")
    for campo in CAMPO_ASESOR | {
        "cliente_pidio_cita",
        "cliente_pidio_credito",
        "cliente_pidio_cotizacion",
    }:
        if resultado[campo] is not None and type(resultado[campo]) is not bool:
            raise ErrorExtraccion("Los indicadores requieren booleano o null.")
    if resultado["forma_pago"] not in (None, "credito", "contado"):
        raise ErrorExtraccion("Forma de pago fuera del contrato.")
    for campo in ("intencion_declarada", "objecion_principal"):
        valor = resultado[campo]
        if valor is not None and (
            not isinstance(valor, str) or not valor.strip()
        ):
            raise ErrorExtraccion("El texto debe ser explícito o null.")
    posiciones = {mensaje["posicion"]: mensaje for mensaje in mensajes}
    por_campo: dict[str, list[int]] = {clave: [] for clave in CLAVES}
    evidencias = resultado["evidencias"]
    if not isinstance(evidencias, list):
        raise ErrorExtraccion("Las evidencias deben ser una lista.")
    for evidencia in evidencias:
        if not isinstance(evidencia, dict) or set(evidencia) != {
            "campo",
            "posicion",
            "cita",
        }:
            raise ErrorExtraccion(
                "La evidencia debe declarar campo, posición y cita."
            )
        campo, posicion = evidencia["campo"], evidencia["posicion"]
        if (
            not isinstance(campo, str)
            or campo not in CLAVES
            or type(posicion) is not int
            or posicion not in posiciones
        ):
            raise ErrorExtraccion(
                "La evidencia no corresponde a un mensaje real."
            )
        mensaje = posiciones[posicion]
        cita = evidencia["cita"]
        if (
            not isinstance(cita, str)
            or not cita.strip()
            or cita not in mensaje["texto"]
        ):
            raise ErrorExtraccion("La cita no existe en el mensaje original.")
        emisor = str(mensaje["emisor"]).strip().lower()
        if campo in CAMPO_CLIENTE and emisor != "cliente":
            raise ErrorExtraccion(
                "Un hecho del cliente cita al emisor incorrecto."
            )
        if campo in CAMPO_ASESOR and emisor != "asesor":
            raise ErrorExtraccion("Una oferta cita al emisor incorrecto.")
        por_campo[campo].append(posicion)
    for campo in CLAVES:
        valor = resultado[campo]
        tiene_valor = valor not in (None, [], "")
        if tiene_valor and not por_campo[campo]:
            raise ErrorExtraccion(
                "Todo hecho debe conservar evidencia explícita."
            )
    for modelo in resultado["modelos_interes"]:
        citas = [
            e["cita"] for e in evidencias if e["campo"] == "modelos_interes"
        ]
        if not any(modelo.casefold() in cita.casefold() for cita in citas):
            raise ErrorExtraccion("El modelo no aparece en su evidencia.")
    if (
        resultado["forma_pago"] == "contado"
        and resultado["cliente_pidio_credito"] is True
    ):
        raise ErrorExtraccion("Contado y crédito requieren revisión.")
    presupuesto = resultado["presupuesto"]
    inicial = resultado["cuota_inicial"]
    if (
        presupuesto is not None
        and inicial is not None
        and inicial > presupuesto
    ):
        raise ErrorExtraccion("La inicial supera el presupuesto declarado.")
    return {
        **resultado,
        "evidencias": sorted(
            evidencias, key=lambda item: (item["campo"], item["posicion"])
        ),
    }


def generar_con_gemini(conversacion: dict, configuracion: dict) -> dict:
    """Solicita JSON estricto a Gemini solo cuando el worker lo ejecuta.

    La importación del SDK y lectura de la clave ocurren dentro de la función,
    por lo que las pruebas y el servidor web no consumen cuota.
    """
    from google import genai
    from google.genai import errors, types
    from httpx import TransportError

    raiz = Path(__file__).resolve().parents[3]
    clave = os.environ.get("API_KEY_GEMINI") or dotenv_values(
        raiz / ".env"
    ).get("API_KEY_GEMINI")
    if not clave:
        raise ErrorExtraccion("Falta configurar la clave del proveedor IA.")
    if not reservar_cuota(configuracion.get("modelo", MODELO_PREDETERMINADO)):
        raise ErrorProveedor("cuota")
    cliente = genai.Client(
        api_key=clave,
        http_options=types.HttpOptions(
            timeout=60000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    contenido = json.dumps(entrada([conversacion]), ensure_ascii=False)

    try:
        respuesta = cliente.models.generate_content(
            model=configuracion.get("modelo", MODELO_PREDETERMINADO),
            contents=contenido,
            config=types.GenerateContentConfig(
                system_instruction=PROMPT,
                response_mime_type="application/json",
                response_json_schema=esquema_resultado(),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
                temperature=0,
            ),
        )
    except errors.APIError as error:
        categoria = "cuota" if error.code == 429 else "proveedor_no_disponible"
        if error.code in (400, 401, 403, 404):
            categoria = "configuracion_proveedor"
        raise ErrorProveedor(categoria) from None
    except TransportError:
        raise ErrorProveedor("error_transitorio") from None
    finally:
        cliente.close()
    try:
        return json.loads(respuesta.text)
    except (TypeError, json.JSONDecodeError) as error:
        raise ErrorExtraccion(
            "El proveedor no devolvió JSON válido."
        ) from error


def procesar_extraccion(
    trabajo,
    proveedor: Callable[[dict, dict], dict] = generar_con_gemini,
) -> str:
    """Ejecuta una extracción y publica solo si el trabajo sigue autorizado.

    El llamador entrega un trabajo recién reclamado. La llamada al proveedor
    ocurre fuera de la transacción de publicación. Captura, historia, score y
    cierre del trabajo se confirman juntos después de revalidar la entrada.
    """
    try:
        with transaccion_empresa(trabajo.empresa_id):
            bloquear_trabajo(trabajo.pk, trabajo.lease_token)
            conversacion = cargar_conversacion(
                trabajo.entidad_id, trabajo.empresa_id
            )
        lead_configurado = trabajo.configuracion.get("lead_id")
        if conversacion["lead_consolidado_id"] != lead_configurado:
            raise ErrorExtraccion(
                "El trabajo no coincide con el lead de la conversación."
            )
        huella = huella_conversacion(conversacion, trabajo.configuracion)
        if trabajo.huella_entrada and trabajo.huella_entrada != huella:
            with transaccion_empresa(trabajo.empresa_id):
                completar_trabajo(
                    trabajo_id=trabajo.pk,
                    lease_token=trabajo.lease_token,
                    revision_entrada_actual=trabajo.revision_entrada + 1,
                )
            return "obsoleto"
        bruto = trabajo.resultado_proveedor
        if bruto is None:
            bruto = proveedor(conversacion, trabajo.configuracion)
            with transaccion_empresa(trabajo.empresa_id):
                actual_trabajo = bloquear_trabajo(
                    trabajo.pk, trabajo.lease_token
                )
                actual_trabajo.resultado_proveedor = bruto
                actual_trabajo.save(update_fields=["resultado_proveedor"])
        if "conversaciones" in bruto:
            with transaccion_empresa(trabajo.empresa_id):
                catalogo = _consultar(
                    "SELECT m.sku, b.nombre AS marca, m.linea "
                    "FROM modelos_moto m "
                    "JOIN marcas b ON b.marca_id = m.marca_id",
                    [],
                )
            try:
                resultado = normalizar_individual(
                    bruto,
                    conversacion,
                    catalogo,
                    trabajo.configuracion.get("modelo", MODELO_PREDETERMINADO),
                )
            except ValueError as error:
                raise ErrorExtraccion(
                    "Contrato o evidencia inválidos."
                ) from error
        else:
            if trabajo.configuracion.get("version_prompt") == VERSION_PROMPT:
                raise ErrorExtraccion("Se requiere el contrato completo.")
            resultado = validar_resultado(bruto, conversacion["mensajes"])
        with transaccion_empresa(trabajo.empresa_id):
            _bloquear_ingestion()
            bloquear_trabajo(trabajo.pk, trabajo.lease_token)
            estado = EstadoOperativoLead.objects.select_for_update().get(
                empresa_id=trabajo.empresa_id,
                lead_consolidado_id=conversacion["lead_consolidado_id"],
            )
            actual = cargar_conversacion(
                trabajo.entidad_id, trabajo.empresa_id
            )
            revision = estado.revision_entrada
            if huella_conversacion(actual, trabajo.configuracion) != huella:
                revision = trabajo.revision_entrada + 1
            if not completar_trabajo(
                trabajo_id=trabajo.pk,
                lease_token=trabajo.lease_token,
                revision_entrada_actual=revision,
            ):
                return "obsoleto"
            captura = CapturaEstructurada.objects.create(
                captura_id=trabajo.pk,
                empresa_id=trabajo.empresa_id,
                lead_consolidado_id=estado.lead_consolidado_id,
                autor_id=trabajo.configuracion["autor_id"],
                origen="gemini",
                declaracion=resultado,
                incidencias=[],
                revision_entrada=estado.revision_entrada,
            )
            guardar_historia_ia(trabajo, actual, resultado, captura)
        return "completado"
    except LeasePerdido:
        return "lease_perdido"
    except ErrorExtraccion:
        return _reintentar(trabajo, "respuesta_invalida")
    except ErrorProveedor as error:
        return _reintentar(trabajo, error.categoria)
    except (TimeoutError, ConnectionError):
        return _reintentar(trabajo, "error_transitorio")


def _bloquear_ingestion() -> None:
    """Evita que una carga cambie mensajes entre validación y publicación."""
    if connection.vendor == "postgresql":
        _consultar(
            "SELECT pg_advisory_xact_lock(hashtext("
            "'prueba_ia_05_' || current_schema())) AS bloqueo",
            [],
        )


def _reintentar(trabajo, categoria: str) -> str:
    """Aplica el límite configurado sin exponer excepciones en la cola."""
    try:
        with transaccion_empresa(trabajo.empresa_id):
            return reintentar_trabajo(
                trabajo_id=trabajo.pk,
                lease_token=trabajo.lease_token,
                categoria_error=categoria,
                espera_segundos=int(
                    max(
                        trabajo.configuracion.get("espera_segundos", 30),
                        60 if categoria == "cuota" else 0,
                    )
                ),
                max_intentos=int(
                    1
                    if categoria == "configuracion_proveedor"
                    else trabajo.configuracion.get("max_intentos", 3)
                ),
            )
    except LeasePerdido:
        return "lease_perdido"
