"""Lecturas comerciales con permisos comunes para HTML y API."""

from cuentas.models import MembresiaEmpresa, RolMembresia
from django.core.exceptions import PermissionDenied
from django.db.models import Q, QuerySet
from django.utils import timezone

from crm.models import (
    AsignacionDiaria,
    CapturaEstructurada,
    EstadoOperativoLead,
    GestionComercial,
)


def estados_visibles(membresia: MembresiaEmpresa) -> QuerySet:
    """Restringe la lectura a la cartera autorizada antes de agregar datos."""
    if not membresia.activa or membresia.rol not in {
        RolMembresia.ASESOR,
        RolMembresia.SUPERVISOR,
    }:
        raise PermissionDenied("No tiene acceso comercial.")
    estados = EstadoOperativoLead.objects.filter(
        empresa_id=membresia.empresa_id
    )
    if membresia.rol == RolMembresia.ASESOR:
        propias = CapturaEstructurada.objects.filter(
            empresa_id=membresia.empresa_id, autor=membresia.usuario
        ).values("lead_consolidado_id")
        estados = estados.filter(
            Q(asesor_responsable=membresia)
            | Q(
                asesor_responsable__isnull=True,
                lead_consolidado_id__in=propias,
            )
        )
    return estados.order_by("lead_consolidado_id")


def asignaciones_propias(membresia: MembresiaEmpresa) -> QuerySet:
    """Obtiene la cola diaria propia, limitada además a la cartera actual."""
    ids = estados_visibles(membresia).values("lead_consolidado_id")
    return AsignacionDiaria.objects.filter(
        empresa_id=membresia.empresa_id,
        asesor=membresia,
        fecha_operativa=timezone.localdate(),
        lead_consolidado_id__in=ids,
    ).order_by("posicion_inicial")


def indicadores(membresia: MembresiaEmpresa) -> dict:
    """Cuenta actividad del día de Bogotá dentro del mismo ámbito visible."""
    estados = estados_visibles(membresia)
    ids = estados.values("lead_consolidado_id")
    hoy = timezone.localdate()
    gestiones = GestionComercial.objects.filter(
        empresa_id=membresia.empresa_id,
        lead_consolidado_id__in=ids,
        registrada_en__date=hoy,
    )
    return {
        "empresa_id": membresia.empresa_id,
        "fecha_operativa": hoy,
        "leads_activos": estados.filter(estado="abierto").count(),
        "asignados_hoy": AsignacionDiaria.objects.filter(
            empresa_id=membresia.empresa_id,
            fecha_operativa=hoy,
            lead_consolidado_id__in=ids,
        ).count(),
        "gestionados_hoy": gestiones.values("lead_consolidado_id")
        .distinct()
        .count(),
        "intentos_hoy": gestiones.filter(resultado="sin_respuesta").count(),
        "contactos_hoy": gestiones.filter(resultado="contactado").count(),
        "requieren_revision": estados.filter(requiere_revision=True).count(),
        "seguimientos_vencidos": estados.filter(
            estado="abierto", proxima_accion_en__lt=timezone.now()
        ).count(),
    }
