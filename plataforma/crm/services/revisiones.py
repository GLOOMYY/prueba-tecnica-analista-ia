"""Resolución supervisada e idempotente de capturas ambiguas."""

import json

from cuentas.acceso import alcance_empresa
from cuentas.models import RolMembresia
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from crm.forms import AltaForm
from crm.historico import _consultar
from crm.models import (
    CapturaRevision,
    EstadoCapturaRevision,
    EstadoOperativoLead,
    EventoAuditoria,
)
from crm.services.alta import _persistir
from dominio.alta import EntradaAlta, preparar_alta

ACCIONES = ("vincular", "rechazar", "crear_distinto")


def resolver_revision(
    *,
    usuario,
    empresa_id: str,
    revision_id: str,
    accion: str,
    nota: str = "",
    lead_id: str = "",
) -> tuple[dict, bool]:
    """Resuelve una captura pendiente sin fusionar ni inventar identidades.

    ``vincular`` requiere un lead operativo de la misma empresa. ``rechazar``
    conserva la captura y su motivo fuera de la cartera activa. La creación de
    una identidad distinta sigue el flujo de alta, que debe aportar contacto y
    sede verificables; nunca se crea por inferencia desde una ambigüedad.

    Args:
        usuario: Supervisor autenticado que resuelve la captura.
        empresa_id: Empresa autorizada para la operación.
        revision_id: Identificador de la captura pendiente.
        accion: ``vincular`` o ``rechazar``.
        nota: Motivo trazable, sin contenido de conversaciones completas.
        lead_id: Lead de la misma empresa, obligatorio al vincular.

    Returns:
        Resumen de la decisión y si ya estaba resuelta de igual manera.

    Raises:
        PermissionDenied: Si el usuario no es supervisor de la empresa.
        ValueError: Si la decisión es incompleta o contradice una previa.
    """
    if accion not in ACCIONES or len(nota) > 500:
        raise ValueError("La decisión de revisión es inválida.")
    if accion == "vincular" and not lead_id.strip():
        raise ValueError("Indique el lead al que se vinculará la captura.")
    if accion in ("rechazar", "crear_distinto") and not nota.strip():
        raise ValueError("Indique el motivo de la decisión.")
    if accion != "vincular" and lead_id:
        raise ValueError("Solo vincular admite un lead de destino.")
    decision = _resolucion(accion, nota, lead_id)
    with alcance_empresa(usuario, empresa_id) as miembro:
        if miembro.rol != RolMembresia.SUPERVISOR:
            raise PermissionDenied(
                "Solo un supervisor puede resolver revisiones."
            )
        with transaction.atomic():
            if connection.vendor == "postgresql":
                _consultar(
                    "SELECT pg_advisory_xact_lock(hashtext("
                    "'prueba_ia_05_' || current_schema())) AS bloqueo",
                    [],
                )
            revision = get_object_or_404(
                CapturaRevision.objects.select_for_update(),
                revision_id=revision_id,
                empresa_id=miembro.empresa_id,
            )
            if revision.estado != EstadoCapturaRevision.PENDIENTE:
                respuesta = _respuesta(revision)
                if revision.resolucion != decision:
                    raise ValueError(
                        "La revisión ya tiene una decisión distinta."
                    )
                return respuesta, True
            if accion in ("vincular", "crear_distinto"):
                lead_id = _persistir_decision(miembro, revision, lead_id)
                estado_revision = EstadoCapturaRevision.RESUELTA
            else:
                lead_id = ""
                estado_revision = EstadoCapturaRevision.RECHAZADA
            revision.estado = estado_revision
            revision.resolutor = usuario
            revision.resolucion = decision
            revision.lead_consolidado_id_resuelto = lead_id
            revision.resuelta_en = timezone.now()
            revision.save(
                update_fields=[
                    "estado",
                    "resolutor",
                    "resolucion",
                    "lead_consolidado_id_resuelto",
                    "resuelta_en",
                    "actualizado_en",
                ]
            )
            EventoAuditoria.objects.create(
                empresa_id=miembro.empresa_id,
                actor=usuario,
                accion="resolver_captura_revision",
                tipo_entidad="captura_revision",
                entidad_id=str(revision.pk),
                detalle={
                    "accion": accion,
                    "lead_id": lead_id or None,
                    "nota": nota.strip(),
                },
            )
            return _respuesta(revision), False


def _resolucion(accion: str, nota: str, lead_id: str) -> str:
    """Genera la representación estable usada para comprobar reintentos."""
    import hashlib

    entrada = json.dumps([accion, lead_id.strip(), nota.strip()])
    return hashlib.sha256(entrada.encode()).hexdigest()


def _persistir_decision(miembro, revision, lead_id: str) -> str:
    """Revalida y guarda consulta y score en una transacción."""
    formulario = AltaForm({**revision.datos_propuestos, "clave": "revision"})
    if not formulario.is_valid():
        raise ValueError("Corrija los datos obligatorios de la captura.")
    datos = formulario.cleaned_data.copy()
    datos.pop("clave")
    if not _consultar(
        "SELECT punto_venta_id FROM puntos_venta "
        "WHERE empresa_id = %s AND punto_venta_id = %s",
        [miembro.empresa_id, datos["sede_id"]],
    ):
        raise ValueError("La sede no pertenece a esta empresa.")
    sku = datos.get("modelo_sku") or None
    if sku and not _consultar(
        "SELECT sku FROM modelos_moto WHERE sku = %s", [sku]
    ):
        raise ValueError("El SKU ya no existe en el catálogo.")
    if lead_id:
        get_object_or_404(
            EstadoOperativoLead.objects.select_for_update(),
            empresa_id=miembro.empresa_id,
            lead_consolidado_id=lead_id,
        )
    preparada = preparar_alta(
        EntradaAlta(
            empresa_id=miembro.empresa_id,
            nombre_cliente=datos["nombre_cliente"],
            telefono=datos["telefono"],
            correo=datos["correo"],
            modelo_sku=sku,
            cuota_inicial=datos["cuota_inicial"],
            forma_pago=datos["forma_pago"],
            cliente_pidio_cita=datos["cliente_pidio_cita"] is True,
        )
    )
    respuesta = _persistir(
        miembro,
        preparada,
        datos,
        revision.datos_propuestos,
        [{"lead_consolidado_id": lead_id}] if lead_id else [],
        autor=revision.solicitante,
        origen="revision_supervisada",
    )
    return respuesta["lead_consolidado_id"]


def _respuesta(revision: CapturaRevision) -> dict:
    """Expone una decisión sin copiar los datos sensibles de la captura."""
    return {
        "revision_id": str(revision.pk),
        "estado": revision.estado,
        "lead_consolidado_id": revision.lead_consolidado_id_resuelto or None,
    }
