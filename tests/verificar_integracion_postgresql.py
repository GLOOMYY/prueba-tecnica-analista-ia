"""Comprueba RLS y alta real en un esquema efímero, revertido íntegramente.

Ejecución: python tests/verificar_integracion_postgresql.py
Requiere SUPABASE_DB_URL administrativa en .env. No imprime la URL ni conserva
el rol o el esquema de prueba; todas las operaciones terminan en ROLLBACK.
"""

import os
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parents[1]


def verificar() -> None:
    """Ejecuta migraciones reales y pruebas negativas con un rol sin bypass."""
    valores = {**dotenv_values(RAIZ / ".env"), **os.environ}
    url = valores.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("Falta configurar SUPABASE_DB_URL.")
    sufijo = uuid4().hex[:12]
    esquema, rol = f"verificacion_{sufijo}", f"rol_prueba_{sufijo}"
    os.environ["DJANGO_DATABASE_URL"] = url
    os.environ["DJANGO_DB_SCHEMA"] = esquema
    os.environ["DJANGO_SETTINGS_MODULE"] = "plataforma.settings"
    sys.path[:0] = [str(RAIZ / "plataforma"), str(RAIZ)]
    import django

    django.setup()
    from crm.contexto_empresa import transaccion_empresa
    from crm.historico import _consultar
    from crm.selectores import indicadores
    from crm.services.alta import crear_lead
    from crm.services.extraccion_ia import (
        encolar_extraccion_conversacion,
        procesar_extraccion,
    )
    from crm.services.trabajos import reclamar_siguiente
    from cuentas.models import MembresiaEmpresa
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.db import DatabaseError, connection, transaction

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA "{esquema}"')
            cursor.execute(f'SET LOCAL search_path TO "{esquema}", pg_catalog')
            directorio = RAIZ / "auto-inicio-datos/utils/migrations"
            for archivo in sorted(directorio.glob("[0-9]*.sql")):
                cursor.execute(archivo.read_text(encoding="utf-8"))
            cursor.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = %s",
                [esquema],
            )
            for (tabla,) in cursor.fetchall():
                cursor.execute(
                    f'ALTER TABLE "{tabla}" ENABLE ROW LEVEL SECURITY'
                )
        call_command("migrate", verbosity=0, interactive=False)
        usuario = get_user_model().objects.create_user(username="sintetico")
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO empresas VALUES ('A','A'),('B','B')")
            cursor.execute(
                "INSERT INTO puntos_venta (punto_venta_id,empresa_id) "
                "VALUES ('SA','A'),('SB','B')"
            )
            cursor.execute(f'CREATE ROLE "{rol}" NOLOGIN NOBYPASSRLS')
            cursor.execute("SELECT current_user")
            administrador = cursor.fetchone()[0]
            cursor.execute(f'GRANT "{rol}" TO "{administrador}"')
            permisos = (
                RAIZ / "plataforma/crm/sql/roles_postgresql.sql"
            ).read_text(encoding="utf-8")
            permisos = (
                permisos.replace("plataforma_web", rol)
                .replace("SCHEMA crm", f'SCHEMA "{esquema}"')
                .replace("TO crm, pg_catalog", f'TO "{esquema}", pg_catalog')
            )
            cursor.execute(permisos)
        for empresa in ("A", "B"):
            MembresiaEmpresa.objects.create(
                usuario=usuario, empresa_id=empresa, rol="supervisor"
            )
        with connection.cursor() as cursor:
            cursor.execute(f'SET LOCAL ROLE "{rol}"')
            cursor.execute(
                "SELECT rolbypassrls, rolsuper FROM pg_roles "
                "WHERE rolname = current_user"
            )
            assert cursor.fetchone() == (False, False), "Rol no restringido"
        assert not _consultar("SELECT * FROM leads", [])
        datos = {
            "nombre_cliente": "Cliente sintético",
            "telefono": "3001234567",
            "sede_id": "SA",
        }
        primero, _ = crear_lead(
            usuario=usuario, empresa_id="A", clave="uno", datos=datos
        )
        repetido, codigo = crear_lead(
            usuario=usuario, empresa_id="A", clave="uno", datos=datos
        )
        assert codigo == 200 and primero == repetido
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(
                "INSERT INTO conversaciones (conversacion_id,lead_id_origen,"
                "lead_consolidado_id,empresa_id,descartada,datos_originales) "
                "VALUES ('C1',%s,%s,'A',false,'{}')",
                [primero["consulta_id"], primero["lead_consolidado_id"]],
            )
            cursor.execute(
                "INSERT INTO mensajes VALUES "
                "('M1','C1',1,'cliente',NULL,'Quiero una cita')"
            )
            cursor.execute(f'SET LOCAL ROLE "{rol}"')
        encolar_extraccion_conversacion(
            usuario=usuario, empresa_id="A", conversacion_id="C1"
        )
        with transaccion_empresa("A"):
            trabajo = reclamar_siguiente(
                tipo_trabajo="extraer_ia", empresa_id="A"
            )

        def proveedor(*_):
            from tests.fixtures_ia import respuesta_cita

            return respuesta_cita()

        assert procesar_extraccion(trabajo, proveedor) == "completado"
        with transaccion_empresa("A"):
            assert len(_consultar("SELECT * FROM extracciones_ia", [])) == 1
            prioridad = _consultar("SELECT * FROM v_prioridad_vigente", [])
            assert len(prioridad) == 1
            assert prioridad[0]["temperatura"] == "caliente"
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO ejecuciones (ejecucion_id,empresa_id,etapa,"
                    "version_codigo,huella_entrada,estado,configuracion,"
                    "conteos) VALUES ('LOTE','A','clasificacion_importada',"
                    "'sintetico','sintetico','completada','{}','{}')"
                )
                cursor.execute(
                    "INSERT INTO priorizaciones (priorizacion_id,empresa_id,"
                    "lead_consolidado_id,ejecucion_id,score_prioridad,"
                    "temperatura,cola,explicacion,version_reglas,contexto,"
                    "datos_originales) VALUES ('LOTE-P','A',%s,'LOTE',0,"
                    "'sin_informacion_suficiente','revision_datos',"
                    "'Sintético','v1','{}','{}')",
                    [primero["lead_consolidado_id"]],
                )
            sys.path.insert(0, str(RAIZ / "auto-inicio-datos"))
            from utils.persistencia.db import publicar_prioridades_lote

            publicar_prioridades_lote(connection.connection, "LOTE")
            publicada = _consultar("SELECT * FROM prioridades_publicadas", [])
            assert (
                publicada[0]["priorizacion_id"]
                == prioridad[0]["priorizacion_id"]
            )
            assert publicada[0]["conflicto_lote"] is True
            from crm.services.conflictos_lote import resolver_conflicto

            decision = dict(
                usuario=usuario,
                empresa_id="A",
                lead_id=primero["lead_consolidado_id"],
                propuesta_id="LOTE-P",
                accion="conservar",
                nota="Conservar la declaración vigente comprobada.",
            )
            assert resolver_conflicto(**decision)["repetido"] is False
            assert resolver_conflicto(**decision)["repetido"] is True
            assert not _consultar(
                "SELECT conflicto_lote FROM prioridades_publicadas", []
            )[0]["conflicto_lote"]
            assert not _consultar(
                "SELECT requiere_revision FROM crm_estadooperativolead", []
            )[0]["requiere_revision"]
            miembro = MembresiaEmpresa.objects.get(
                usuario=usuario, empresa_id="A"
            )
            sla = indicadores(miembro)["sla_24h"]
            assert sla["en_plazo"] == 1 and sla["no_medibles"] == 0
            assert len(_consultar("SELECT * FROM leads", [])) == 1
            with transaccion_empresa("B"):
                assert not _consultar("SELECT * FROM leads", [])
            assert len(_consultar("SELECT * FROM leads", [])) == 1
            rechazado = False
            try:
                with transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO leads (lead_consolidado_id,empresa_id,"
                        "reglas_identidad,datos_originales) "
                        "VALUES ('intruso','B','[]','{}')"
                    )
            except DatabaseError:
                rechazado = True
            assert rechazado, "RLS permitió escribir en otra empresa"
        assert not _consultar("SELECT * FROM leads", [])
        transaction.set_rollback(True)
    print("OK: migraciones, alta/reintento, worker y score, RLS y contexto.")
    print("ROLLBACK: no se conservan esquema, rol ni registros sintéticos.")


if __name__ == "__main__":
    verificar()
