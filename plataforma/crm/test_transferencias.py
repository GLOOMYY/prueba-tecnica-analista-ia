"""Regresiones de cupos, posiciones y auditoría de transferencias."""

from unittest.mock import patch

from cuentas.models import MembresiaEmpresa
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from crm.models import AsignacionDiaria, EstadoOperativoLead, EventoAuditoria
from crm.services.cartera import transferir_responsable


class TransferenciasTest(TestCase):
    """Verifica movimientos con cupos consumidos y huecos en la cola."""

    def setUp(self):
        """Prepara dos asesores y supervisor de una misma empresa."""
        miembros = []
        for nombre, rol in (
            ("sup", "supervisor"),
            ("uno", "asesor"),
            ("dos", "asesor"),
        ):
            usuario = get_user_model().objects.create_user(username=nombre)
            miembros.append(
                MembresiaEmpresa.objects.create(
                    usuario=usuario,
                    empresa_id="A",
                    rol=rol,
                    asesor_id=nombre,
                )
            )
        self.supervisor, self.uno, self.dos = miembros
        self.estado = EstadoOperativoLead.objects.create(
            empresa_id="A",
            lead_consolidado_id="L1",
            asesor_responsable=self.uno,
        )
        self.asignacion = self.asignar("L1", self.uno, 1)
        self.sede = patch("crm.services.cartera._validar_sede", return_value=2)
        self.sede.start()
        self.addCleanup(self.sede.stop)

    def asignar(self, lead, asesor, posicion):
        """Crea una asignación del día con su posición original."""
        return AsignacionDiaria.objects.create(
            empresa_id="A",
            lead_consolidado_id=lead,
            asesor=asesor,
            posicion_inicial=posicion,
            fecha_operativa=timezone.localdate(),
        )

    def transferir(self):
        """Invoca el servicio con las membresías autorizadas de la prueba."""
        return transferir_responsable(
            empresa_id="A",
            lead_consolidado_id="L1",
            supervisor=self.supervisor,
            nuevo_responsable=self.dos,
        )

    def test_hueco_no_reutiliza_posicion_ocupada(self):
        """Con una fila en posición dos, la transferida recibe tres."""
        self.asignar("L2", self.dos, 2)
        self.transferir()
        self.asignacion.refresh_from_db()
        self.assertEqual(self.asignacion.posicion_inicial, 3)
        self.assertEqual(self.asignacion.asesor_id, self.dos.pk)

    def test_repetir_transferencia_no_consume_cupo_ni_duplica_auditoria(self):
        """La segunda petición al mismo destino no produce cambios."""
        self.asignar("L2", self.dos, 1)
        self.transferir()
        self.transferir()
        self.assertEqual(EventoAuditoria.objects.count(), 1)

    def test_completada_conserva_asesor_que_la_atendio(self):
        """La transferencia cambia la cartera, pero conserva el cupo pasado."""
        self.asignacion.estado = "completada"
        self.asignacion.save()
        self.transferir()
        self.asignacion.refresh_from_db()
        self.estado.refresh_from_db()
        self.assertEqual(self.asignacion.asesor_id, self.uno.pk)
        self.assertEqual(self.estado.asesor_responsable_id, self.dos.pk)

    def test_sin_cupo_no_modifica_cartera(self):
        """El rechazo del movimiento no deja cambios parciales."""
        self.asignar("L2", self.dos, 1)
        self.asignar("L3", self.dos, 2)
        with self.assertRaises(ValueError):
            self.transferir()
        self.estado.refresh_from_db()
        self.assertEqual(self.estado.asesor_responsable_id, self.uno.pk)
        self.assertFalse(EventoAuditoria.objects.exists())
