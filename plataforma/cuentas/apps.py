"""Configuración de la aplicación de identidad."""

from django.apps import AppConfig


class CuentasConfig(AppConfig):
    """Configura la aplicación de identidad."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "cuentas"
