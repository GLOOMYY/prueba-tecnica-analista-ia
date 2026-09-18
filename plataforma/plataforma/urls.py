"""Rutas raíz de la plataforma."""

from crm import health
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("healthz/", health.vivo),
    path("readyz/", health.listo),
    path("", include("crm.urls")),
]
