"""Pruebas de los modelos de identidad de la plataforma."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.test import TestCase

from cuentas.acceso import alcance_empresa, obtener_membresia_activa
from cuentas.models import MembresiaEmpresa, RolMembresia


class MembresiaEmpresaTest(TestCase):
    """Comprueba las restricciones básicas de pertenencia empresarial."""

    def setUp(self) -> None:
        """Crea un usuario reutilizable para los escenarios de membresía."""
        self.usuario = get_user_model().objects.create_user(
            username="asesor_prueba",
            password="clave-de-prueba-segura",
        )

    def test_un_usuario_puede_pertenecer_a_dos_empresas(self) -> None:
        """Mantiene ámbitos separados para una misma persona."""
        MembresiaEmpresa.objects.create(
            usuario=self.usuario,
            empresa_id="empresa_a",
            rol=RolMembresia.ASESOR,
            asesor_id="asesor_a",
        )
        MembresiaEmpresa.objects.create(
            usuario=self.usuario,
            empresa_id="empresa_b",
            rol=RolMembresia.SUPERVISOR,
        )

        empresas = set(
            self.usuario.membresias.values_list("empresa_id", flat=True)
        )

        self.assertEqual(empresas, {"empresa_a", "empresa_b"})

    def test_no_duplica_membresia_de_la_misma_empresa(self) -> None:
        """Protege la elección de empresa contra registros contradictorios."""
        MembresiaEmpresa.objects.create(
            usuario=self.usuario,
            empresa_id="empresa_a",
            rol=RolMembresia.ASESOR,
        )

        with self.assertRaises(IntegrityError):
            MembresiaEmpresa.objects.create(
                usuario=self.usuario,
                empresa_id="empresa_a",
                rol=RolMembresia.SUPERVISOR,
            )

    def test_rechaza_empresa_sin_membresia_activa(self) -> None:
        """No permite tomar una empresa recibida sin autorización válida."""
        MembresiaEmpresa.objects.create(
            usuario=self.usuario,
            empresa_id="empresa_a",
            rol=RolMembresia.ASESOR,
            activa=False,
        )

        with self.assertRaises(PermissionDenied):
            obtener_membresia_activa(self.usuario, "empresa_a")

    def test_alcance_valida_empresa_antes_de_abrir_transaccion(self) -> None:
        """Expone la membresía autorizada al servicio comercial."""
        MembresiaEmpresa.objects.create(
            usuario=self.usuario,
            empresa_id="empresa_a",
            rol=RolMembresia.ASESOR,
        )

        with alcance_empresa(self.usuario, "empresa_a") as membresia:
            self.assertEqual(membresia.empresa_id, "empresa_a")
