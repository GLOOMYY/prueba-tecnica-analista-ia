"""Cola durable para procesamiento diferido, sin ejecutar IA en el request."""

from datetime import timedelta
from uuid import UUID, uuid4

from django.db import transaction
from django.utils import timezone

from crm.models import EstadoTrabajo, TrabajoProcesamiento


class LeasePerdido(ValueError):
    """El worker dejó de ser propietario del trabajo."""


def bloquear_trabajo(trabajo_id: UUID, lease_token: UUID):
    """Bloquea y valida el lease dentro de la transacción del publicador."""
    trabajo = TrabajoProcesamiento.objects.select_for_update().get(
        trabajo_id=trabajo_id
    )
    if (
        trabajo.estado != EstadoTrabajo.EJECUTANDO
        or trabajo.lease_token != lease_token
        or trabajo.lease_hasta is None
        or trabajo.lease_hasta <= timezone.now()
    ):
        raise LeasePerdido("El lease ya no autoriza este resultado.")
    return trabajo


def encolar_trabajo(
    *,
    empresa_id: str,
    tipo_entidad: str,
    entidad_id: str,
    tipo_trabajo: str,
    revision_entrada: int,
    configuracion: dict,
    huella_entrada: str = "",
) -> tuple[TrabajoProcesamiento, bool]:
    """Crea un trabajo idempotente o devuelve el ya pendiente.

    Args:
        empresa_id: Ámbito de empresa ya autorizado por el llamador.
        tipo_entidad: Tipo de objeto que requiere procesamiento.
        entidad_id: Identificador técnico del objeto.
        tipo_trabajo: Operación diferida, por ejemplo extracción de IA.
        revision_entrada: Foto de entrada que el resultado debe comprobar.
        configuracion: Versiones y opciones no secretas del worker.
        huella_entrada: Huella de la conversación o entrada que se procesará.

    Returns:
        Par del trabajo durable y si fue creado en esta solicitud.

    Raises:
        ValueError: Si falta una clave de alcance o revisión válida.
    """
    _validar_referencia(
        empresa_id,
        tipo_entidad,
        entidad_id,
        tipo_trabajo,
        revision_entrada,
    )
    trabajo, creado = TrabajoProcesamiento.objects.get_or_create(
        empresa_id=empresa_id,
        tipo_entidad=tipo_entidad,
        entidad_id=entidad_id,
        tipo_trabajo=tipo_trabajo,
        revision_entrada=revision_entrada,
        defaults={
            "estado": EstadoTrabajo.PENDIENTE,
            "disponible_en": timezone.now(),
            "configuracion": configuracion,
            "huella_entrada": huella_entrada,
        },
    )
    if not creado and trabajo.huella_entrada != huella_entrada:
        raise ValueError("La entrada cambió sin incrementar su revisión.")
    return trabajo, creado


def reclamar_siguiente(
    *,
    tipo_trabajo: str,
    lease_segundos: int = 300,
    empresa_id: str | None = None,
) -> TrabajoProcesamiento | None:
    """Reclama un único trabajo disponible mediante bloqueo de fila.

    Args:
        tipo_trabajo: Tipo atendido por este worker.
        lease_segundos: Duración positiva del reclamo temporal.
        empresa_id: Empresa del worker; se filtra incluso sin RLS.

    Returns:
        Trabajo reclamado o ``None`` si no hay uno disponible.

    Raises:
        ValueError: Si el tipo o duración del lease no es válido.
    """
    if not tipo_trabajo.strip() or lease_segundos < 1:
        raise ValueError("El tipo de trabajo y lease deben ser válidos.")
    ahora = timezone.now()
    with transaction.atomic():
        recuperar_leases_vencidos(
            ahora=ahora, tipo_trabajo=tipo_trabajo, empresa_id=empresa_id
        )
        filtro = {"empresa_id": empresa_id} if empresa_id else {}
        trabajo = (
            TrabajoProcesamiento.objects.select_for_update(skip_locked=True)
            .filter(
                **filtro,
                tipo_trabajo=tipo_trabajo,
                estado__in=[EstadoTrabajo.PENDIENTE, EstadoTrabajo.REINTENTO],
                disponible_en__lte=ahora,
            )
            .order_by("disponible_en", "creado_en", "trabajo_id")
            .first()
        )
        if trabajo is None:
            return None
        trabajo.estado = EstadoTrabajo.EJECUTANDO
        trabajo.intentos += 1
        trabajo.lease_hasta = ahora + timedelta(seconds=lease_segundos)
        trabajo.lease_token = uuid4()
        trabajo.save(
            update_fields=[
                "estado",
                "intentos",
                "lease_hasta",
                "lease_token",
                "actualizado_en",
            ]
        )
        return trabajo


