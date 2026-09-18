"""Configuración de la aplicación comercial."""

from django.apps import AppConfig


class CrmConfig(AppConfig):
    """Configura la aplicación comercial."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "crm"
