"""Pruebas de reglas de identidad reutilizadas por lote y plataforma."""

import unittest

from dominio.identidad import (
    clave_texto,
    id_consolidado,
    nombres_compatibles,
    normalizar_telefono_colombia,
)


class IdentidadDominioTest(unittest.TestCase):
    """Comprueba normalizaciones conservadoras y aislamiento de empresa."""

    def test_normaliza_movil_colombiano_a_e164(self) -> None:
        """Acepta separadores frecuentes sin inventar dígitos."""
        resultado = normalizar_telefono_colombia("+57 300 123 4567")

        self.assertEqual(resultado.valor, "+573001234567")
        self.assertEqual(resultado.estado, "valido")

    def test_rechaza_texto_en_campo_telefono(self) -> None:
        """No convierte texto de prueba en una identidad utilizable."""
        resultado = normalizar_telefono_colombia("prueba prueba")

        self.assertIsNone(resultado.valor)
        self.assertEqual(resultado.estado, "caracteres_no_permitidos")

    def test_nombres_con_inicial_y_apellido_son_compatibles(self) -> None:
        """Permite una inicial solo cuando el resto da evidencia suficiente."""
        self.assertTrue(nombres_compatibles("J. Pérez", "Jose Perez"))
        self.assertFalse(nombres_compatibles("José", "Jose Perez"))
        self.assertEqual(clave_texto("  José Pérez  "), "jose perez")

    def test_id_consolidado_separa_empresas(self) -> None:
        """La misma referencia no produce el mismo lead entre empresas."""
        primero = id_consolidado("EMP-01", "3001234567")
        segundo = id_consolidado("EMP-02", "3001234567")

        self.assertNotEqual(primero, segundo)
        self.assertEqual(primero, id_consolidado("EMP-01", "3001234567"))
