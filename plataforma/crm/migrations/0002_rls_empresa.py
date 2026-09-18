"""Activa aislamiento por empresa para las tablas operativas en PostgreSQL."""

from django.db import migrations


TABLAS_CON_EMPRESA = (
    "crm_asignaciondiaria",
    "crm_capturaestructurada",
    "crm_capturarevision",
    "crm_estadooperativolead",
    "crm_eventoauditoria",
    "crm_gestioncomercial",
    "crm_solicitudidempotente",
    "crm_trabajoprocesamiento",
)
NOMBRE_POLITICA = "crm_empresa_aislada"


def aplicar_rls_empresa(apps, schema_editor):
    """Protege tablas CRM por el contexto SQL local de empresa.

    SQLite se conserva para pruebas locales de modelos. La política PostgreSQL
    depende de ``crm.contexto_empresa.transaccion_empresa`` y se aplica con
    ``FORCE`` para que el propietario tampoco eluda RLS accidentalmente.
    """
    if schema_editor.connection.vendor != "postgresql":
        return

    for tabla in TABLAS_CON_EMPRESA:
        identificador = schema_editor.quote_name(tabla)
        schema_editor.execute(
            f"ALTER TABLE {identificador} ENABLE ROW LEVEL SECURITY"
        )
        schema_editor.execute(
            f"ALTER TABLE {identificador} FORCE ROW LEVEL SECURITY"
        )
        schema_editor.execute(
            f"DROP POLICY IF EXISTS {NOMBRE_POLITICA} ON {identificador}"
        )
        schema_editor.execute(
            f"""
            CREATE POLICY {NOMBRE_POLITICA} ON {identificador}
            USING (
                current_setting('app.empresa_id', true) IS NOT NULL
                AND empresa_id = current_setting('app.empresa_id', true)
            )
            WITH CHECK (
                current_setting('app.empresa_id', true) IS NOT NULL
                AND empresa_id = current_setting('app.empresa_id', true)
            )
            """
        )


def retirar_rls_empresa(apps, schema_editor):
    """Retira las políticas creadas por esta migración al revertirla."""
    if schema_editor.connection.vendor != "postgresql":
        return

    for tabla in TABLAS_CON_EMPRESA:
        identificador = schema_editor.quote_name(tabla)
        schema_editor.execute(
            f"DROP POLICY IF EXISTS {NOMBRE_POLITICA} ON {identificador}"
        )
        schema_editor.execute(
            f"ALTER TABLE {identificador} NO FORCE ROW LEVEL SECURITY"
        )
        schema_editor.execute(
            f"ALTER TABLE {identificador} DISABLE ROW LEVEL SECURITY"
        )


class Migration(migrations.Migration):
    """Añade políticas RLS sin cambiar el estado del ORM."""

    dependencies = [
        ("crm", "0001_modelo_operativo_inicial"),
    ]

    operations = [
        migrations.RunPython(aplicar_rls_empresa, retirar_rls_empresa),
    ]
