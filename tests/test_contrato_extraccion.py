"""Regresiones del contrato común de lote y extracción individual."""

import unittest

from dominio.contrato_extraccion import crear_normalizador
from dominio.extraccion_individual import normalizar_individual
from tests.fixtures_ia import respuesta_cita


class ContratoCompartidoTest(unittest.TestCase):
    """No cambia evidencia ni confunde desconocidos al adaptar a la web."""

    def setUp(self):
        self.conversacion = {
            "conversacion_id": "C1",
            "empresa_id": "A",
            "mensajes": [{"emisor": "cliente", "texto": "Quiero una cita"}],
        }

    def test_misma_normalizacion_y_desconocidos(self):
        respuesta = respuesta_cita()
        normalizar, _, _ = crear_normalizador([], modelo="simulado")
        lote = normalizar(respuesta["conversaciones"][0], self.conversacion)
        individual = normalizar_individual(
            respuesta, self.conversacion, [], "simulado"
        )
        self.assertEqual(individual["_normalizado"], lote)
        self.assertIs(individual["cliente_pidio_cita"], True)
        self.assertIsNone(individual["presupuesto"])
        self.assertIsNone(individual["cliente_pidio_credito"])

    def test_rechaza_conversacion_ajena(self):
        with self.assertRaises(ValueError):
            normalizar_individual(
                respuesta_cita("OTRA"), self.conversacion, [], "simulado"
            )

    def test_evidencia_inventada_no_publica(self):
        respuesta = respuesta_cita()
        respuesta["conversaciones"][0]["cita"]["cliente_solicito"][
            "evidencias"
        ][0]["texto"] = "Me comprometo a comprar mañana"
        with self.assertRaises(ValueError):
            normalizar_individual(respuesta, self.conversacion, [], "simulado")
