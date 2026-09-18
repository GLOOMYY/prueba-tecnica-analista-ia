"""Esquemas de respuesta públicos para clientes de la API comercial."""

from crm.models import EstadoComercial


def objeto(propiedades: dict) -> dict:
    """Describe campos presentes; los desconocidos se expresan como null."""
    return {
        "type": "object",
        "properties": propiedades,
        "required": list(propiedades),
    }


def pagina(item: dict, *, historia=False) -> dict:
    """Distingue URLs de paginación DRF e índices de páginas históricas."""
    propiedades = {
        "count": {"type": "integer", "minimum": 0},
        "next": {
            "type": "integer" if historia else "string",
            "nullable": True,
        },
        "previous": {
            "type": "integer" if historia else "string",
            "nullable": True,
        },
        "results": {"type": "array", "items": item},
    }
    if historia:
        propiedades["page"] = {"type": "integer", "minimum": 1}
    return objeto(propiedades)


TEXTO = {"type": "string"}
TEXTO_NULO = {"type": "string", "nullable": True}
ENTERO = {"type": "integer", "minimum": 0}
BOOLEANO = {"type": "boolean"}
ESTADO_LEAD = objeto(
    {
        "lead_consolidado_id": TEXTO,
        "estado": {
            "type": "string",
            "enum": list(EstadoComercial.values),
        },
        "requiere_revision": BOOLEANO,
        "revision_entrada": {"type": "integer", "minimum": 1},
        "priorizacion_vigente_id": TEXTO_NULO,
        "proxima_accion_en": {
            "type": "string",
            "format": "date-time",
            "nullable": True,
        },
        "asesor_responsable_id": {"type": "integer", "nullable": True},
    }
)

RESPUESTAS_GET = {
    "me/": objeto(
        {
            "usuario": TEXTO,
            "membresias": {
                "type": "array",
                "items": objeto(
                    {
                        "empresa_id": TEXTO,
                        "rol": TEXTO,
                        "asesor_id": TEXTO,
                    }
                ),
            },
        }
    ),
    "leads/": pagina(ESTADO_LEAD),
    "leads/{id}/": ESTADO_LEAD,
    "mis-leads/": pagina(
        objeto(
            {
                "lead_consolidado_id": TEXTO,
                "posicion_inicial": ENTERO,
                "estado": TEXTO,
                "motivo": TEXTO,
            }
        )
    ),
    "leads/{id}/prioridades/": pagina(
        objeto(
            {
                "priorizacion_id": TEXTO,
                "score_prioridad": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                },
                "temperatura": TEXTO,
                "cola": TEXTO,
                "explicacion": TEXTO,
                "accion_sugerida": TEXTO_NULO,
                "version_reglas": TEXTO,
            }
        ),
        historia=True,
    ),
    "leads/{id}/conversaciones/": pagina(
        objeto(
            {
                "conversacion_id": TEXTO,
                "canal": TEXTO_NULO,
                "fecha_inicio": {
                    "type": "string",
                    "format": "date",
                    "nullable": True,
                },
                "descartada": BOOLEANO,
                "motivos_descarte": {"type": "array", "items": {}},
            }
        ),
        historia=True,
    ),
    "sedes/": objeto(
        {
            "results": {
                "type": "array",
                "items": objeto(
                    {
                        "punto_venta_id": TEXTO,
                        "nombre": TEXTO_NULO,
                        "ubicacion": TEXTO_NULO,
                    }
                ),
            }
        }
    ),
    "catalogo/modelos/": objeto(
        {
            "results": {
                "type": "array",
                "items": objeto(
                    {
                        "sku": TEXTO,
                        "marca": TEXTO,
                        "linea": TEXTO,
                        "cilindraje": {"type": "number", "nullable": True},
                        "precio_lista": {"type": "number", "nullable": True},
                        "unidades_disponibles": {
                            "type": "integer",
                            "nullable": True,
                        },
                    }
                ),
            }
        }
    ),
    "dashboard/": objeto(
        {
            "empresa_id": TEXTO,
            "fecha_operativa": {"type": "string", "format": "date"},
            **{
                n: ENTERO
                for n in (
                    "leads_activos",
                    "asignados_hoy",
                    "gestionados_hoy",
                    "intentos_hoy",
                    "contactos_hoy",
                    "requieren_revision",
                    "seguimientos_vencidos",
                )
            },
            "sla_24h": {
                "type": "object",
                "properties": {
                    "disponible": BOOLEANO,
                    "criterio": TEXTO,
                    **{
                        n: ENTERO
                        for n in (
                            "cumplen",
                            "vencidos",
                            "en_plazo",
                            "no_medibles",
                        )
                    },
                },
            },
        }
    ),
}

REVISION = objeto({"revision_id": TEXTO, "estado": TEXTO})
ALTA = objeto(
    {
        "lead_consolidado_id": TEXTO,
        "consulta_id": TEXTO,
        "lead_creado": BOOLEANO,
        "revision_entrada": ENTERO,
        "prioridad": objeto(
            {
                "puntos": ENTERO,
                "score": {
                    "type": "string",
                    "description": "Decimal, ejemplo 44.44",
                },
                "temperatura": TEXTO,
                "contribuciones": {
                    "type": "array",
                    "items": objeto(
                        {
                            "senal": TEXTO,
                            "puntos": ENTERO,
                            "explicacion": TEXTO,
                        }
                    ),
                },
            }
        ),
        "incidencias": {"type": "array", "items": TEXTO},
        "asignacion": objeto({"estado": TEXTO}),
    }
)
RESPUESTAS_POST = {
    "leads/": {"oneOf": [ALTA, REVISION]},
    "leads/{id}/gestiones/": objeto({"gestion_id": TEXTO, "estado": TEXTO}),
    "revisiones/{id}/resolver/": objeto(
        {
            "revision_id": TEXTO,
            "estado": TEXTO,
            "lead_consolidado_id": TEXTO_NULO,
        }
    ),
    "leads/{id}/responsable/": objeto({"estado": ESTADO_LEAD}),
    "asignaciones/generar/": objeto(
        {
            "fecha": {"type": "string", "format": "date"},
            "creadas": ENTERO,
            "pendientes_por_motivo": {
                "type": "object",
                "additionalProperties": ENTERO,
            },
        }
    ),
    "conversaciones/{id}/extraer/": objeto(
        {"trabajo_id": TEXTO, "estado": TEXTO}
    ),
}
