"""Migraciones privadas y carga PostgreSQL transaccional e idempotente."""

from datetime import UTC, datetime
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

from .config import (
    MIGRACIONES,
    VERSION,
    Configuracion,
    ErrorValidacion,
    huella,
)
from .plan import CLAVES, ORDEN, Lote, exigir


def conectar(config: Configuracion) -> psycopg.Connection:
    """Abre una conexión administrativa sin imprimir la URI.

    Args:
        config: Configuración validada con SSL obligatorio.

    Returns:
        Conexión con autocommit; cada operación usa transacción explícita.

    Raises:
        ErrorValidacion: Si falta URI o se intenta degradar SSL.
        psycopg.Error: Si PostgreSQL rechaza la conexión.
    """
    config.exigir_url()
    opciones = conninfo_to_dict(config.url)
    niveles = {"require": 1, "verify-ca": 2, "verify-full": 3}
    ssl_uri = opciones.get("sslmode", config.sslmode)
    if ssl_uri not in niveles:
        raise ErrorValidacion("La URI SQL contiene un modo SSL no permitido.")
    sslmode = max([ssl_uri, config.sslmode], key=niveles.__getitem__)
    return psycopg.connect(
        config.url,
        autocommit=True,
        sslmode=sslmode,
        connect_timeout=config.connect_timeout,
        prepare_threshold=None,
        application_name="prueba_ia_punto_05",
    )


def preparar_transaccion(
    conn: psycopg.Connection, config: Configuracion
) -> None:
    """Fija timeouts, esquema y bloqueo por transacción, incluso con pooler."""
    conn.execute(
        "SELECT set_config('statement_timeout', %s, true)",
        (str(config.statement_timeout),),
    )
    conn.execute("SELECT set_config('lock_timeout', %s, true)", ("15000",))
    conn.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s))",
        ("prueba_ia_05_" + config.schema,),
    )
    conn.execute(
        sql.SQL("SET LOCAL search_path TO {}, pg_catalog").format(
            sql.Identifier(config.schema)
        )
    )
    if conn.info.server_version < 150000:
        raise ErrorValidacion("El esquema requiere PostgreSQL 15 o posterior.")


def archivos_migracion() -> list[Path]:
    """Devuelve migraciones versionadas, no vacías y en orden estable."""
    paths = sorted(MIGRACIONES.glob("[0-9][0-9][0-9]_*.sql"))
    exigir(bool(paths), "No hay migraciones SQL disponibles.")
    for path in paths:
        exigir(
            bool(path.read_text(encoding="utf-8").strip()),
            "Migración SQL vacía.",
        )
    return paths


def verificar_migraciones(conn: psycopg.Connection) -> None:
    """Rechaza versiones ausentes, modificadas o desconocidas del esquema."""
    actual = dict(
        conn.execute(
            "SELECT version, sha256 FROM schema_migrations"
        ).fetchall()
    )
    esperado = {p.name: huella(p) for p in archivos_migracion()}
    exigir(
        actual == esperado,
        "Migraciones distintas: ejecutar 05_crear_db o revisar versiones.",
    )


def cerrar_acceso_publico(conn: psycopg.Connection, schema: str) -> None:
    """Deniega acceso público y activa RLS sin políticas permisivas.

    La aplicación aún no tiene identidad/roles por empresa; no se simulan.
    El propietario conserva acceso administrativo para esta carga.
    """
    esqu = sql.Identifier(schema)
    roles = ["PUBLIC"]
    roles += [
        r[0]
        for r in conn.execute(
            "SELECT rolname FROM pg_roles "
            "WHERE rolname IN ('anon', 'authenticated')"
        ).fetchall()
    ]
    for rol in roles:
        receptor = (
            sql.SQL("PUBLIC") if rol == "PUBLIC" else sql.Identifier(rol)
        )
        for template in [
            "REVOKE ALL ON SCHEMA {} FROM {}",
            "REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM {}",
            "REVOKE ALL ON ALL SEQUENCES IN SCHEMA {} FROM {}",
            "ALTER DEFAULT PRIVILEGES IN SCHEMA {} "
            "REVOKE ALL ON TABLES FROM {}",
            "ALTER DEFAULT PRIVILEGES IN SCHEMA {} "
            "REVOKE ALL ON SEQUENCES FROM {}",
        ]:
            conn.execute(sql.SQL(template).format(esqu, receptor))
    for tabla in [*CLAVES, "schema_migrations"]:
        conn.execute(
            sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(
                sql.Identifier(schema, tabla)
            )
        )


