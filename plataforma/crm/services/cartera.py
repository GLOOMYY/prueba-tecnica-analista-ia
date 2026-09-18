"""Operaciones de cartera que preservan asignaciones y su auditoría."""

from cuentas.models import MembresiaEmpresa, RolMembresia
from django.core.exceptions import PermissionDenied
from django.db import transaction

from crm.models import EstadoOperativoLead, EventoAuditoria


def transferir_responsable(
    *,
    empresa_id: str,
    lead_consolidado_id: str,
    supervisor: MembresiaEmpresa,
    nuevo_responsable: MembresiaEmpresa,
) -> EstadoOperativoLead:
    """Transfiere una cartera de forma explícita y deja evidencia auditable."""
    if (
        supervisor.empresa_id != empresa_id
        or not supervisor.activa
        or not supervisor.usuario.is_active
        or supervisor.rol != RolMembresia.SUPERVISOR
    ):
        raise PermissionDenied(
            "Solo un supervisor de la empresa puede transferir."
        )
    if (
        nuevo_responsable.empresa_id != empresa_id
        or nuevo_responsable.rol != RolMembresia.ASESOR
        or not nuevo_responsable.activa
        or not nuevo_responsable.usuario.is_active
    ):
        raise PermissionDenied("El responsable no es un asesor activo válido.")
    with transaction.atomic():
        estado = EstadoOperativoLead.objects.select_for_update().get(
            empresa_id=empresa_id,
            lead_consolidado_id=lead_consolidado_id,
        )
        anterior = estado.asesor_responsable_id
        estado.asesor_responsable = nuevo_responsable
        estado.save(update_fields=["asesor_responsable", "actualizado_en"])
        EventoAuditoria.objects.create(
            empresa_id=empresa_id,
            actor=supervisor.usuario,
            accion="transferir_responsable",
            tipo_entidad="lead",
            entidad_id=lead_consolidado_id,
            detalle={
                "responsable_anterior_id": anterior,
                "responsable_nuevo_id": nuevo_responsable.id,
            },
        )
    return estado
