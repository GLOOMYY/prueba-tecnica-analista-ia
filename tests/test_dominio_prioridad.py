"""Pruebas de paridad de la política comercial compartida."""

import unittest
from decimal import Decimal

from dominio.prioridad import (
    PrioridadEntrada,
    calcular_prioridad,
    clasificar_cola,
)


class PrioridadReglasTest(unittest.TestCase):
    """Protege el contrato de `reglas_evidencia_v1`."""

    def test_cita_unica_es_caliente(self) -> None:
        """No usa un umbral numérico para determinar temperatura."""
        resultado = calcular_prioridad(
            PrioridadEntrada(
                modelo_sku=None,
                cuota_inicial_positiva=False,
                forma_pago=None,
                cliente_pidio_cita=True,
            )
        )

        self.assertEqual(resultado.puntos, 40)
        self.assertEqual(resultado.score, Decimal("44.44"))
        self.assertEqual(resultado.temperatura, "caliente")

    def test_solo_pago_es_tibio_y_no_infiere_credito(self) -> None:
        """Acepta solo las formas de pago permitidas por la política actual."""
        resultado = calcular_prioridad(
            PrioridadEntrada(
                modelo_sku="DESCONOCIDO",
                cuota_inicial_positiva=False,
                forma_pago="mixto",
                cliente_pidio_cita=False,
            )
        )

        self.assertEqual(resultado.puntos, 0)
        self.assertEqual(resultado.temperatura, "sin_informacion_suficiente")

    def test_todas_las_senales_alcanzan_el_maximo(self) -> None:
        """Conserva pesos y explicación de la regla operacional vigente."""
        resultado = calcular_prioridad(
            PrioridadEntrada(
                modelo_sku="HON-125",
                cuota_inicial_positiva=True,
                forma_pago="credito",
                cliente_pidio_cita=True,
            )
        )

        self.assertEqual(resultado.puntos, 90)
        self.assertEqual(resultado.score, Decimal("100.00"))
        self.assertEqual(
            [item.senal for item in resultado.contribuciones],
            [
                "modelo_identificado",
                "inicial_positiva",
                "forma_pago_declarada",
                "cita_solicitada",
            ],
        )

    def test_cola_de_revision_prevalece_sobre_temperatura(self) -> None:
        """Evita enviar automáticamente a atención un contexto inseguro."""
        cola, accion = clasificar_cola(
            temperatura="caliente",
            todas_consultas_descartadas=False,
            estado_contexto="revision_orden",
        )

        self.assertEqual(cola, "revision_datos")
        self.assertIn("orden temporal", accion)


if __name__ == "__main__":
    unittest.main()
