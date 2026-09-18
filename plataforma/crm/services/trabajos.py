"""Cola durable para procesamiento diferido, sin ejecutar IA en el request."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from crm.models import EstadoTrabajo, TrabajoProcesamiento


def encolar_trabajo(
    *,
    empresa_id: str,
    tipo_entidad: str,
    entidad_id: str,
    tipo_trabajo: str,
    revision_entrada: int,
    configuracion: dict,
) -> tuple[TrabajoProcesamiento, bool]:
    """Crea un trabajo idempotente o devuelve el ya pendiente.

    Args:
        empresa_id: Ámbito de empresa ya autorizado por el llamador.
        tipo_entidad: Tipo de objeto que requiere procesamiento.
        entidad_id: Identificador técnico del objeto.
        tipo_trabajo: Operación diferida, por ejemplo extracción de IA.
        revision_entrada: Foto de entrada que el resultado debe comprobar.
        configuracion: Versiones y opciones no secretas del worker.

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
    return TrabajoProcesamiento.objects.get_or_create(
        empresa_id=empresa_id,
        tipo_entidad=tipo_entidad,
        entidad_id=entidad_id,
        tipo_trabajo=tipo_trabajo,
        revision_entrada=revision_entrada,
        defaults={
            "estado": EstadoTrabajo.PENDIENTE,
            "disponible_en": timezone.now(),
            "configuracion": configuracion,
        },
    )


def reclamar_siguiente(
    *,
    tipo_trabajo: str,
    lease_segundos: int = 300,
) -> TrabajoProcesamiento | None:
    """Reclama un único trabajo disponible mediante bloqueo de fila.

    Args:
        tipo_trabajo: Tipo atendido por este worker.
        lease_segundos: Duración positiva del reclamo temporal.

    Returns:
        Trabajo reclamado o ``None`` si no hay uno disponible.

    Raises:
        ValueError: Si el tipo o duración del lease no es válido.
    """
    if not tipo_trabajo.strip() or lease_segundos < 1:
        raise ValueError("El tipo de trabajo y lease deben ser válidos.")
    ahora = timezone.now()
    with transaction.atomic():
        recuperar_leases_vencidos(ahora=ahora, tipo_trabajo=tipo_trabajo)
        trabajo = (
            TrabajoProcesamiento.objects.select_for_update(skip_locked=True)
            .filter(
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
        trabajo.save(
            update_fields=[
                "estado",
                "intentos",
                "lease_hasta",
                "actualizado_en",
            ]
        )
        return trabajo


def recuperar_leases_vencidos(
    *,
    ahora: object | None = None,
    tipo_trabajo: str | None = None,
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
    return pendientes.update(
        estado=EstadoTrabajo.REINTENTO,
        lease_hasta=None,
        disponible_en=instante,
    )


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
