"""Impide consumir trabajos antes de integrar el ejecutor individual."""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """Expone el estado pendiente sin modificar la cola durable."""

    help = "No disponible: falta integrar el ejecutor individual de T09."

    def add_arguments(self, parser):
        """Declara el tipo de tarea sin permitir ejecución ambigua."""
        parser.add_argument("--tipo", required=True)
        parser.add_argument("--lease-segundos", type=int, default=300)

    def handle(self, *args, **options):
        """Termina con error explícito sin reclamar ninguna tarea."""
        raise CommandError(
            "Ejecutor individual pendiente; no se reclamaron trabajos."
        )
