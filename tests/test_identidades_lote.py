"""Conserva IDs canónicos al combinar fuentes y altas de la plataforma."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "auto-inicio-datos")
)

from utils.persistencia.config import ErrorValidacion  # noqa: E402
from utils.persistencia.identidades import conciliar_identidades  # noqa: E402


class IdentidadesLoteTest(unittest.TestCase):
    """La misma empresa es obligatoria y las ambigüedades fallan cerradas."""

    def ejecutar(self, empresa="A", nombre="Cliente Sintético"):
        cursor = MagicMock()
        cursor.__iter__.side_effect = [
            iter(
                [
                    {
                        "lead_consolidado_id": "WEB-1",
                        "empresa_id": "A",
                        "nombre_presentacion": "Cliente Sintético",
                    }
                ]
            ),
            iter(
                [
                    {
                        "lead_id_origen": "MANUAL-1",
                        "lead_consolidado_id": "WEB-1",
                        "empresa_id": "A",
                        "telefono": "+573001234567",
                    }
                ]
            ),
        ]
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        lote = SimpleNamespace(
            filas={
                "leads": [
                    {
                        "lead_consolidado_id": "FUENTE-1",
                        "empresa_id": empresa,
                        "nombre_presentacion": nombre,
                    }
                ],
                "consultas": [
                    {
                        "lead_id_origen": "FUENTE-C1",
                        "lead_consolidado_id": "FUENTE-1",
                        "empresa_id": empresa,
                        "telefono": "+573001234567",
                    }
                ],
            }
        )
        conciliar_identidades(conn, lote)
        return lote

    def test_reutiliza_canonico_y_referencia(self):
        lote = self.ejecutar()
        self.assertEqual(
            lote.filas["leads"][0]["lead_consolidado_id"], "WEB-1"
        )
        self.assertEqual(
            lote.filas["consultas"][0]["lead_consolidado_id"], "WEB-1"
        )

    def test_mismo_telefono_otra_empresa_no_fusiona(self):
        lote = self.ejecutar(empresa="B")
        self.assertEqual(
            lote.filas["leads"][0]["lead_consolidado_id"], "FUENTE-1"
        )

    def test_nombre_incompatible_requiere_revision(self):
        with self.assertRaises(ErrorValidacion):
            self.ejecutar(nombre="Otra Persona")
