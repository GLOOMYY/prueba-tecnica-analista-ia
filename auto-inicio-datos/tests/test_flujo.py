"""Pruebas de fallos, reanudación y disparo sin API ni base de datos."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

AUTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AUTO))

from utils import flujo  # noqa: E402
from utils.archivos import guardar_json, huella  # noqa: E402
from utils.reglas_normalizacion import (  # noqa: E402
    fecha_exportable,
    id_consolidado,
    normalizar_fecha,
    normalizar_telefono,
)
from utils.reglas_priorizacion import (  # noqa: E402
    elegir_ultima,
    inicial_de_extraccion,
    score_reglas,
)


class Orquestacion(unittest.TestCase):
    """Verifica garantías operativas con archivos temporales."""

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.root = Path(self.temporal.name)
        self.origen = self.root / "data/raw"
        self.origen.mkdir(parents=True)
        for nombre in flujo.FUENTES:
            (self.origen / nombre).write_text("fuente", encoding="utf-8")
        self.identidad = {
            "fuentes": {n: huella(self.origen / n) for n in flujo.FUENTES}
        }
        self.parches = [
            patch.object(flujo, "AUTO", self.root),
            patch.object(flujo, "entradas", return_value=self.identidad),
        ]
        for parche in self.parches:
            parche.start()
        self.llamadas = []
        self.fallo = None

    def tearDown(self):
        for parche in reversed(self.parches):
            parche.stop()
        self.temporal.cleanup()

    def simular(self, cmd, check):
        """Simula salidas de etapas, nunca ejecuta servicios externos."""
        etapa = Path(cmd[1]).name[:2]
        self.llamadas.append(etapa)
        if etapa == self.fallo:
            return SimpleNamespace(returncode=1)
        root = Path(cmd[3])
        guardar_json(root / f"data/processed/etapa_{etapa}.json", {"ok": True})
        return SimpleNamespace(returncode=0)

    def test_fallo_detiene_y_reanuda(self):
        self.fallo = "03"
        with patch.object(flujo.subprocess, "run", side_effect=self.simular):
            primero = flujo.ejecutar(self.origen, True, False)
            self.assertEqual(primero["estado"], "fallida")
            self.assertEqual(self.llamadas, ["01", "02", "03"])
            self.assertFalse((self.root / "ultima_exitosa.json").exists())
            self.fallo = None
            self.llamadas.clear()
            segundo = flujo.ejecutar(self.origen, True, False)
        self.assertEqual(segundo["estado"], "completada")
        self.assertEqual(self.llamadas, ["03", "04", "05"])

    def test_validacion_no_publica_exito_sql(self):
        with patch.object(flujo.subprocess, "run", side_effect=self.simular):
            resultado = flujo.ejecutar(self.origen, True, True)
        self.assertEqual(resultado["estado"], "validada_sin_db")
        self.assertFalse((self.root / "ultima_exitosa.json").exists())

    def test_producto_alterado_invalida_checkpoint(self):
        with patch.object(flujo.subprocess, "run", side_effect=self.simular):
            primero = flujo.ejecutar(self.origen, True, False)
            root = self.root / "ejecuciones" / primero["id"]
            (root / "data/processed/etapa_02.json").write_text("alterado")
            self.llamadas.clear()
            flujo.ejecutar(self.origen, True, False)
        self.assertEqual(self.llamadas, ["02", "03", "04", "05"])

    def test_fuente_cambia_durante_copia(self):
        self.identidad["fuentes"]["leads.csv"] = "hash_distinto"
        with self.assertRaises(ValueError):
            flujo.ejecutar(self.origen, True, False)

    def test_bloqueo_impide_segunda_ejecucion(self):
        with flujo.bloqueo(self.root / ".lock"):
            with self.assertRaises(OSError):
                with flujo.bloqueo(self.root / ".lock"):
                    self.fail("Se adquirió dos veces el bloqueo.")
        with flujo.bloqueo(self.root / ".lock"):
            pass

    def test_watch_dispara_solo_tras_cambio_estable(self):
        estados = [{"v": 1}, {"v": 1}, {"v": 2}, {"v": 2}]
        resultado = {"estado": "completada", "id": "prueba"}
        with (
            patch.object(
                sys, "argv", ["run.py", "--watch", "--intervalo", "5"]
            ),
            patch.object(flujo, "entradas", side_effect=estados),
            patch.object(
                flujo, "ejecutar", return_value=resultado
            ) as ejecutar,
            patch.object(
                flujo.time,
                "sleep",
                side_effect=[None, None, None, KeyboardInterrupt],
            ),
        ):
            self.assertEqual(flujo.main(), 130)
        self.assertEqual(ejecutar.call_count, 2)


class Preservacion(unittest.TestCase):
    """Comprueba la independencia del runtime respecto a Jupyter."""

    def test_runtime_no_lee_notebooks(self):
        for path in (AUTO / "utils").rglob("*.py"):
            contenido = path.read_text(encoding="utf-8")
            self.assertNotIn("import nbformat", contenido)
            self.assertNotIn("NotebookClient", contenido)
            self.assertNotIn("from IPython", contenido)

    def test_particion_carga_completa(self):
        candidatas = list((AUTO / "ejecuciones").glob("*/ejecucion.json"))
        completas = [
            json.loads(p.read_text(encoding="utf-8")) for p in candidatas
        ]
        completas = [
            e
            for e in completas
            if e["estado"] in ("completada", "validada_sin_db")
        ]
        if not completas:
            self.skipTest("Ejecutar primero run.py --sin-api --sin-db.")
        estado = max(completas, key=lambda e: e["inicio"])
        root = AUTO / "ejecuciones" / estado["id"]
        resumen = json.loads((root / "resultado_05.json").read_text("utf-8"))
        self.assertEqual(resumen["conteos"]["leads"], 1451)
        self.assertEqual(resumen["conteos"]["conversaciones"], 665)


class ReglasNegocio(unittest.TestCase):
    """Casos sintéticos que protegen las decisiones del usuario."""

    def test_identidad_separada_por_empresa(self):
        self.assertNotEqual(
            id_consolidado("EMP-01", "3001234567"),
            id_consolidado("EMP-02", "3001234567"),
        )

    def test_fecha_valida_invertida_y_precision(self):
        fecha, estado, precision, _ = normalizar_fecha("08/18/2026", "MDY")
        self.assertEqual(estado, "valida")
        self.assertEqual(fecha_exportable(fecha, precision), "2026-08-18")
        _, estado, _, motivo = normalizar_fecha("31/02/2026")
        self.assertEqual(estado, "invalida")
        self.assertIn("imposible", motivo)

    def test_fecha_sin_hora_no_define_orden_intradia(self):
        posicion, motivo = elegir_ultima(["2026-08-18", "2026-08-18 14:00:00"])
        self.assertIsNone(posicion)
        self.assertEqual(motivo, "orden_intradia_desconocido")

    def test_cero_explicito_distinto_de_ausencia(self):
        ex = {
            "dinero": {
                "cuota_inicial": {"evidencias": [], "valor": 0, "minimo": None}
            }
        }
        self.assertEqual(inicial_de_extraccion(ex), "NO_INFORMA")
        ex["dinero"]["cuota_inicial"]["evidencias"] = [{"texto": "no tengo"}]
        self.assertEqual(inicial_de_extraccion(ex), "NO")

    def test_telefono_como_texto(self):
        telefono, estado = normalizar_telefono("+57 300 123 4567")
        self.assertEqual(estado, "valido")
        self.assertIsInstance(telefono, str)

    def test_reglas_compartidas_conservan_el_score_del_lote(self):
        """Protege la paridad entre el flujo y el módulo de dominio."""
        entradas = pd.DataFrame(
            [
                {
                    "modelo_sku": "HON-125",
                    "manifesto_cuota_inicial": "SI",
                    "forma_pago_declarada": "credito",
                    "cita_observada": "SI",
                },
                {
                    "modelo_sku": "DESCONOCIDO",
                    "manifesto_cuota_inicial": "NO_INFORMA",
                    "forma_pago_declarada": "mixto",
                    "cita_observada": "NO_OBSERVADA",
                },
            ]
        )

        self.assertEqual(score_reglas(entradas).tolist(), [1.0, 0.0])


if __name__ == "__main__":
    unittest.main()
