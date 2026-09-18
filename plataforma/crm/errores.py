"""Errores API sin trazas SQL, credenciales ni información de terceros."""

from uuid import uuid4

from django.db import DatabaseError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def manejar_error(error, contexto):
    """Normaliza errores previstos y protege detalles de conexión SQL."""
    if isinstance(error, DatabaseError):
        return Response(
            {
                "code": "persistencia_no_disponible",
                "detail": "Operación no disponible. Intenta más tarde.",
                "request_id": str(uuid4()),
            },
            status=503,
        )
    respuesta = exception_handler(error, contexto)
    if respuesta is not None:
        respuesta.data = {
            "code": getattr(error, "default_code", "error"),
            "errors": respuesta.data,
            "request_id": str(uuid4()),
        }
    return respuesta
