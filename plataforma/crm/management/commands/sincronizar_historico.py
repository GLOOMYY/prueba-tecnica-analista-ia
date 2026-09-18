"""Inicializa estados operativos desde las prioridades históricas."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from crm.contexto_empresa import transaccion_empresa


class Command(BaseCommand):
    """Hace visibles los leads históricos después de instalar Django."""

    help = "Sincroniza estados de una empresa después de migrar Django."

    def add_arguments(self, parser):
        """Exige ámbito explícito también para credenciales administrativas."""
        parser.add_argument("--empresa", required=True)

    def handle(self, *args, **options):
        """Activa el trigger sin modificar la prioridad histórica publicada."""
        if connection.vendor != "postgresql":
            raise CommandError("La sincronización requiere PostgreSQL.")
        with transaccion_empresa(options["empresa"]):
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE prioridades_publicadas SET origen = origen "
                    "WHERE empresa_id = %s",
                    [options["empresa"]],
                )
                cantidad = cursor.rowcount
        self.stdout.write(f"Estados sincronizados: {cantidad}.")
