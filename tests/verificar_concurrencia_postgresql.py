"""Prueba sesiones simultáneas en un esquema exclusivo y elimina sus fixtures.

Solo se borran el esquema y rol aleatorios creados por esta ejecución. No se
modifica el esquema configurado del proyecto ni se llama a Gemini.
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parents[1]


def verificar() -> None:
    """Comprueba identidad, aislamiento y reclamación con conexiones reales."""
    valores = {**dotenv_values(RAIZ / ".env"), **os.environ}
    sufijo = uuid4().hex
    esquema, rol = f"carrera_{sufijo}", f"rol_{sufijo}"
    os.environ["DJANGO_DATABASE_URL"] = valores["SUPABASE_DB_URL"]
    os.environ["DJANGO_DB_SCHEMA"] = esquema
    os.environ["DJANGO_SETTINGS_MODULE"] = "plataforma.settings"
    sys.path[:0] = [str(RAIZ / "plataforma"), str(RAIZ)]
    import django

    django.setup()
    from crm.contexto_empresa import transaccion_empresa
    from crm.models import (
        AsignacionDiaria,
        EstadoOperativoLead,
        GestionComercial,
        TrabajoProcesamiento,
    )
    from crm.services.alta import crear_lead
    from crm.services.asignacion import generar_asignaciones
    from crm.services.cartera import transferir_responsable
    from crm.services.gestion import registrar_gestion
    from crm.services.trabajos import encolar_trabajo, reclamar_siguiente
    from cuentas.models import MembresiaEmpresa, Usuario
    from django.core.management import call_command
    from django.db import connection, connections
    from django.test import override_settings
    from rest_framework.test import APIClient

    creado = False
    try:
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA "{esquema}"')
            creado = True
            cursor.execute(f'SET search_path TO "{esquema}", pg_catalog')
            for archivo in sorted(
                (RAIZ / "auto-inicio-datos/utils/migrations").glob(
                    "[0-9]*.sql"
                )
            ):
                cursor.execute(archivo.read_text(encoding="utf-8"))
        call_command("migrate", verbosity=0, interactive=False)
        usuarios = {}
        with connection.cursor() as cursor:
            for empresa in ("A", "B", "C"):
                cursor.execute(
                    "INSERT INTO empresas VALUES (%s,%s)", [empresa, empresa]
                )
                cursor.execute(
                    "INSERT INTO puntos_venta(punto_venta_id,empresa_id) "
                    "VALUES (%s,%s)",
                    ["S" + empresa, empresa],
                )
                usuarios[empresa] = Usuario.objects.create_user(
                    username="supervisor_" + empresa
                )
                MembresiaEmpresa.objects.create(
                    usuario=usuarios[empresa],
                    empresa_id=empresa,
                    rol="supervisor",
                )
            cursor.execute(
                "INSERT INTO asesores(asesor_id,empresa_id,punto_venta_id,"
                "nombre,"
                "activo,capacidad_diaria_leads,datos_originales) "
                "VALUES ('AS1','A','SA','Asesor sintético',true,1,'{}'),"
                "('AS2','A','SA','Segundo asesor',true,1,'{}')"
            )
            asesor = Usuario.objects.create_user(username="asesor_A")
            MembresiaEmpresa.objects.create(
                usuario=asesor, empresa_id="A", rol="asesor", asesor_id="AS1"
            )
            segundo_asesor = Usuario.objects.create_user(username="asesor_dos")
            asesor_destino = MembresiaEmpresa.objects.create(
                usuario=segundo_asesor,
                empresa_id="A",
                rol="asesor",
                asesor_id="AS2",
            )
            restringidos = []
            for empresa in usuarios:
                for nombre, perfil, activa in (
                    ("sin_cartera", "asesor", True),
                    ("tecnico", "operador", True),
                    ("revocado", "supervisor", False),
                ):
                    u = Usuario.objects.create_user(username=nombre + empresa)
                    MembresiaEmpresa.objects.create(
                        usuario=u,
                        empresa_id=empresa,
                        rol=perfil,
                        activa=activa,
                    )
                    restringidos.append((u, perfil, activa, empresa))
            cursor.execute(f'CREATE ROLE "{rol}" NOLOGIN NOBYPASSRLS')
            cursor.execute("SELECT current_user")
            administrador = cursor.fetchone()[0]
            cursor.execute(f'GRANT "{rol}" TO "{administrador}"')
            permisos = RAIZ / "plataforma/crm/sql/roles_postgresql.sql"
            cursor.execute(
                permisos.read_text(encoding="utf-8")
                .replace("plataforma_web", rol)
                .replace("SCHEMA crm", f'SCHEMA "{esquema}"')
                .replace("TO crm, pg_catalog", f'TO "{esquema}", pg_catalog')
            )
            cursor.execute(f'SET ROLE "{rol}"')

        barrera = Barrier(2)

        def alta_paralela(numero):
            """Abre una sesión independiente y compite por la misma alta."""
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'SET ROLE "{rol}"')
                barrera.wait(timeout=30)
                return crear_lead(
                    usuario=usuarios["A"],
                    empresa_id="A",
                    clave=f"misma-alta-{numero}",
                    datos={
                        "nombre_cliente": "Cliente sintético",
                        "telefono": "3001234567",
                        "sede_id": "SA",
                    },
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            respuestas = list(pool.map(alta_paralela, range(2)))
        assert sorted(r[1] for r in respuestas) == [201, 201]
        lead_a = respuestas[0][0]["lead_consolidado_id"]
        assert respuestas[1][0]["lead_consolidado_id"] == lead_a
        for empresa in ("B", "C"):
            respuesta, _ = crear_lead(
                usuario=usuarios[empresa],
                empresa_id=empresa,
                clave="alta",
                datos={
                    "nombre_cliente": "Cliente sintético",
                    "telefono": "3001234567",
                    "sede_id": "S" + empresa,
                },
            )
            assert respuesta["lead_consolidado_id"] != lead_a

        with override_settings(ALLOWED_HOSTS=["testserver"]):
            for empresa, usuario in usuarios.items():
                cliente = APIClient()
                cliente.force_authenticate(usuario)
                for destino in usuarios:
                    respuesta = cliente.get(
                        "/api/v1/leads/", HTTP_X_EMPRESA_ID=destino
                    )
                    assert respuesta.status_code == (
                        200 if destino == empresa else 403
                    )
                    if destino == empresa:
                        assert respuesta.data["count"] == 1
                if empresa != "A":
                    assert (
                        cliente.get(
                            f"/api/v1/leads/{lead_a}/",
                            HTTP_X_EMPRESA_ID=empresa,
                        ).status_code
                        == 404
                    )

        with transaccion_empresa("A"):
            encolar_trabajo(
                empresa_id="A",
                tipo_entidad="conversacion",
                entidad_id="C1",
                tipo_trabajo="extraer_ia",
                revision_entrada=1,
                configuracion={},
            )
        barrera = Barrier(2)

        def reclamar(numero):
            """Dos sesiones intentan reclamar la única tarea disponible."""
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'SET ROLE "{rol}"')
                barrera.wait(timeout=30)
                with transaccion_empresa("A"):
                    trabajo = reclamar_siguiente(
                        tipo_trabajo="extraer_ia", empresa_id="A"
                    )
                    return str(trabajo.pk) if trabajo else None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            reclamos = list(pool.map(reclamar, range(2)))
        assert sum(r is not None for r in reclamos) == 1
        with transaccion_empresa("A"):
            assert TrabajoProcesamiento.objects.get().intentos == 1
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(
                "UPDATE leads SET primera_fecha_registro = DATE '2020-01-01' "
                "WHERE empresa_id = 'A' AND lead_consolidado_id = %s",
                [lead_a],
            )
            cursor.execute(f'SET ROLE "{rol}"')
        barrera = Barrier(2)

        def asignar(numero):
            """Compite por el único cupo del mismo asesor físico."""
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'SET ROLE "{rol}"')
                barrera.wait(timeout=30)
                return generar_asignaciones(
                    usuario=usuarios["A"], empresa_id="A"
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            asignaciones = list(pool.map(asignar, range(2)))
        assert sum(r["creadas"] for r in asignaciones) == 1
        with transaccion_empresa("A"):
            from django.utils import timezone

            assert AsignacionDiaria.objects.get().fecha_operativa == (
                timezone.localdate()
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT primera_fecha_registro FROM leads "
                    "WHERE lead_consolidado_id = %s",
                    [lead_a],
                )
                assert cursor.fetchone()[0].isoformat() == "2020-01-01"
        with override_settings(ALLOWED_HOSTS=["testserver"]):
            assert APIClient().get("/api/v1/leads/").status_code == 401
            for u, perfil, activa, empresa in restringidos:
                cliente = APIClient()
                cliente.force_authenticate(u)
                lista = cliente.get(
                    "/api/v1/leads/", HTTP_X_EMPRESA_ID=empresa
                )
                if perfil == "asesor" and activa:
                    assert (
                        lista.status_code == 200 and lista.data["count"] == 0
                    )
                    for hijo in ("", "prioridades/", "conversaciones/"):
                        assert (
                            cliente.get(
                                f"/api/v1/leads/{lead_a}/{hijo}",
                                HTTP_X_EMPRESA_ID=empresa,
                            ).status_code
                            == 404
                        )
                else:
                    assert lista.status_code == 403
                for ruta in ("asignaciones/generar/",):
                    assert (
                        cliente.post(
                            "/api/v1/" + ruta,
                            {},
                            format="json",
                            HTTP_X_EMPRESA_ID=empresa,
                        ).status_code
                        == 403
                    )
            cliente = APIClient()
            cliente.force_authenticate(asesor)
            assert (
                cliente.get(
                    f"/api/v1/leads/{lead_a}/", HTTP_X_EMPRESA_ID="A"
                ).status_code
                == 200
            )
        with connection.cursor() as cursor:
            for _ in range(8):
                cursor.execute("SELECT reservar_cuota_ia('sintetico')")
                assert cursor.fetchone()[0] is True
            cursor.execute("SELECT reservar_cuota_ia('sintetico')")
            assert cursor.fetchone()[0] is False
        print("OK: asignadores concurrentes y límite de cuota compartido.")
        print(
            "OK: alta concurrente idempotente, tres empresas, HTTP y leases."
        )
        supervisor = MembresiaEmpresa.objects.get(
            usuario=usuarios["A"], empresa_id="A"
        )
        barrera = Barrier(2)

        def transferir_o_gestionar(numero):
            """Compite por el lead conservando atención y cartera."""
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'SET ROLE "{rol}"')
                barrera.wait(timeout=30)
                if numero == 0:
                    transferir_responsable(
                        empresa_id="A",
                        lead_consolidado_id=lead_a,
                        supervisor=supervisor,
                        nuevo_responsable=asesor_destino,
                    )
                else:
                    registrar_gestion(
                        usuario=usuarios["A"],
                        empresa_id="A",
                        lead_id=lead_a,
                        clave="gestion-concurrente",
                        resultado="contactado",
                    )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(transferir_o_gestionar, range(2)))
        with transaccion_empresa("A"):
            assert (
                EstadoOperativoLead.objects.get(
                    lead_consolidado_id=lead_a
                ).asesor_responsable_id
                == asesor_destino.pk
            )
            assert GestionComercial.objects.count() == 1
            assert AsignacionDiaria.objects.get().estado == "completada"
        print("OK: transferencia y gestión simultáneas sin perder actividad.")
        if os.environ.get("POSTGRES_BIN"):
            from tests.respaldo_postgresql import probar_respaldo

            probar_respaldo(
                connection,
                esquema,
                valores["SUPABASE_DB_URL"],
                Path(os.environ["POSTGRES_BIN"]),
            )
    finally:
        if creado:
            # Los nombres proceden únicamente del UUID generado arriba.
            assert esquema == "carrera_" + sufijo and rol == "rol_" + sufijo
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE')
                cursor.execute(
                    f'DROP SCHEMA IF EXISTS "{esquema}_original" CASCADE'
                )
                cursor.execute(f'DROP ROLE IF EXISTS "{rol}"')
        connections.close_all()


if __name__ == "__main__":
    verificar()
