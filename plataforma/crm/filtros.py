"""Filtros comerciales compartidos por tablero y API."""

from django import forms
from django.utils import timezone

from crm.historico import _consultar
from crm.models import EstadoComercial
from crm.selectores import estados_visibles


class FiltrosLeadForm(forms.Form):
    """Restringe filtros a valores conocidos y mantiene alcance autorizado."""

    estado = forms.ChoiceField(
        required=False, choices=[("", "Todos"), *EstadoComercial.choices]
    )
    temperatura = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Todas"),
            ("caliente", "Caliente"),
            ("tibio", "Tibio"),
            ("sin_informacion_suficiente", "Sin información suficiente"),
        ],
    )
    sede = forms.CharField(required=False, max_length=100, label="Código sede")
    seguimiento = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Todos"),
            ("vencido", "Vencidos"),
            ("futuro", "Programados"),
        ],
    )
    revision = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Todos"),
            ("si", "Requiere revisión"),
            ("no", "Sin revisión"),
        ],
    )


def filtrar_estados(miembro, formulario):
    """Filtra el conjunto autorizado y conserva un orden estable."""
    filas = estados_visibles(miembro)
    datos = formulario.cleaned_data
    if datos["estado"]:
        filas = filas.filter(estado=datos["estado"])
    if datos["revision"]:
        filas = filas.filter(requiere_revision=datos["revision"] == "si")
    if datos["seguimiento"] == "vencido":
        filas = filas.filter(proxima_accion_en__lte=timezone.now())
    elif datos["seguimiento"] == "futuro":
        filas = filas.filter(proxima_accion_en__gt=timezone.now())
    if datos["temperatura"] or datos["sede"]:
        ids = _consultar(
            "SELECT p.lead_consolidado_id FROM v_prioridad_vigente p "
            "LEFT JOIN consultas c ON c.lead_id_origen = p.lead_id_contexto "
            "AND c.empresa_id = p.empresa_id "
            "WHERE p.empresa_id = %s AND (%s = '' OR p.temperatura = %s) "
            "AND (%s = '' OR c.punto_venta_id = %s)",
            [
                miembro.empresa_id,
                datos["temperatura"],
                datos["temperatura"],
                datos["sede"],
                datos["sede"],
            ],
        )
        filas = filas.filter(
            lead_consolidado_id__in=[r["lead_consolidado_id"] for r in ids]
        )
    return filas
