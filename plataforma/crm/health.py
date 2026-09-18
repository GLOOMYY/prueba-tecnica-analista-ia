"""Endpoints sin datos comerciales para supervisión de disponibilidad."""

from django.db import connection
from django.http import JsonResponse


def vivo(request):
    """Confirma que el proceso HTTP responde sin información comercial."""
    return JsonResponse({"status": "ok"})


def listo(request):
    """Confirma que la conexión configurada a base de datos está disponible."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "not_ready"}, status=503)
    return JsonResponse({"status": "ready"})
