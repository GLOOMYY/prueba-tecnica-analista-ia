"""Contrato OpenAPI de los endpoints comerciales implementados."""

from django import forms
from rest_framework.response import Response
from rest_framework.views import APIView

from crm.esquema_respuestas import RESPUESTAS_GET, RESPUESTAS_POST, REVISION
from crm.filtros import FiltrosLeadForm
from crm.forms import AltaForm, BooleanoDeclarado, GestionForm, RevisionForm


def _cuerpo(formulario):
    """Describe tipos y campos requeridos desde el validador compartido."""
    propiedades, obligatorios = {}, []
    for nombre, campo in formulario.base_fields.items():
        if nombre == "clave":
            continue
        tipo = "string"
        if isinstance(campo, (forms.BooleanField, BooleanoDeclarado)):
            tipo = "boolean"
        propiedades[nombre] = {"type": tipo}
        if isinstance(campo, BooleanoDeclarado):
            propiedades[nombre]["nullable"] = True
        if isinstance(campo, forms.DecimalField):
            propiedades[nombre].update(type="number", minimum=0, nullable=True)
        if isinstance(campo, forms.ChoiceField):
            propiedades[nombre]["enum"] = [valor for valor, _ in campo.choices]
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
            if ruta == "leads/":
                parametros.extend(
                    {
                        "in": "query",
                        "name": nombre,
                        "required": False,
                        "schema": esquema,
                    }
                    for nombre, esquema in _cuerpo(FiltrosLeadForm)[
                        "properties"
                    ].items()
                )
            if ruta in (
                "leads/",
                "mis-leads/",
                "leads/{id}/prioridades/",
                "leads/{id}/conversaciones/",
            ):
                parametros.append(
                    {
                        "in": "query",
                        "name": "page",
                        "required": False,
                        "schema": {"type": "integer", "minimum": 1},
                    }
                )
            rutas["/api/v1/" + ruta] = {
                "get": {
                    "parameters": parametros,
                    "responses": {
                        "200": {
                            "description": "Resultado autorizado",
                            "content": {
                                "application/json": {
                                    "schema": RESPUESTAS_GET[ruta]
                                }
                            },
                        },
                        "401": {"description": "Autenticación requerida"},
                        "403": {"description": "Sin permiso"},
                        "404": {"description": "No encontrado"},
                    },
                }
            }
        for ruta, formulario in [
            ("leads/", AltaForm),
            ("leads/{id}/gestiones/", GestionForm),
            ("revisiones/{id}/resolver/", RevisionForm),
        ]:
            parametros = [
                {
                    "in": "header",
                    "name": nombre,
                    "required": True,
                    "schema": {"type": "string"},
                }
                for nombre in ["X-Empresa-ID"]
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
            if formulario in {AltaForm, GestionForm}:
                parametros.append(
                    {
                        "in": "header",
                        "name": "Idempotency-Key",
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
        rutas["/api/v1/asignaciones/generar/"] = {
            "post": _post_simple({}, "Genera asignaciones dentro de cupos.")
        }
        rutas["/api/v1/leads/{id}/responsable/"] = {
            "post": _post_simple(
                {
                    "membresia_responsable_id": {
                        "type": "integer",
                        "minimum": 1,
                    }
                },
                "Transfiere una cartera por supervisor autorizado.",
                requiere_id=True,
            )
        }
        rutas["/api/v1/conversaciones/{id}/extraer/"] = {
            "post": _post_simple(
                {},
                "Encola una extracción individual autorizada.",
                requiere_id=True,
            )
        }
        for ruta, metodos in rutas.items():
            if "post" not in metodos:
                continue
            for codigo, respuesta in metodos["post"]["responses"].items():
                if codigo.startswith("2"):
                    esquema = RESPUESTAS_POST[ruta.removeprefix("/api/v1/")]
                else:
                    esquema = {
                        "type": "object",
                        "properties": {
                            "detail": {"type": "string"},
                            "errors": {"type": "object"},
                        },
                    }
                    if ruta == "/api/v1/leads/" and codigo == "409":
                        esquema = {"oneOf": [esquema, REVISION]}
                respuesta["content"] = {
                    "application/json": {"schema": esquema}
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


def _post_simple(
    propiedades: dict,
    descripcion: str,
    *,
    requiere_id: bool = False,
) -> dict:
    """Describe un POST autenticado no basado en un formulario Django."""
    parametros = [
        {
            "in": "header",
            "name": "X-Empresa-ID",
            "required": True,
            "schema": {"type": "string"},
        }
    ]
    if requiere_id:
        parametros.append(
            {
                "in": "path",
                "name": "id",
                "required": True,
                "schema": {"type": "string"},
            }
        )
    return {
        "parameters": parametros,
        "requestBody": {
            "required": bool(propiedades),
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": propiedades,
                        "required": list(propiedades),
                        "additionalProperties": False,
                    }
                }
            },
        },
        "responses": {
            "200": {"description": descripcion},
            "201": {"description": descripcion},
            "400": {"description": "Entrada inválida"},
            "403": {"description": "Sin permiso"},
            "404": {"description": "No encontrado"},
        },
    }
