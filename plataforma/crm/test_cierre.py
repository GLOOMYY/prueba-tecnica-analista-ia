"""Pruebas de vigencia, cola durable y resolución supervisada."""

from datetime import timedelta
from unittest.mock import patch

from cuentas.models import MembresiaEmpresa, RolMembresia
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from crm.models import (
    CapturaEstructurada,
    CapturaRevision,
    EstadoCapturaRevision,
    EstadoOperativoLead,
    EstadoTrabajo,
    TrabajoProcesamiento,
)
from crm.services.extraccion_ia import (
    ErrorExtraccion,
    procesar_extraccion,
    validar_resultado,
)
from crm.services.revisiones import resolver_revision
from crm.services.trabajos import (
    completar_trabajo,
    encolar_trabajo,
    reclamar_siguiente,
    reintentar_trabajo,
)
from crm.services.vigencia import publicar_prioridad


class VigenciaYTrabajosTest(TestCase):
    """Protege resultados tardíos de entradas y workers reemplazados."""

    def setUp(self):
        """Crea un estado operativo sintético para operaciones atómicas."""
        self.estado = EstadoOperativoLead.objects.create(
            empresa_id="A", lead_consolidado_id="LEAD-1", revision_entrada=2
        )

    def test_prioridad_tardia_no_desplaza_revision_mas_nueva(self):
        """Una prioridad de revisión uno queda histórica, no vigente."""
        publicada = publicar_prioridad(
            empresa_id="A",
            lead_id="LEAD-1",
            revision_entrada=1,
            priorizacion_id="PRIO-ANTERIOR",
            origen="lote",
        )
        self.assertFalse(publicada)
        self.estado.refresh_from_db()
        self.assertEqual(self.estado.priorizacion_vigente_id, "")

    def test_worker_no_publica_tras_cambio_de_revision(self):
        """La tarea queda obsoleta si la entrada cambia durante ejecución."""
        trabajo, _ = encolar_trabajo(
            empresa_id="A",
            tipo_entidad="conversacion",
            entidad_id="CONV-1",
            tipo_trabajo="extraer_ia",
            revision_entrada=1,
            configuracion={"modelo": "simulado"},
            huella_entrada="a" * 64,
        )
        reclamado = reclamar_siguiente(tipo_trabajo="extraer_ia")
        completado = completar_trabajo(
            trabajo_id=trabajo.pk,
            lease_token=reclamado.lease_token,
            revision_entrada_actual=2,
        )
        self.assertFalse(completado)
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.estado, EstadoTrabajo.OBSOLETO)

    def test_reintentos_acotados_no_guardan_detalle_de_error(self):
        """El último intento guarda un código sanitario sin traza completa."""
        trabajo, _ = encolar_trabajo(
            empresa_id="A",
            tipo_entidad="conversacion",
            entidad_id="CONV-2",
            tipo_trabajo="extraer_ia",
            revision_entrada=1,
            configuracion={},
        )
        reclamado = reclamar_siguiente(tipo_trabajo="extraer_ia")
        estado = reintentar_trabajo(
            trabajo_id=trabajo.pk,
            lease_token=reclamado.lease_token,
            categoria_error="timeout",
            espera_segundos=0,
            max_intentos=1,
        )
        self.assertEqual(estado, EstadoTrabajo.FALLIDO)
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.ultimo_error, "timeout")