def crear_esquema(config: Configuracion) -> dict:
    """Aplica migraciones en una transacción, sin recrear bases ni tablas."""
    aplicadas = []
    with conectar(config) as conn, conn.transaction():
        preparar_transaccion(conn, config)
        conn.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(config.schema)
            )
        )
        existentes = {
            r[0]
            for r in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = %s",
                (config.schema,),
            ).fetchall()
        }
        if existentes and "schema_migrations" not in existentes:
            raise ErrorValidacion(
                "El esquema ya contiene tablas sin registro de migraciones."
            )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version text PRIMARY KEY,
                sha256 text NOT NULL,
                aplicada_en timestamptz NOT NULL DEFAULT clock_timestamp()
            )
        """)
        actual = dict(
            conn.execute(
                "SELECT version, sha256 FROM schema_migrations"
            ).fetchall()
        )
        archivos = archivos_migracion()
        exigir(
            set(actual) <= {p.name for p in archivos},
            "La base contiene migraciones desconocidas para este código.",
        )
        for path in archivos:
            digest = huella(path)
            if path.name in actual:
                exigir(
                    actual[path.name] == digest,
                    "Una migración aplicada fue modificada; crear otra.",
                )
                continue
            conn.execute(path.read_text(encoding="utf-8"), prepare=False)
            conn.execute(
                "INSERT INTO schema_migrations (version, sha256) "
                "VALUES (%s, %s)",
                (path.name, digest),
            )
            aplicadas.append(path.name)
        cerrar_acceso_publico(conn, config.schema)
        verificar_migraciones(conn)
        tablas = {
            r[0]
            for r in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = %s",
                (config.schema,),
            ).fetchall()
        }
        exigir(
            {*CLAVES, "schema_migrations"} <= tablas,
            "Faltan tablas requeridas del esquema histórico.",
        )
    return {
        "estado": "esquema_verificado",
        "schema": config.schema,
        "migraciones_aplicadas": aplicadas,
        "tablas_dominio": len(CLAVES),
        "tablas_tecnicas": 1,
    }


def columnas_json(
    conn: psycopg.Connection, schema: str, tabla: str
) -> set[str]:
    """Identifica columnas JSONB para adaptar incluso escalares y nulos."""
    return {
        r[0]
        for r in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s "
            "AND data_type = 'jsonb'",
            (schema, tabla),
        ).fetchall()
    }


def escribir_tabla(
    conn: psycopg.Connection,
    schema: str,
    tabla: str,
    filas: list[dict],
) -> None:
    """Inserta o actualiza por claves estables, sin cambiar propietarios.

    Las filas históricas de ejecuciones no se reescriben: sus marcas de
    registro determinan cuál clasificación completa es la vigente.
    """
    if not filas:
        return
    claves = CLAVES[tabla]
    columnas = list(filas[0])
    exigir(
        all(set(r) == set(columnas) for r in filas),
        f"Filas con contratos distintos en {tabla}.",
    )
    cambios = [c for c in columnas if c not in claves and c != "empresa_id"]
    sentencia = sql.SQL(
        "INSERT INTO {} AS destino ({}) VALUES ({}) ON CONFLICT ({}) "
    ).format(
        sql.Identifier(schema, tabla),
        sql.SQL(", ").join(map(sql.Identifier, columnas)),
        sql.SQL(", ").join(sql.Placeholder() for _ in columnas),
        sql.SQL(", ").join(map(sql.Identifier, claves)),
    )
    if cambios and tabla != "ejecuciones":
        sentencia += sql.SQL("DO UPDATE SET ") + sql.SQL(", ").join(
            sql.SQL("{} = EXCLUDED.{}").format(
                sql.Identifier(c), sql.Identifier(c)
            )
            for c in cambios
        )
        if "empresa_id" in columnas:
            sentencia += sql.SQL(
                " WHERE destino.empresa_id "
                "IS NOT DISTINCT FROM EXCLUDED.empresa_id"
            )
    else:
        sentencia += sql.SQL("DO NOTHING")
    jsons = columnas_json(conn, schema, tabla)
    with conn.cursor() as cursor:
        for inicio in range(0, len(filas), 500):
            valores = [
                tuple(
                    Jsonb(r[c]) if c in jsons and r[c] is not None else r[c]
                    for c in columnas
                )
                for r in filas[inicio : inicio + 500]
            ]
            cursor.executemany(sentencia, valores)


def reconciliar_tabla(
    conn: psycopg.Connection,
    schema: str,
    tabla: str,
    filas: list[dict],
) -> int:
    """Compara todas las columnas cargadas contra su representación SQL."""
    if not filas:
        return 0
    columnas = list(filas[0])
    resultado = conn.execute(
        sql.SQL("SELECT {} FROM {}").format(
            sql.SQL(", ").join(map(sql.Identifier, columnas)),
            sql.Identifier(schema, tabla),
        )
    ).fetchall()
    claves = CLAVES[tabla]
    actual = {}
    for valores in resultado:
        row = dict(zip(columnas, valores, strict=True))
        actual[tuple(row[k] for k in claves)] = row
    for esperado in filas:
        clave = tuple(esperado[k] for k in claves)
        exigir(
            actual.get(clave) == esperado,
            f"Falló la conciliación de valores/propietario en {tabla}.",
        )
    return len(filas)


def verificar_base_operativa(conn: psycopg.Connection, lote: Lote) -> None:
    """Rechaza desapariciones silenciosas de entidades de una foto completa."""
    for tabla in [
        "empresas",
        "puntos_venta",
        "asesores",
        "marcas",
        "modelos_moto",
        "disponibilidad_modelo",
        "leads",
        "consultas",
        "conversaciones",
        "mensajes",
        "historico_cierres",
    ]:
        claves = CLAVES[tabla]
        origen = (
            sql.SQL(" WHERE origen_registro = 'lote'")
            if tabla in {"leads", "consultas"}
            else sql.SQL("")
        )
        actuales = set(
            conn.execute(
                sql.SQL("SELECT {} FROM {}{}").format(
                    sql.SQL(", ").join(map(sql.Identifier, claves)),
                    sql.Identifier(tabla),
                    origen,
                )
            ).fetchall()
        )
        nuevas = {tuple(r[k] for k in claves) for r in lote.filas[tabla]}
        exigir(
            actuales <= nuevas,
            f"La fuente omite registros ya existentes de {tabla}; "
            "se requiere una política explícita de bajas.",
        )


def cargar_lote(config: Configuracion, lote: Lote) -> dict:
    """Persiste el lote y comprueba lectura antes de confirmar el COMMIT."""
    with conectar(config) as conn, conn.transaction():
        preparar_transaccion(conn, config)
        verificar_migraciones(conn)
        verificar_base_operativa(conn, lote)
        anterior = conn.execute(
            "SELECT estado FROM ejecuciones WHERE ejecucion_id = %s",
            (lote.ejecucion_id,),
        ).fetchone()
        if anterior and anterior[0] == "completada":
            for tabla in ORDEN:
                reconciliar_tabla(
                    conn, config.schema, tabla, lote.filas[tabla]
                )
            return {**lote.resumen(), "estado": "ya_cargado_y_verificado"}
        inicio = datetime.now(UTC)
        ejecucion_carga = {
            "ejecucion_id": lote.ejecucion_id,
            "etapa": "carga_sql",
            "version_codigo": VERSION,
            "huella_entrada": lote.ejecucion_id,
            "importada": False,
            "inicio": inicio,
            "fin": inicio,
            "estado": "en_curso",
            "configuracion": {
                "fuentes_sha256": lote.fuentes.hashes,
            },
            "conteos": lote.resumen()["conteos"],
            "errores": [],
        }
        escribir_tabla(conn, config.schema, "ejecuciones", [ejecucion_carga])
        for tabla in ORDEN:
            escribir_tabla(conn, config.schema, tabla, lote.filas[tabla])
            reconciliar_tabla(conn, config.schema, tabla, lote.filas[tabla])
        mal = conn.execute(
            """
            SELECT count(*) FROM priorizaciones p
            JOIN conversaciones c
                ON c.conversacion_id = p.conversacion_id_contexto
            WHERE p.ejecucion_id = %s AND c.descartada
        """,
            (lote.etapas["clasificacion"],),
        ).fetchone()[0]
        exigir(
            mal == 0,
            "Una prioridad vigente utiliza una conversación descartada.",
        )
        total = conn.execute(
            "SELECT count(*) FROM priorizaciones WHERE ejecucion_id = %s",
            (lote.etapas["clasificacion"],),
        ).fetchone()[0]
        exigir(
            total == len(lote.filas["priorizaciones"]),
            "La clasificación importada no coincide con sus prioridades.",
        )
        conn.execute(
            "UPDATE ejecuciones SET estado = 'completada', fin = %s "
            "WHERE ejecucion_id = %s",
            (datetime.now(UTC), lote.ejecucion_id),
        )
    return {**lote.resumen(), "estado": "cargado_y_verificado"}
