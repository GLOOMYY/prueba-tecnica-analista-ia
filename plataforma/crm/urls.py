"""Rutas HTML y REST del CRM."""

from django.urls import path

from crm import api, views
from crm.esquema import EsquemaApi

urlpatterns = [
    path("api/schema/", EsquemaApi.as_view()),
    path("api/docs/", EsquemaApi.as_view()),
    path("", views.tablero, name="tablero"),
    path("nuevo-lead/", views.alta, name="alta"),
    path("empresas/", views.elegir_empresa, name="elegir_empresa"),
    path("leads/<str:lead_id>/", views.detalle, name="detalle"),
    path("mis-leads/", views.mis_leads, name="mis_leads"),
    path("api/v1/me/", api.MeApi.as_view()),
    path("api/v1/asignaciones/generar/", api.AsignacionApi.as_view()),
    path("api/v1/catalogo/modelos/", api.CatalogoApi.as_view()),
    path("api/v1/sedes/", api.SedesApi.as_view()),
    path("api/v1/leads/<str:lead_id>/prioridades/", api.HistoriaApi.as_view()),
    path(
        "api/v1/leads/<str:lead_id>/conversaciones/",
        api.HistoriaApi.as_view(tipo="conversaciones"),
    ),
    path("api/v1/dashboard/", api.DashboardApi.as_view()),
    path("api/v1/mis-leads/", api.MisLeadsApi.as_view()),
    path("api/v1/leads/", api.LeadsApi.as_view()),
    path("api/v1/leads/<str:lead_id>/", api.LeadDetalleApi.as_view()),
    path("api/v1/leads/<str:lead_id>/gestiones/", api.GestionApi.as_view()),
    path(
        "api/v1/leads/<str:lead_id>/responsable/",
        api.ResponsableApi.as_view(),
    ),
]
