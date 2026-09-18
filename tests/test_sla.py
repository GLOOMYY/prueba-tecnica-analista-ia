"""Casos límite de medición temporal sin completar horas desconocidas."""

import unittest
from datetime import UTC, datetime, timedelta

from dominio.sla import resumir_sla


class SlaTest(unittest.TestCase):
    """Comprueba límites, incertidumbre y denominadores del indicador."""

    def test_limite_y_fechas_incompletas(self):
        ahora = datetime(2026, 9, 17, tzinfo=UTC)
        inicio = ahora - timedelta(days=2)
        filas = [
            {
                "inicio": inicio,
                "contacto": inicio + timedelta(hours=24),
                "contacto_impreciso": False,
            },
            {"inicio": inicio, "contacto": None, "contacto_impreciso": False},
            {"inicio": ahora, "contacto": None, "contacto_impreciso": False},
            {"inicio": None, "contacto": None, "contacto_impreciso": False},
            {"inicio": inicio, "contacto": None, "contacto_impreciso": True},
        ]
        resultado = resumir_sla(filas, ahora)
        self.assertEqual(resultado["denominador"], 2)
        self.assertEqual(resultado["porcentaje"], 50)
        self.assertEqual(resultado["en_plazo"], 1)
        self.assertEqual(resultado["no_medibles"], 2)