class ValidacionExtraccionTest(TestCase):
    """Comprueba evidencia antes de publicar una extracción de IA."""

    def setUp(self):
        """Define dos mensajes sintéticos de autores distintos."""
        self.mensajes = [
            {"posicion": 1, "emisor": "cliente", "texto": "Quiero la X."},
            {"posicion": 2, "emisor": "asesor", "texto": "Ofrezco crédito."},
        ]
        self.resultado = {
            "modelos_interes": ["X"],
            "presupuesto": None,
            "cuota_inicial": None,
            "forma_pago": None,
            "intencion_declarada": None,
            "objecion_principal": None,
            "cliente_pidio_cita": None,
            "cliente_pidio_cotizacion": None,
            "cliente_pidio_credito": None,
            "asesor_ofrecio_credito": True,
            "evidencias": [
                {
                    "campo": "modelos_interes",
                    "posicion": 1,
                    "cita": "Quiero la X.",
                },
                {
                    "campo": "asesor_ofrecio_credito",
                    "posicion": 2,
                    "cita": "Ofrezco crédito.",
                },
            ],
        }

    def test_hechos_con_emisor_correcto_se_conservan(self):
        """Acepta la respuesta cuando cada valor declarado tiene evidencia."""
        validada = validar_resultado(self.resultado, self.mensajes)
        self.assertEqual(validada["modelos_interes"], ["X"])

    def test_hecho_cliente_no_acepta_evidencia_de_asesor(self):
        """Evita convertir una oferta del asesor en intención del cliente."""
        self.resultado["cliente_pidio_credito"] = True
        self.resultado["evidencias"].append(
            {
                "campo": "cliente_pidio_credito",
                "posicion": 2,
                "cita": "Ofrezco crédito.",
            }
        )
        with self.assertRaises(ErrorExtraccion):
            validar_resultado(self.resultado, self.mensajes)

    def test_cita_inventada_y_tipos_incorrectos_se_rechazan(self):
        """Una posición real no basta para respaldar texto inventado."""
        self.resultado["evidencias"][0]["cita"] = "Quiero la Z."
        with self.assertRaises(ErrorExtraccion):
            validar_resultado(self.resultado, self.mensajes)
        self.resultado["evidencias"][0]["cita"] = "Quiero la X."
        for valor in (True, -1, float("nan"), "100"):
            self.resultado["presupuesto"] = valor
            with self.subTest(valor=valor), self.assertRaises(ErrorExtraccion):
                validar_resultado(self.resultado, self.mensajes)


class PublicacionWorkerTest(TestCase):
    """Ejercita el worker completo con proveedor sintético sin usar cuota."""

    def setUp(self):
        """Prepara una tarea real y simula solo la fuente histórica externa."""
        self.usuario = get_user_model().objects.create_user(username="worker")
        self.estado = EstadoOperativoLead.objects.create(
            empresa_id="A", lead_consolidado_id="L1"
        )
        encolar_trabajo(
            empresa_id="A",
            tipo_entidad="conversacion",
            entidad_id="C1",
            tipo_trabajo="extraer_ia",
            revision_entrada=1,
            configuracion={"autor_id": self.usuario.pk, "lead_id": "L1"},
        )
        self.trabajo = reclamar_siguiente(tipo_trabajo="extraer_ia")
        self.conversacion = {
            "conversacion_id": "C1",
            "lead_consolidado_id": "L1",
            "empresa_id": "A",
            "mensajes": [
                {"posicion": 1, "emisor": "cliente", "texto": "Hola"}
            ],
        }
        self.resultado = {
            "modelos_interes": [],
            "presupuesto": None,
            "cuota_inicial": None,
            "forma_pago": None,
            "intencion_declarada": None,
            "objecion_principal": None,
            "cliente_pidio_cita": None,
            "cliente_pidio_cotizacion": None,
            "cliente_pidio_credito": None,
            "asesor_ofrecio_credito": None,
            "evidencias": [],
        }
        self.fuente = patch(
            "crm.services.extraccion_ia.cargar_conversacion",
            return_value=self.conversacion,
        )
        self.fuente.start()
        self.addCleanup(self.fuente.stop)
        self.historia = patch("crm.services.extraccion_ia.guardar_historia_ia")
        self.historia.start()
        self.addCleanup(self.historia.stop)

    def test_publica_una_vez_con_autor_correcto(self):
        """El identificador de usuario se persiste como FK, sin ValueError."""

        def proveedor(*_):
            return self.resultado

        self.assertEqual(
            procesar_extraccion(self.trabajo, proveedor), "completado"
        )
        self.assertEqual(CapturaEstructurada.objects.get().autor, self.usuario)
        self.assertEqual(
            procesar_extraccion(self.trabajo, proveedor), "lease_perdido"
        )
        self.assertEqual(CapturaEstructurada.objects.count(), 1)

    def test_expira_durante_proveedor_sin_publicar(self):
        """Un resultado tardío no modifica la captura ni el trabajo."""

        def proveedor(*_):
            TrabajoProcesamiento.objects.filter(pk=self.trabajo.pk).update(
                lease_hasta=timezone.now() - timedelta(seconds=1)
            )
            return self.resultado

        self.assertEqual(
            procesar_extraccion(self.trabajo, proveedor), "lease_perdido"
        )
        self.assertFalse(CapturaEstructurada.objects.exists())

    def test_revision_cambia_durante_proveedor(self):
        """Conserva la revisión nueva y marca obsoleta la tarea anterior."""

        def proveedor(*_):
            EstadoOperativoLead.objects.filter(pk=self.estado.pk).update(
                revision_entrada=2
            )
            return self.resultado

        self.assertEqual(
            procesar_extraccion(self.trabajo, proveedor), "obsoleto"
        )
        self.assertFalse(CapturaEstructurada.objects.exists())

    def test_fallo_guardando_revierte_cierre_trabajo(self):
        """Un error de programación se propaga y revierte toda publicación."""
        with (
            patch(
                "crm.services.extraccion_ia.CapturaEstructurada.objects.create",
                side_effect=RuntimeError("fallo sintético"),
            ),
            self.assertRaises(RuntimeError),
        ):
            procesar_extraccion(self.trabajo, lambda *_: self.resultado)
        self.trabajo.refresh_from_db()
        self.assertEqual(self.trabajo.estado, EstadoTrabajo.EJECUTANDO)
        self.assertFalse(CapturaEstructurada.objects.exists())
        self.assertEqual(self.trabajo.resultado_proveedor, self.resultado)
        # Simula recuperación tras caída antes de publicar: la respuesta ya
        # recibida es durable y el proveedor no debe volver a consumir cuota.
        with patch(
            "crm.services.extraccion_ia.generar_con_gemini"
        ) as proveedor:
            self.assertEqual(
                procesar_extraccion(self.trabajo, proveedor), "completado"
            )
            proveedor.assert_not_called()


