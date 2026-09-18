"""Protege publicación de prioridades y finalización de trabajos."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Añade datos de control sin alterar la historia de tablas fuente."""

    dependencies = [("crm", "0002_rls_empresa")]

    operations = [
        migrations.AddField(
            model_name="estadooperativolead",
            name="priorizacion_origen",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="estadooperativolead",
            name="priorizacion_revision_entrada",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="trabajoprocesamiento",
            name="lease_token",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="trabajoprocesamiento",
            name="huella_entrada",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
