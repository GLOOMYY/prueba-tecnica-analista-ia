"""Integración local del alta con tablas SQL de contrato mínimo.

SQLite comprueba transacciones y flujo HTTP; no sustituye las pruebas de
restricciones, bloqueos ni RLS del PostgreSQL de destino.
"""

from unittest.mock import patch

from cuentas.models import MembresiaEmpresa
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from crm.models import AsignacionDiaria, CapturaEstructurada, CapturaRevision
from crm.services.asignacion import generar_asignaciones
from crm.services.revisiones import resolver_revision

TABLAS = {
    "prioridades_publicadas": """empresa_id TEXT, lead_consolidado_id TEXT,
        priorizacion_id TEXT, revision_entrada INTEGER, origen TEXT,
        conflicto_lote BOOLEAN, PRIMARY KEY(empresa_id,lead_consolidado_id)""",
    "puntos_venta": "punto_venta_id TEXT PRIMARY KEY, empresa_id TEXT",
    "modelos_moto": "sku TEXT PRIMARY KEY",
    "leads": """lead_consolidado_id TEXT PRIMARY KEY, empresa_id TEXT,
        nombre_presentacion TEXT, primera_fecha_registro TEXT,
        primera_fecha_registro_hora TEXT,
        primera_fecha_registro_precision TEXT,
        ultima_fecha_registro TEXT, ultima_fecha_registro_hora TEXT,
        ultima_fecha_registro_precision TEXT, reglas_identidad TEXT,
        datos_originales TEXT, origen_registro TEXT""",
    "consultas": """lead_id_origen TEXT PRIMARY KEY, lead_consolidado_id TEXT,
        empresa_id TEXT, punto_venta_id TEXT, nombre_declarado TEXT,
        telefono TEXT, email TEXT, ciudad TEXT, modelo_declarado TEXT,
        modelo_sku TEXT, fecha_registro TEXT, fecha_registro_hora TEXT,
        fecha_registro_precision TEXT, calidad TEXT, datos_originales TEXT,
        origen_registro TEXT""",
    "ejecuciones": """ejecucion_id TEXT PRIMARY KEY,
        empresa_id TEXT, etapa TEXT,
        version_codigo TEXT, huella_entrada TEXT, importada BOOLEAN,
        inicio TEXT, fin TEXT, estado TEXT, configuracion TEXT,
        conteos TEXT, errores TEXT""",
    "priorizaciones": """priorizacion_id TEXT PRIMARY KEY,
        lead_consolidado_id TEXT, empresa_id TEXT, ejecucion_id TEXT,
        lead_id_contexto TEXT, score_prioridad NUMERIC, temperatura TEXT,
        cola TEXT, explicacion TEXT, accion_sugerida TEXT, version_reglas TEXT,
        contexto TEXT, datos_originales TEXT""",
}


