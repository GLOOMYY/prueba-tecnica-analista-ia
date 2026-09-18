"""Contrato OpenAPI de los endpoints comerciales implementados."""

from django import forms
from rest_framework.response import Response
from rest_framework.views import APIView

from crm.forms import AltaForm, GestionForm


def _cuerpo(formulario):
    """Describe tipos y campos requeridos desde el validador compartido."""
    propiedades, obligatorios = {}, []
    for nombre, campo in formulario.base_fields.items():
        if nombre == "clave":
            continue
        tipo = "string"
        if isinstance(campo, (forms.BooleanField, forms.NullBooleanField)):
            tipo = "boolean"
        propiedades[nombre] = {"type": tipo}
        if isinstance(campo, forms.NullBooleanField):
            propiedades[nombre]["nullable"] = True
        if isinstance(campo, forms.DateTimeField):
            propiedades[nombre]["format"] = "date-time"
        if campo.required:
            obligatorios.append(nombre)
    return {
        "type": "object",
        "properties": propiedades,
        "required": obligatorios,
        "additionalProperties": False,
    }


class EsquemaApi(APIView):
    """Publica un esquema autenticado sin datos personales ni tokens."""

    def get(self, request):
        """Enumera rutas reales y contratos de escritura compartidos."""
        rutas = {}
        for ruta in [
            "me/",
            "dashboard/",
            "mis-leads/",
            "leads/",
            "leads/{id}/",
            "leads/{id}/prioridades/",
            "leads/{id}/conversaciones/",
            "catalogo/modelos/",
            "sedes/",
        ]:
            parametros = []
            if ruta != "me/":
                parametros.append(
                    {
                        "in": "header",
                        "name": "X-Empresa-ID",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                )
            if "{id}" in ruta:
                parametros.append(
                    {
                        "in": "path",
                        "name": "id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                )
            rutas["/api/v1/" + ruta] = {
                "get": {
                    "parameters": parametros,
                    "responses": {
                        "200": {"description": "Resultado autorizado"},
                        "403": {"description": "Sin permiso"},
                        "404": {"description": "No encontrado"},
                    },
                }
            }
        for ruta, formulario in [
            ("leads/", AltaForm),
            ("leads/{id}/gestiones/", GestionForm),
        ]:
            parametros = [
                {
                    "in": "header",
                    "name": nombre,
                    "required": True,
                    "schema": {"type": "string"},
                }
                for nombre in ["X-Empresa-ID", "Idempotency-Key"]
            ]
            if "{id}" in ruta:
                parametros.append(
                    {
                        "in": "path",
                        "name": "id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                )
            rutas.setdefault("/api/v1/" + ruta, {})["post"] = {
                "parameters": parametros,
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {"schema": _cuerpo(formulario)}
                    },
                },
                "responses": {
                    str(c): {"description": texto}
                    for c, texto in [
                        (200, "Reintento"),
                        (201, "Guardado"),
                        (202, "En revisión"),
                        (400, "Entrada inválida"),
                        (409, "Conflicto"),
                        (503, "Persistencia no disponible"),
                    ]
                },
            }
        return Response(
            {
                "openapi": "3.0.3",
                "info": {"title": "CRM", "version": "1.0"},
                "paths": rutas,
                "security": [{"Token": []}, {"Session": []}],
                "components": {
                    "securitySchemes": {
                        "Token": {
                            "type": "apiKey",
                            "in": "header",
                            "name": "Authorization",
                            "description": "Token <credencial>",
                        },
                        "Session": {
                            "type": "apiKey",
                            "in": "cookie",
                            "name": "sessionid",
                        },
                    }
                },
            }
        )
