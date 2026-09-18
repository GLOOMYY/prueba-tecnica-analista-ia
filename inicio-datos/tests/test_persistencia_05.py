"""Pruebas locales de contratos de carga; nunca conectan a Supabase."""

import copy
import json
import sys
import unittest
from datetime import date, time
from decimal import Decimal
from pathlib import Path

from pglast import parse_sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs/modelo_datos"))

from persistencia.config import ErrorValidacion, identidad  # noqa: E402
from persistencia.fuentes import (  # noqa: E402
    booleano,
    entero,
    numero,
    temporal,
)
from persistencia.plan import (  # noqa: E402
    CLAVES,
    Lote,
    preparar_clientes,
    preparar_conversaciones,
    preparar_lote,
    preparar_prioridades,
    verificar_evidencias,
)


class ContratosBasicos(unittest.TestCase):
    """Distingue desconocidos, valores explícitos y formatos inválidos."""

    def test_cero_no_es_ausencia(self):
        self.assertIsNone(numero(""))
        self.assertEqual(numero("0"), Decimal("0"))
        self.assertEqual(entero("3.0"), 3)
        with self.assertRaises(ErrorValidacion):
            entero("3.5")
        with self.assertRaises(ErrorValidacion):
            numero("NaN")

    def test_booleanos_de_la_fuente(self):
        self.assertIs(booleano("NO"), False)
        self.assertIs(booleano("False"), False)
        self.assertIs(booleano("SI"), True)
        self.assertIsNone(booleano(""))
        with self.assertRaises(ErrorValidacion):
            booleano("tal vez")

    def test_fecha_sin_hora_no_recibe_medianoche(self):
        salida = temporal("fecha", "2026-08-25")
        self.assertEqual(salida["fecha"], date(2026, 8, 25))
        self.assertIsNone(salida["fecha_hora"])
        salida = temporal("fecha", "2026-08-25 00:00:00", "fecha")
        self.assertIsNone(salida["fecha_hora"])
        salida = temporal("fecha", "2026-08-25 00:00:00", "fecha_hora")
        self.assertEqual(salida["fecha_hora"], time(0, 0))
        with self.assertRaises(ErrorValidacion):
            temporal("fecha", "08/25/2026")

    def test_evidencia_no_puede_cambiar_emisor(self):
        mensajes = [{"emisor": "asesor", "texto": "Le ofrezco crédito"}]
        cita = {"mensaje": 1, "emisor": "cliente", "texto": "crédito"}
        with self.assertRaises(ErrorValidacion):
            verificar_evidencias(cita, mensajes)
        cita["emisor"] = "asesor"
        verificar_evidencias(cita, mensajes)

    def test_identidades_estables_sin_fusionar_empresas(self):
        self.assertEqual(
            identidad("EMP-01", "persona"), identidad("EMP-01", "persona")
        )
        self.assertNotEqual(
            identidad("EMP-01", "persona"), identidad("EMP-02", "persona")
        )

    def test_sintaxis_postgresql_y_veinte_tablas(self):
        path = ROOT / "docs/modelo_datos/migrations/001_inicial.sql"
        statements = parse_sql(path.read_text(encoding="utf-8"))
        tablas = {
            s.stmt.relation.relname
            for s in statements
            if type(s.stmt).__name__ == "CreateStmt"
        }
        self.assertEqual(tablas, set(CLAVES))


class ContratosLote(unittest.TestCase):
    """Verifica integridad contra los artefactos existentes del proyecto."""

    @classmethod
    def setUpClass(cls):
        """Prepara una sola instantánea local sin conectarse a la base."""
        cls.lote = preparar_lote(ROOT)

    def test_particion_sin_perdidas(self):
        filas = self.lote.filas
        fuentes = self.lote.fuentes
        externas = [
            r
            for r in self.lote.revision
            if r["tipo"] == "conversacion_sin_vinculo"
        ]
        self.assertEqual(
            len(filas["conversaciones"]) + len(externas),
            len(fuentes.lista("conversaciones.json")),
        )
        self.assertEqual(
            len(filas["extracciones_ia"]), len(filas["conversaciones"])
        )
        self.assertEqual(len(filas["priorizaciones"]), len(filas["leads"]))
        huérfanas = {r["conversacion"]["conversacion_id"] for r in externas}
        contenido_db = json.dumps(filas, ensure_ascii=False, default=str)
        self.assertTrue(all(cid not in contenido_db for cid in huérfanas))

    def test_descartadas_con_motivos_no_son_contexto_activo(self):
        descartadas = {
            r["conversacion_id"]
            for r in self.lote.filas["conversaciones"]
            if r["descartada"]
        }
        for r in self.lote.filas["conversaciones"]:
            if r["descartada"]:
                self.assertTrue(r["motivos_descarte"])
                self.assertIsNone(r["fecha_descarte"])
        for r in self.lote.filas["priorizaciones"]:
            self.assertNotIn(r["conversacion_id_contexto"], descartadas)

    def test_rechaza_consulta_cruzada(self):
        fuentes = copy.deepcopy(self.lote.fuentes)
        fuentes.lista("consultas_leads.csv")[0]["empresa_id"] = "EMP-OTRA"
        lote = Lote(fuentes)
        lote.filas["modelos_moto"] = self.lote.filas["modelos_moto"]
        with self.assertRaises(ErrorValidacion):
            preparar_clientes(lote)

    def test_rechaza_prioridad_con_lead_de_otra_empresa(self):
        lote = copy.deepcopy(self.lote)
        lote.fuentes.lista("priorizacion_leads.json")[0]["empresa_id"] = "OTRA"
        with self.assertRaises(ErrorValidacion):
            preparar_prioridades(lote, "modelo_de_prueba")

    def test_cruce_de_conversacion_va_a_revision_externa(self):
        lote = copy.deepcopy(self.lote)
        c = lote.fuentes.lista("conversaciones_utilizables_ia.json")[0]
        cid = c["conversacion_id"]
        c["empresa_id"] = "EMP-OTRA"
        for fila in lote.fuentes.lista("conversaciones.json"):
            if fila["conversacion_id"] == cid:
                fila["empresa_id"] = "EMP-OTRA"
        for tabla in [
            "conversaciones",
            "mensajes",
            "extracciones_ia",
            "intereses_modelo",
        ]:
            lote.filas[tabla] = []
        lote.revision = []
        externas = preparar_conversaciones(lote)
        self.assertIn(cid, externas)
        self.assertNotIn(
            cid, {r["conversacion_id"] for r in lote.filas["conversaciones"]}
        )

    def test_historico_sin_gestion_se_conserva(self):
        esperado = sum(
            r["desenlace"] == "Sin gestión"
            for r in self.lote.fuentes.lista("historico_cierres.csv")
        )
        actual = sum(
            r["desenlace"] == "Sin gestión"
            for r in self.lote.filas["historico_cierres"]
        )
        self.assertEqual(actual, esperado)

    def test_plan_repetido_conserva_claves_y_contenido(self):
        repetido = preparar_lote(ROOT)
        self.assertEqual(repetido.ejecucion_id, self.lote.ejecucion_id)
        self.assertEqual(repetido.filas, self.lote.filas)


if __name__ == "__main__":
    unittest.main()
