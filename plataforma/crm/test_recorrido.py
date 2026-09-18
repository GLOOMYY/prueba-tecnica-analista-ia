"""Pruebas HTTP de permisos, gestión idempotente y navegación comercial."""

from cuentas.models import MembresiaEmpresa
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from crm.models import EstadoOperativoLead, GestionComercial


class RecorridoTest(TestCase):
    """Verifica comportamientos que protegen cartera e historia comercial."""

    def setUp(self):
        """Crea carteras sintéticas en dos empresas y un operador técnico."""
        self.usuario = get_user_model().objects.create_user(username="asesor")
        self.miembro = MembresiaEmpresa.objects.create(
            usuario=self.usuario, empresa_id="A", rol="asesor"
        )
        self.propio = EstadoOperativoLead.objects.create(
            empresa_id="A",
            lead_consolidado_id="propio",
            asesor_responsable=self.miembro,
        )
        EstadoOperativoLead.objects.create(
            empresa_id="A", lead_consolidado_id="ajeno"
        )
        EstadoOperativoLead.objects.create(
            empresa_id="B", lead_consolidado_id="otra-empresa"
        )
        self.api = APIClient()
        self.api.force_authenticate(self.usuario)
        self.api.credentials(HTTP_X_EMPRESA_ID="A")

    def test_tablero_cuenta_solo_cartera(self):
        """Un asesor no recibe agregados de otros asesores."""
        respuesta = self.api.get("/api/v1/dashboard/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["leads_activos"], 1)

    def test_objetos_ajenos_no_se_revelan(self):
        """Un lead ajeno devuelve el mismo resultado que uno inexistente."""
        for lead in ["ajeno", "otra-empresa", "inexistente"]:
            with self.subTest(lead=lead):
                respuesta = self.api.get(f"/api/v1/leads/{lead}/")
                self.assertEqual(respuesta.status_code, 404)

    def test_operador_sin_acceso_comercial(self):
        """El rol técnico no obtiene listados ni métricas comerciales."""
        self.miembro.rol = "operador"
        self.miembro.save()
        for ruta in ["dashboard", "leads", "mis-leads"]:
            self.assertEqual(self.api.get(f"/api/v1/{ruta}/").status_code, 403)

    def test_gestion_repetida_y_conflicto(self):
        """El mismo envío no duplica; otro cuerpo con la clave falla."""
        ruta = "/api/v1/leads/propio/gestiones/"
        datos = {"resultado": "sin_respuesta", "nota": "Primer intento"}
        for esperado in [201, 200]:
            respuesta = self.api.post(
                ruta, datos, format="json", HTTP_IDEMPOTENCY_KEY="envio-1"
            )
            self.assertEqual(respuesta.status_code, esperado, respuesta.data)
        self.assertEqual(GestionComercial.objects.count(), 1)
        respuesta = self.api.post(
            ruta,
            {"resultado": "contactado"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="envio-1",
        )
        self.assertEqual(respuesta.status_code, 409)

    def test_rechaza_perdida_sin_motivo(self):
        """Un error de negocio revierte solicitud y evento juntos."""
        respuesta = self.api.post(
            "/api/v1/leads/propio/gestiones/",
            {"resultado": "perdido"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="perdida",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(GestionComercial.objects.exists())

    def test_seleccion_y_detalle_html(self):
        """La sesión selecciona una empresa validada y abre su detalle."""
        self.client.force_login(self.usuario)
        self.assertRedirects(self.client.get("/"), "/empresas/")
        self.client.post("/empresas/", {"empresa_id": "A"})
        self.assertContains(self.client.get("/leads/propio/"), "Guardar")
        self.assertEqual(self.client.get("/leads/ajeno/").status_code, 404)
