"""Verifica los accesos privados iniciales sin imprimir sus credenciales."""

import os
import sys
import time
from pathlib import Path


def verificar() -> None:
    """Autentica tres usuarios reales y comprueba sus ámbitos HTTP y SQL."""
    raiz = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(raiz / "plataforma"), str(raiz)]
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plataforma.settings")
    import django

    django.setup()
    from django.db import connection
    from django.test import override_settings
    from django.test.utils import CaptureQueriesContext
    from rest_framework.test import APIClient

    accesos = []
    for linea in (
        (raiz / "local-private/usuarios.md")
        .read_text(encoding="utf-8")
        .splitlines()
    ):
        if linea.startswith("| evaluador_"):
            usuario, empresa, clave = [
                c.strip() for c in linea.split("|")[1:4]
            ]
            accesos.append((usuario, empresa, clave.strip("`")))
    assert len(accesos) == 3, "Se requieren los tres accesos documentados."
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper,rolbypassrls FROM pg_roles "
            "WHERE rolname=current_user"
        )
        assert cursor.fetchone() == (False, False)
    with override_settings(ALLOWED_HOSTS=["testserver"]):
        for usuario, empresa, clave in accesos:
            cliente = APIClient()
            assert cliente.login(username=usuario, password=clave)
            try:
                identidad = cliente.get("/api/v1/me/")
                assert identidad.status_code == 200
                assert len(identidad.data["membresias"]) == 1
                inicio = time.monotonic()
                with CaptureQueriesContext(connection) as consultas:
                    pagina = cliente.get(
                        "/api/v1/leads/", HTTP_X_EMPRESA_ID=empresa
                    )
                assert pagina.status_code == 200
                assert len(pagina.data["results"]) <= 25
                print(
                    f"Cartera autorizada: {pagina.data['count']} leads; "
                    f"{len(consultas)} consultas; "
                    f"{time.monotonic() - inicio:.2f} s."
                )
                dashboard = cliente.get(
                    "/api/v1/dashboard/", HTTP_X_EMPRESA_ID=empresa
                )
                assert dashboard.status_code == 200
                for _, otra, _ in accesos:
                    if otra != empresa:
                        assert (
                            cliente.get(
                                "/api/v1/leads/", HTTP_X_EMPRESA_ID=otra
                            ).status_code
                            == 403
                        )
            finally:
                cliente.logout()
    print("OK: tres accesos, autenticación y aislamiento con el rol web real.")


if __name__ == "__main__":
    verificar()
