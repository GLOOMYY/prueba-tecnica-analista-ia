"""Pruebas de la decisión pura para altas manuales."""

import unittest
from decimal import Decimal

from dominio.alta import (
    CandidatoIdentidad,
    EntradaAlta,
    EstadoResolucionIdentidad,
    preparar_alta,
    resolver_identidad,
)


class AltaDominioTest(unittest.TestCase):
    """Comprueba contactos, prioridad y decisiones sin base de datos."""

    def test_conserva_telefono_invalido_si_hay_correo(self) -> None:
        """El teléfono se conserva como incidencia y no impide contactar."""
        preparada = preparar_alta(
            EntradaAlta(
                empresa_id="EMP-01",
                nombre_cliente="  Ana Pérez ",
                telefono="prueba prueba",
                correo="Ana@Ejemplo.co",
                cuota_inicial=Decimal("100000"),
            )
        )

        self.assertEqual(preparada.nombre_cliente, "Ana Pérez")
        self.assertEqual(preparada.correo, "ana@ejemplo.co")
        self.assertEqual(
            preparada.incidencias, ("telefono:caracteres_no_permitidos",)
        )
        self.assertEqual(preparada.prioridad.puntos, 30)

    def test_rechaza_alta_sin_contacto_utilizable(self) -> None:
        """No crea un lead interactivo imposible de contactar."""
        with self.assertRaisesRegex(ValueError, "teléfono utilizable"):
            preparar_alta(
                EntradaAlta(
                    empresa_id="EMP-01",
                    nombre_cliente="Ana Pérez",
                    telefono="prueba prueba",
                    correo=None,
                )
            )

    def test_rechaza_correo_malformado_aun_con_telefono_valido(self) -> None:
        """Evita persistir un correo que el usuario debe corregir."""
        with self.assertRaisesRegex(ValueError, "correo no tiene"):
            preparar_alta(
                EntradaAlta(
                    empresa_id="EMP-01",
                    nombre_cliente="Ana Pérez",
                    telefono="3001234567",
                    correo="correo sin formato",
                )
            )

    def test_coincidencia_visible_agrega_consulta(self) -> None:
        """Un único candidato visible se reutiliza dentro de su empresa."""
        resultado = resolver_identidad(
            "EMP-01",
            (
                CandidatoIdentidad(
                    empresa_id="EMP-01",
                    lead_consolidado_id="LC-001",
                    visible_para_actor=True,
                ),
            ),
        )

        self.assertEqual(
            resultado.estado, EstadoResolucionIdentidad.CONSULTA_EXISTENTE
        )
        self.assertEqual(resultado.lead_consolidado_id, "LC-001")

    def test_coincidencia_ajena_pasa_a_revision_sin_id(self) -> None:
        """El asesor no recibe datos ni identificador de una cartera ajena."""
        resultado = resolver_identidad(
            "EMP-01",
            (
                CandidatoIdentidad(
                    empresa_id="EMP-01",
                    lead_consolidado_id="LC-001",
                    visible_para_actor=False,
                ),
            ),
        )

        self.assertEqual(
            resultado.estado, EstadoResolucionIdentidad.REVISION_REQUERIDA
        )
        self.assertIsNone(resultado.lead_consolidado_id)
        self.assertEqual(resultado.motivo, "coincidencia_fuera_de_cartera")

    def test_candidato_de_otra_empresa_es_error_de_adaptador(self) -> None:
        """La resolución no permite que el borde mezcle empresas."""
        with self.assertRaisesRegex(ValueError, "empresa activa"):
            resolver_identidad(
                "EMP-01",
                (
                    CandidatoIdentidad(
                        empresa_id="EMP-02",
                        lead_consolidado_id="LC-001",
                        visible_para_actor=True,
                    ),
                ),
            )
