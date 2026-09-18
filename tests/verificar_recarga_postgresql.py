"""Prueba una recarga completa en un esquema temporal, sin tocar el comercial.

Uso: python tests/verificar_recarga_postgresql.py --trabajo <instantánea>
La instantánea debe ser una ejecución propia terminada con --sin-api --sin-db.
"""

import argparse
import copy
import os
import sys
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[1]


def verificar(trabajo: Path) -> None:
    """Carga, captura, gestiona, concilia una nueva fuente y repite lotes."""
    sys.path[:0] = [
        str(RAIZ),
        str(RAIZ / "auto-inicio-datos"),
        str(RAIZ / "plataforma"),
    ]
    from utils.persistencia.config import Configuracion
    from utils.persistencia.db import cargar_lote, conectar, crear_esquema
    from utils.persistencia.plan import preparar_lote

    esquema = "recarga_" + uuid4().hex
    config = replace(Configuracion.leer(), schema=esquema)
    os.environ.update(
        DJANGO_DATABASE_URL=config.url,
        DJANGO_DB_SCHEMA=esquema,
        DJANGO_SETTINGS_MODULE="plataforma.settings",
    )
    import django

    django.setup()
    from crm.contexto_empresa import transaccion_empresa
    from crm.models import EstadoOperativoLead, GestionComercial
    from crm.services.alta import crear_lead
    from crm.services.gestion import registrar_gestion
    from cuentas.models import MembresiaEmpresa, Usuario
    from django.core.management import call_command
    from django.db import connection

    creado = False
    try:
        crear_esquema(config)
        creado = True
        call_command("migrate", verbosity=0, interactive=False)
        lote = preparar_lote(trabajo)
        cargar_lote(config, lote)
        empresa = lote.filas["empresas"][0]["empresa_id"]
        sede = next(
            s["punto_venta_id"]
            for s in lote.filas["puntos_venta"]
            if s["empresa_id"] == empresa
        )
        usuario = Usuario.objects.create_user(username="recarga_sintetica")
        MembresiaEmpresa.objects.create(
            usuario=usuario, empresa_id=empresa, rol="supervisor"
        )
        datos = {
            "nombre_cliente": "Persona Sintética Recarga",
            "telefono": "3000000001",
            "sede_id": sede,
            "cliente_pidio_cita": True,
        }
        respuesta, codigo = crear_lead(
            usuario=usuario, empresa_id=empresa, clave="nueva", datos=datos
        )
        assert codigo == 201
        lead = respuesta["lead_consolidado_id"]
        registrar_gestion(
            usuario=usuario,
            empresa_id=empresa,
            lead_id=lead,
            clave="contacto",
            resultado="contactado",
            nota="Prueba sintética",
        )
        assert cargar_lote(config, preparar_lote(trabajo))["estado"] == (
            "ya_cargado_y_verificado"
        )
        nuevo = preparar_lote(trabajo)
        nuevo.ejecucion_id += "-sintetico"
        etapa_anterior = nuevo.etapas["clasificacion"]
        nuevo.etapas["clasificacion"] = "CLASIFICACION-SINTETICA"
        for ejecucion in nuevo.filas["ejecuciones"]:
            if ejecucion["ejecucion_id"] == etapa_anterior:
                ejecucion["ejecucion_id"] = nuevo.etapas["clasificacion"]
        for prioridad in nuevo.filas["priorizaciones"]:
            prioridad["priorizacion_id"] += "-sintetico"
            prioridad["ejecucion_id"] = nuevo.etapas["clasificacion"]
        fila = copy.deepcopy(nuevo.filas["leads"][0])
        fila.update(
            lead_consolidado_id="FUENTE-NUEVA",
            empresa_id=empresa,
            nombre_presentacion=datos["nombre_cliente"],
        )
        nuevo.filas["leads"].append(fila)
        consulta = copy.deepcopy(nuevo.filas["consultas"][0])
        consulta.update(
            lead_id_origen="CONSULTA-NUEVA",
            empresa_id=empresa,
            lead_consolidado_id="FUENTE-NUEVA",
            punto_venta_id=sede,
            telefono="+573000000001",
            nombre_declarado=datos["nombre_cliente"],
        )
        nuevo.filas["consultas"].append(consulta)
        prioridad = copy.deepcopy(nuevo.filas["priorizaciones"][0])
        prioridad.update(
            priorizacion_id="PRIORIDAD-NUEVA",
            empresa_id=empresa,
            lead_consolidado_id="FUENTE-NUEVA",
            lead_id_contexto="CONSULTA-NUEVA",
            conversacion_id_contexto=None,
        )
        nuevo.filas["priorizaciones"].append(prioridad)
        with transaccion_empresa(empresa):
            vigente = EstadoOperativoLead.objects.get(
                empresa_id=empresa, lead_consolidado_id=lead
            ).priorizacion_vigente_id
        cargar_lote(config, nuevo)
        # Una foto anterior ya aceptada tampoco puede revertir la nueva.
        cargar_lote(config, preparar_lote(trabajo))
        with transaccion_empresa(empresa):
            assert (
                GestionComercial.objects.filter(
                    lead_consolidado_id=lead
                ).count()
                == 1
            )
            assert (
                EstadoOperativoLead.objects.get(
                    empresa_id=empresa, lead_consolidado_id=lead
                ).priorizacion_vigente_id
                == vigente
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT lead_consolidado_id FROM consultas "
                    "WHERE lead_id_origen='CONSULTA-NUEVA'"
                )
                assert cursor.fetchone()[0] == lead
                cursor.execute(
                    "SELECT count(*) FROM leads "
                    "WHERE lead_consolidado_id='FUENTE-NUEVA'"
                )
                assert cursor.fetchone()[0] == 0
        print(
            "OK: carga completa, alta, gestión, alias y recargas idempotentes."
        )
    finally:
        connection.close()
        if creado:
            assert esquema.startswith("recarga_") and len(esquema) == 40
            from psycopg import sql

            with conectar(config) as conn:
                conn.execute(
                    sql.SQL("DROP SCHEMA {} CASCADE").format(
                        sql.Identifier(esquema)
                    )
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trabajo", type=Path, required=True)
    verificar(parser.parse_args().trabajo)