class RevisionSupervisadaTest(TestCase):
    """Comprueba que revisión no crea ni fusiona identidades por intuición."""

    def setUp(self):
        """Crea solicitante, supervisor, asesor y una captura ambigua."""
        usuario = get_user_model()
        self.solicitante = usuario.objects.create_user(username="solicitante")
        self.supervisor = usuario.objects.create_user(username="supervisor")
        self.asesor = usuario.objects.create_user(username="asesor")
        MembresiaEmpresa.objects.create(
            usuario=self.solicitante, empresa_id="A", rol=RolMembresia.ASESOR
        )
        MembresiaEmpresa.objects.create(
            usuario=self.supervisor,
            empresa_id="A",
            rol=RolMembresia.SUPERVISOR,
        )
        MembresiaEmpresa.objects.create(
            usuario=self.asesor, empresa_id="A", rol=RolMembresia.ASESOR
        )
        self.estado = EstadoOperativoLead.objects.create(
            empresa_id="A", lead_consolidado_id="LEAD-RESOLVER"
        )
        self.revision = CapturaRevision.objects.create(
            empresa_id="A",
            solicitante=self.solicitante,
            datos_propuestos={"nombre_cliente": "Dato declarado"},
            motivo="identidad_ambigua",
        )

    def test_captura_incompleta_no_se_publica(self):
        """No se da por resuelta una captura sin contacto ni sede válidos."""
        datos = {
            "usuario": self.supervisor,
            "empresa_id": "A",
            "revision_id": str(self.revision.pk),
            "accion": "vincular",
            "lead_id": self.estado.lead_consolidado_id,
        }
        with self.assertRaises(ValueError):
            resolver_revision(**datos)
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.estado, EstadoCapturaRevision.PENDIENTE)
        self.assertFalse(CapturaEstructurada.objects.exists())

    def test_asesor_no_resuelve(self):
        """La decisión de identidad está reservada para supervisión."""
        with self.assertRaises(PermissionDenied):
            resolver_revision(
                usuario=self.asesor,
                empresa_id="A",
                revision_id=str(self.revision.pk),
                accion="rechazar",
                nota="No hay evidencia suficiente.",
            )
