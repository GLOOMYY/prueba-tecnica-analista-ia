"""Ejecuta una unidad durable de extracción sin procesar lotes completos."""

from django.core.management.base import BaseCommand, CommandError

from crm.contexto_empresa import transaccion_empresa
from crm.services.extraccion_ia import procesar_extraccion
from crm.services.trabajos import reclamar_siguiente


class Command(BaseCommand):
    """Reclama y procesa una unidad, respetando lease y revisión de entrada."""

    help = "Procesa una tarea durable de extracción individual."

    def add_arguments(self, parser):
        """Declara el tipo y duración del lease de una ejecución única."""
        parser.add_argument("--tipo", choices=["extraer_ia"], required=True)
        parser.add_argument("--lease-segundos", type=int, default=300)
        parser.add_argument("--empresa", required=True)

    def handle(self, *args, **options):
        """Procesa el trabajo reclamado y falla al agotar sus reintentos."""
        with transaccion_empresa(options["empresa"]):
            trabajo = reclamar_siguiente(
                tipo_trabajo=options["tipo"],
                lease_segundos=options["lease_segundos"],
                empresa_id=options["empresa"],
            )
        if trabajo is None:
            self.stdout.write("No hay trabajos disponibles.")
            return
        resultado = procesar_extraccion(trabajo)
        self.stdout.write(f"Trabajo {trabajo.trabajo_id}: {resultado}.")
        if resultado == "fallido":
            raise CommandError("El trabajo agotó sus reintentos.")