def recuperar_leases_vencidos(
    *,
    ahora: object | None = None,
    tipo_trabajo: str | None = None,
    empresa_id: str | None = None,
) -> int:
    """Devuelve a reintento trabajos interrumpidos cuyo lease venció.

    El helper se invoca dentro de la transacción de reclamo y no ejecuta
    contenido comercial ni llamadas externas.
    """
    instante = timezone.now() if ahora is None else ahora
    pendientes = TrabajoProcesamiento.objects.filter(
        estado=EstadoTrabajo.EJECUTANDO,
        lease_hasta__lt=instante,
    )
    if tipo_trabajo is not None:
        pendientes = pendientes.filter(tipo_trabajo=tipo_trabajo)
    if empresa_id is not None:
        pendientes = pendientes.filter(empresa_id=empresa_id)
    cantidad = 0
    for trabajo in pendientes.select_for_update(skip_locked=True):
        limite = int(trabajo.configuracion.get("max_intentos", 3))
        trabajo.estado = (
            EstadoTrabajo.FALLIDO
            if trabajo.intentos >= limite
            else EstadoTrabajo.REINTENTO
        )
        trabajo.lease_hasta = None
        trabajo.lease_token = None
        trabajo.disponible_en = instante
        trabajo.ultimo_error = "lease_vencido"
        trabajo.save()
        cantidad += 1
    return cantidad


def completar_trabajo(
    *,
    trabajo_id: UUID,
    lease_token: UUID,
    revision_entrada_actual: int,
) -> bool:
    """Cierra una tarea solo si conserva su lease y revisión de entrada.

    Un worker que terminó tarde no puede publicar un resultado sobre una
    conversación reemplazada ni sobre un lease recuperado por otro worker.

    Args:
        trabajo_id: Trabajo reclamado anteriormente.
        lease_token: Token opaco emitido al reclamar el trabajo.
        revision_entrada_actual: Revisión comprobada por el adaptador antes de
            persistir su resultado.

    Returns:
        ``True`` si el trabajo se cerró. ``False`` si quedó obsoleto.

    Raises:
        ValueError: Si el lease ya no pertenece al worker que intenta cerrar.
    """
    with transaction.atomic():
        trabajo = bloquear_trabajo(trabajo_id, lease_token)
        if trabajo.revision_entrada != revision_entrada_actual:
            trabajo.estado = EstadoTrabajo.OBSOLETO
            trabajo.lease_hasta = None
            trabajo.lease_token = None
            trabajo.save(
                update_fields=[
                    "estado",
                    "lease_hasta",
                    "lease_token",
                    "actualizado_en",
                ]
            )
            return False
        trabajo.estado = EstadoTrabajo.COMPLETADO
        trabajo.lease_hasta = None
        trabajo.lease_token = None
        trabajo.ultimo_error = ""
        trabajo.save(
            update_fields=[
                "estado",
                "lease_hasta",
                "lease_token",
                "ultimo_error",
                "actualizado_en",
            ]
        )
        return True


def reintentar_trabajo(
    *,
    trabajo_id: UUID,
    lease_token: UUID,
    categoria_error: str,
    espera_segundos: int,
    max_intentos: int,
) -> str:
    """Programa un reintento acotado sin guardar texto comercial o técnico.

    Args:
        trabajo_id: Trabajo reclamado por el worker.
        lease_token: Token de su lease actual.
        categoria_error: Código sanitario, por ejemplo ``timeout`` o ``cuota``.
        espera_segundos: Espera antes del siguiente intento.
        max_intentos: Número máximo total de reclamos permitidos.

    Returns:
        Estado final: ``reintento`` o ``fallido``.

    Raises:
        ValueError: Si el lease, límites o categoría son inválidos.
    """
    if (
        espera_segundos < 0
        or max_intentos < 1
        or not categoria_error.isidentifier()
    ):
        raise ValueError("La política de reintento es inválida.")
    with transaction.atomic():
        trabajo = bloquear_trabajo(trabajo_id, lease_token)
        trabajo.lease_hasta = None
        trabajo.lease_token = None
        trabajo.ultimo_error = categoria_error
        if trabajo.intentos >= max_intentos:
            trabajo.estado = EstadoTrabajo.FALLIDO
        else:
            trabajo.estado = EstadoTrabajo.REINTENTO
            trabajo.disponible_en = timezone.now() + timedelta(
                seconds=espera_segundos
            )
        trabajo.save(
            update_fields=[
                "estado",
                "disponible_en",
                "lease_hasta",
                "lease_token",
                "ultimo_error",
                "actualizado_en",
            ]
        )
        return trabajo.estado


def _validar_referencia(
    empresa_id: str,
    tipo_entidad: str,
    entidad_id: str,
    tipo_trabajo: str,
    revision_entrada: int,
) -> None:
    """Valida identificadores mínimos antes de escribir una tarea durable."""
    textos = [empresa_id, tipo_entidad, entidad_id, tipo_trabajo]
    if any(not texto or not texto.strip() for texto in textos):
        raise ValueError(
            "El trabajo requiere empresa, entidad, tipo y referencia."
        )
    if revision_entrada < 1:
        raise ValueError("La revisión de entrada debe ser positiva.")
