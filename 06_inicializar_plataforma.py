"""Inicializa SQL, Django, rol restringido y tres usuarios de evaluación.

Ejecutar desde la raíz: python 06_inicializar_plataforma.py --aplicar
Las contraseñas nuevas se guardan únicamente en local-private/usuarios.md.
"""

import argparse
import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
from dotenv import dotenv_values, set_key
from psycopg import sql

RAIZ = Path(__file__).resolve().parent


def crear_usuarios(empresa_ids: list[str], destino: Path) -> int:
    """Crea un supervisor por empresa y conserva los accesos existentes."""
    from cuentas.models import MembresiaEmpresa, Usuario
    from django.db import transaction

    if len(empresa_ids) != 3:
        raise ValueError("La inicialización espera exactamente tres empresas.")
    altas = []
    with transaction.atomic():
        for empresa in empresa_ids:
            nombre = "evaluador_" + re.sub(r"[^a-z0-9_]", "_", empresa.lower())
            usuario, nuevo = Usuario.objects.get_or_create(username=nombre)
            if usuario.membresias.exclude(empresa_id=empresa).exists():
                raise ValueError(
                    "Un usuario inicial pertenece a otra empresa."
                )
            if nuevo:
                password = secrets.token_urlsafe(24)
                usuario.set_password(password)
                usuario.save(update_fields=["password"])
                altas.append((nombre, empresa, password))
            MembresiaEmpresa.objects.get_or_create(
                usuario=usuario,
                empresa_id=empresa,
                defaults={"rol": "supervisor", "activa": True},
            )
        if altas:
            destino.parent.mkdir(parents=True, exist_ok=True)
            previo = (
                destino.read_text(encoding="utf-8")
                if destino.exists()
                else (
                    "# Accesos privados de evaluación\n\n"
                    "No publicar ni adjuntar al repositorio. "
                    "Entrada: /accounts/login/.\n\n"
                    "| Usuario | Empresa | Contraseña inicial |\n"
                    "|---|---|---|\n"
                )
            )
            temporal = destino.with_suffix(".tmp")
            temporal.write_text(
                previo
                + "".join(
                    f"| {nombre} | {empresa} | `{password}` |\n"
                    for nombre, empresa, password in altas
                ),
                encoding="utf-8",
            )
            temporal.replace(destino)
    return len(altas)


def inicializar() -> None:
    """Aplica migraciones y verifica la conexión restringida."""
    sys.path[:0] = [
        str(RAIZ),
        str(RAIZ / "auto-inicio-datos"),
        str(RAIZ / "plataforma"),
    ]
    from utils.persistencia.config import Configuracion
    from utils.persistencia.db import conectar, crear_esquema

    configuracion = Configuracion.leer()
    crear_esquema(configuracion)
    os.environ["DJANGO_DATABASE_URL"] = configuracion.url
    os.environ["DJANGO_DB_SCHEMA"] = configuracion.schema
    os.environ["DJANGO_SETTINGS_MODULE"] = "plataforma.settings"
    import django

    django.setup()
    from django.core.management import call_command
    from django.db import connection
    from psycopg.conninfo import conninfo_to_dict

    call_command("migrate", verbosity=0, interactive=False)
    rol = "plataforma_web"
    valores = dotenv_values(RAIZ / ".env")
    url_web = valores.get("DJANGO_DATABASE_URL")
    with conectar(configuracion) as conn, conn.transaction():
        existe = conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", [rol])
        if not existe.fetchone():
            password = secrets.token_urlsafe(36)
            conn.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT NOBYPASSRLS"
                ).format(sql.Identifier(rol), sql.Literal(password))
            )
            partes = urlsplit(configuracion.url)
            sufijo = (partes.username or "").partition(".")[2]
            usuario_sql = rol + ("." + sufijo if sufijo else "")
            host = partes.hostname
            if partes.port:
                host += f":{partes.port}"
            url_web = urlunsplit(
                (
                    partes.scheme,
                    f"{quote(usuario_sql)}:{quote(password)}@{host}",
                    partes.path,
                    partes.query,
                    "",
                )
            )
        elif not url_web:
            raise ValueError(
                "El rol ya existe: configure su DJANGO_DATABASE_URL. "
                "No se rota una contraseña existente automáticamente."
            )
        permisos = (
            (RAIZ / "plataforma/crm/sql/roles_postgresql.sql")
            .read_text(encoding="utf-8")
            .replace("SCHEMA crm", f'SCHEMA "{configuracion.schema}"')
            .replace(
                "TO crm, pg_catalog",
                f'TO "{configuracion.schema}", pg_catalog',
            )
        )
        conn.execute(permisos, prepare=False)
        empresas = [
            fila[0]
            for fila in conn.execute(
                sql.SQL(
                    "SELECT empresa_id FROM {}.empresas ORDER BY empresa_id"
                ).format(sql.Identifier(configuracion.schema))
            )
        ]
    # Persistir la credencial privada antes de la prueba de red permite retomar
    # un fallo del pooler sin recrear el rol ni perder su contraseña.
    set_key(str(RAIZ / ".env"), "DJANGO_DATABASE_URL", url_web)
    set_key(str(RAIZ / ".env"), "DJANGO_DB_SCHEMA", configuracion.schema)
    cantidad = crear_usuarios(empresas, RAIZ / "local-private/usuarios.md")
    for empresa in empresas:
        call_command("sincronizar_historico", empresa=empresa, verbosity=0)
    connection.close()
    with psycopg.connect(
        url_web,
        sslmode=conninfo_to_dict(url_web).get(
            "sslmode", configuracion.sslmode
        ),
        connect_timeout=15,
    ) as conn:
        privilegios = conn.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles "
            "WHERE rolname=current_user"
        ).fetchone()
        if privilegios != (False, False):
            raise ValueError("La conexión web conserva privilegios elevados.")
    print(f"Inicialización verificada. Usuarios creados: {cantidad}.")
    print("Accesos privados: local-private/usuarios.md")


def main() -> None:
    """Exige ejecución explícita y evita mostrar credenciales ante un fallo."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aplicar", action="store_true", required=True)
    parser.parse_args()
    try:
        inicializar()
    except (psycopg.Error, ValueError) as error:
        raise SystemExit(
            f"Inicialización detenida: {type(error).__name__}. "
            "Revise conexión, migraciones y configuración privada."
        ) from None


if __name__ == "__main__":
    main()
