"""Pruebas de integridad de los modelos operativos de CRM."""

from datetime import date, timedelta

from cuentas.models import MembresiaEmpresa, RolMembresia
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from plataforma.database import configurar_base_datos

from crm.contexto_empresa import transaccion_empresa
from crm.models import (
    AsignacionDiaria,
    EstadoOperativoLead,
    SolicitudIdempotente,
    TrabajoProcesamiento,
)
from crm.services.trabajos import encolar_trabajo, reclamar_siguiente


class TrabajosDurablesTest(TestCase):
    """Comprueba idempotencia, reclamo y recuperación de trabajos."""

    def test_encolar_misma_revision_no_duplica(self) -> None:
        """Un reintento de alta produce un solo trabajo lógico."""
        primero, creado = encolar_trabajo(
            empresa_id="EMP-01",
            tipo_entidad="conversacion",
            entidad_id="CONV-01",
            tipo_trabajo="extraer_ia",
            revision_entrada=1,
            configuracion={"modelo": "gemini"},
        )
        segundo, repetido = encolar_trabajo(
            empresa_id="EMP-01",
            tipo_entidad="conversacion",
            entidad_id="CONV-01",
            tipo_trabajo="extraer_ia",
            revision_entrada=1,
            configuracion={"modelo": "gemini"},
        )

        self.assertTrue(creado)
        self.assertFalse(repetido)
        self.assertEqual(primero.trabajo_id, segundo.trabajo_id)

    def test_reclama_y_recupera_un_lease_vencido(self) -> None:
        """Un worker interrumpido permite reanudar el trabajo tras su lease."""
        trabajo, _ = encolar_trabajo(
            empresa_id="EMP-01",
            tipo_entidad="conversacion",
            entidad_id="CONV-02",
            tipo_trabajo="extraer_ia",
            revision_entrada=1,
            configuracion={},
        )
        reclamado = reclamar_siguiente(
            tipo_trabajo="extraer_ia", lease_segundos=1
        )
        self.assertEqual(reclamado.trabajo_id, trabajo.trabajo_id)
        TrabajoProcesamiento.objects.filter(
            trabajo_id=trabajo.trabajo_id
        ).update(lease_hasta=timezone.now() - timedelta(seconds=1))

        recuperado = reclamar_siguiente(
            tipo_trabajo="extraer_ia", lease_segundos=1
        )
        self.assertEqual(recuperado.trabajo_id, trabajo.trabajo_id)
        self.assertEqual(recuperado.intentos, 2)


class ModeloOperativoCrmTest(TestCase):
    """Comprueba invariantes que protegen estado, cartera e idempotencia."""

    def setUp(self) -> None:
        """Crea actores y membresías para las pruebas de integridad."""
        self.usuario = get_user_model().objects.create_user(
            username="supervisor_crm",
            password="clave-de-prueba-segura",
        )
        self.membresia = MembresiaEmpresa.objects.create(
            usuario=self.usuario,
            empresa_id="empresa_a",
            rol=RolMembresia.SUPERVISOR,
        )

    def test_estado_es_unico_por_empresa_y_lead(self) -> None:
        """Evita dos estados operativos contradictorios para un mismo lead."""
        EstadoOperativoLead.objects.create(
            empresa_id="empresa_a",
            lead_consolidado_id="lead_001",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            EstadoOperativoLead.objects.create(
                empresa_id="empresa_a",
                lead_consolidado_id="lead_001",
            )

    def test_asignacion_diaria_no_duplica_un_lead(self) -> None:
        """Protege el reparto diario ante dos inserciones del mismo lead."""
        AsignacionDiaria.objects.create(
            empresa_id="empresa_a",
            lead_consolidado_id="lead_001",
            asesor=self.membresia,
            fecha_operativa=date(2026, 9, 17),
            posicion_inicial=1,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            AsignacionDiaria.objects.create(
                empresa_id="empresa_a",
                lead_consolidado_id="lead_001",
                asesor=self.membresia,
                fecha_operativa=date(2026, 9, 17),
                posicion_inicial=2,
            )

    def test_solicitud_idempotente_unica_por_actor_y_operacion(self) -> None:
        """Evita que un reintento cree otra operación lógica del actor."""
        SolicitudIdempotente.objects.create(
            empresa_id="empresa_a",
            actor=self.usuario,
            operacion="crear_lead",
            clave="clave-prueba-001",
            huella_cuerpo="a" * 64,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            SolicitudIdempotente.objects.create(
                empresa_id="empresa_a",
                actor=self.usuario,
                operacion="crear_lead",
                clave="clave-prueba-001",
                huella_cuerpo="a" * 64,
            )


class ContextoBaseDatosTest(TestCase):
    """Comprueba límites locales antes de la integración PostgreSQL real."""

    def test_configuracion_web_no_usa_la_credencial_del_cargador(self) -> None:
        """Mantiene SQLite si no se declara la URL propia de la web."""
        configuracion = configurar_base_datos(
            {
                "SUPABASE_DB_URL": "postgresql://no-debe-usarse/privada",
                "DJANGO_SQLITE_PATH": "prueba.sqlite3",
            }
        )

        self.assertEqual(configuracion["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(configuracion["NAME"], "prueba.sqlite3")

    def test_configuracion_postgresql_fija_ssl_y_esquema(self) -> None:
        """Construye una conexión web aislada sin imprimir su contraseña."""
        configuracion = configurar_base_datos(
            {
                "DJANGO_DATABASE_URL": (
                    "postgresql://usuario:clave%40segura@db.example.com:6543/"
                    "crm_demo?sslmode=require"
                ),
                "DJANGO_DB_SCHEMA": "crm",
            }
        )

        self.assertEqual(
            configuracion["ENGINE"],
            "django.db.backends.postgresql",
        )
        self.assertEqual(configuracion["HOST"], "db.example.com")
        self.assertEqual(configuracion["PORT"], "6543")
        self.assertEqual(configuracion["OPTIONS"]["sslmode"], "require")
        self.assertIn(
            "search_path=crm,public",
            configuracion["OPTIONS"]["options"],
        )

    def test_contexto_requiere_empresa_y_es_no_op_en_sqlite(self) -> None:
        """Rechaza ámbitos vacíos y permite pruebas locales sin PostgreSQL."""
        with self.assertRaises(ValueError):
            with transaccion_empresa(" "):
                pass

        with transaccion_empresa("empresa_a"):
            self.assertTrue(True)