class AltaSqlTest(TestCase):
    """Comprueba alta real, deduplicación, rollback y reintento vía API."""

    @classmethod
    def setUpTestData(cls):
        """Crea un contrato SQL local aislado de las fuentes de evaluación."""
        with connection.cursor() as cursor:
            for tabla, columnas in TABLAS.items():
                cursor.execute(f"CREATE TABLE {tabla} ({columnas})")
            cursor.execute("INSERT INTO puntos_venta VALUES ('S1', 'A')")
            cursor.execute("INSERT INTO puntos_venta VALUES ('S2', 'B')")
        cls.usuario = get_user_model().objects.create_user(username="captura")
        for empresa in ["A", "B"]:
            MembresiaEmpresa.objects.create(
                usuario=cls.usuario, empresa_id=empresa, rol="asesor"
            )

    def setUp(self):
        """Prepara un cliente y declaraciones sintéticas explícitas."""
        self.api = APIClient()
        self.api.force_authenticate(self.usuario)
        self.datos = {
            "nombre_cliente": "Ana Perez",
            "telefono": "3001234567",
            "sede_id": "S1",
            "cliente_pidio_cita": True,
        }

    def enviar(self, clave="uno", empresa="A"):
        """Envía una captura JSON con ámbito e idempotencia."""
        return self.api.post(
            "/api/v1/leads/",
            self.datos,
            format="json",
            HTTP_X_EMPRESA_ID=empresa,
            HTTP_IDEMPOTENCY_KEY=clave,
        )

    def test_alta_prioridad_y_reintento(self):
        """Guarda prioridad de cita y preserva IDs ante doble envío."""
        primera = self.enviar()
        self.assertEqual(primera.status_code, 201, primera.data)
        self.assertEqual(primera.data["prioridad"]["score"], "44.44")
        segunda = self.enviar()
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(primera.data, segunda.data)
        self.assertEqual(CapturaEstructurada.objects.count(), 1)
        self.client.force_login(self.usuario)
        self.client.post("/empresas/", {"empresa_id": "A"})
        detalle = self.client.get(
            "/leads/" + primera.data["lead_consolidado_id"] + "/"
        )
        self.assertContains(detalle, "44,44")

    def test_consulta_nueva_y_empresa_distinta(self):
        """Mismo cliente se consolida solo dentro de la misma empresa."""
        primera = self.enviar()
        segunda = self.enviar("dos")
        self.assertEqual(segunda.status_code, 201, segunda.data)
        self.assertFalse(segunda.data["lead_creado"])
        self.assertEqual(
            primera.data["lead_consolidado_id"],
            segunda.data["lead_consolidado_id"],
        )
        self.datos["sede_id"] = "S2"
        otra = self.enviar("tres", "B")
        self.assertEqual(otra.status_code, 201, otra.data)
        self.assertNotEqual(
            primera.data["lead_consolidado_id"],
            otra.data["lead_consolidado_id"],
        )

    def test_telefono_compartido_se_conserva_en_revision(self):
        """Un nombre incompatible no fusiona ni pierde su captura."""
        self.enviar()
        self.datos["nombre_cliente"] = "Pedro Gomez"
        respuesta = self.enviar("ambiguo")
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertNotIn("lead_consolidado_id", respuesta.data)
        self.assertEqual(CapturaRevision.objects.count(), 1)

    def test_fallo_prioridad_revierte_todo(self):
        """Un fallo posterior a la consulta no deja un lead parcial."""
        with patch(
            "crm.services.alta.EventoAuditoria.objects.create",
            side_effect=RuntimeError("fallo simulado"),
        ):
            with self.assertRaises(RuntimeError):
                self.enviar()
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM leads")
            self.assertEqual(cursor.fetchone()[0], 0)
        self.assertFalse(CapturaEstructurada.objects.exists())

    def test_revision_crea_cliente_distinto_con_score_y_reintento(self):
        """La decisión explícita conserva ambos clientes del teléfono común."""
        primera = self.enviar()
        self.datos["nombre_cliente"] = "Pedro Gomez"
        respuesta = self.enviar("ambiguo")
        miembro = MembresiaEmpresa.objects.get(
            usuario=self.usuario, empresa_id="A"
        )
        miembro.rol = "supervisor"
        miembro.save()
        argumentos = {
            "usuario": self.usuario,
            "empresa_id": "A",
            "revision_id": respuesta.data["revision_id"],
            "accion": "crear_distinto",
            "nota": "Teléfono compartido.",
        }
        resolucion, repetida = resolver_revision(**argumentos)
        self.assertFalse(repetida)
        self.assertNotEqual(
            primera.data["lead_consolidado_id"],
            resolucion["lead_consolidado_id"],
        )
        self.assertTrue(resolver_revision(**argumentos)[1])
        with connection.cursor() as cursor:
            for tabla in ("leads", "consultas", "priorizaciones"):
                cursor.execute(f"SELECT count(*) FROM {tabla}")
                self.assertEqual(cursor.fetchone()[0], 2)

    def test_pantalla_revision_restringida_y_resolucion(self):
        """Solo el supervisor puede ver la captura y guardar su decisión."""
        self.enviar()
        self.datos["nombre_cliente"] = "Pedro Gomez"
        respuesta = self.enviar("ambiguo")
        ruta = f"/revisiones/{respuesta.data['revision_id']}/"
        self.client.force_login(self.usuario)
        sesion = self.client.session
        sesion["empresa_id"] = "A"
        sesion.save()
        self.assertEqual(self.client.get(ruta).status_code, 403)
        miembro = MembresiaEmpresa.objects.get(
            usuario=self.usuario, empresa_id="A"
        )
        miembro.rol = "supervisor"
        miembro.save()
        self.assertContains(self.client.get("/revisiones/"), "Pedro Gomez")
        self.assertContains(self.client.get(ruta), "Crear cliente distinto")
        resultado = self.client.post(
            ruta,
            {
                "accion": "rechazar",
                "nota": "Contacto no verificable.",
            },
        )
        self.assertRedirects(resultado, "/revisiones/")

    def test_asignacion_capacidad_y_repeticion(self):
        """Capacidad uno deja el segundo lead pendiente aunque se repita."""
        self.enviar()
        self.datos["telefono"] = "3011234567"
        self.datos["nombre_cliente"] = "Luis Perez"
        self.enviar("segundo")
        miembro = MembresiaEmpresa.objects.get(
            usuario=self.usuario, empresa_id="A"
        )
        miembro.asesor_id = "AS1"
        miembro.save()
        supervisor = get_user_model().objects.create_user(
            username="supervisor"
        )
        MembresiaEmpresa.objects.create(
            usuario=supervisor, empresa_id="A", rol="supervisor"
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE asesores (asesor_id TEXT, empresa_id TEXT, "
                "punto_venta_id TEXT, capacidad_diaria_leads INTEGER, "
                "activo BOOLEAN)"
            )
            cursor.execute(
                "INSERT INTO asesores VALUES ('AS1','A','S1',1,true)"
            )
            cursor.execute(
                "CREATE VIEW v_prioridad_vigente AS "
                "SELECT * FROM priorizaciones"
            )
        primera = generar_asignaciones(usuario=supervisor, empresa_id="A")
        self.assertEqual(primera["creadas"], 1)
        segunda = generar_asignaciones(usuario=supervisor, empresa_id="A")
        self.assertEqual(segunda["creadas"], 0)
        self.assertEqual(AsignacionDiaria.objects.count(), 1)
