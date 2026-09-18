"""Resolución centralizada del ámbito de empresa autorizado."""

from collections.abc import Iterator
from contextlib import contextmanager

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import PermissionDenied

from cuentas.models import MembresiaEmpresa


def obtener_membresia_activa(
    usuario: AbstractBaseUser,
    empresa_id: str,
) -> MembresiaEmpresa:
    """Obtiene la membresía activa que autoriza un ámbito empresarial.

    Args:
        usuario: Usuario autenticado que solicita operar en una empresa.
        empresa_id: Empresa elegida por la sesión o API para esta solicitud.

    Returns:
        Membresía activa y única del usuario para la empresa solicitada.

    Raises:
        PermissionDenied: Si no hay autenticación o membresía activa válida.
    """
    if (
        not usuario.is_authenticated
        or not usuario.is_active
        or not empresa_id
        or not empresa_id.strip()
    ):
        raise PermissionDenied("No tiene una empresa activa autorizada.")
    try:
        return MembresiaEmpresa.objects.get(
            usuario=usuario,
            empresa_id=empresa_id.strip(),
            activa=True,
        )
    except MembresiaEmpresa.DoesNotExist as error:
        raise PermissionDenied(
            "No tiene acceso a la empresa solicitada."
        ) from error


@contextmanager
def alcance_empresa(
    usuario: AbstractBaseUser,
    empresa_id: str,
) -> Iterator[MembresiaEmpresa]:
    """Abre el contexto SQL de una membresía autorizada.

    Args:
        usuario: Usuario autenticado que ejecutará operaciones comerciales.
        empresa_id: Empresa solicitada, validada contra la membresía.

    Yields:
        Membresía autorizada dentro de una transacción de empresa.

    Raises:
        PermissionDenied: Si usuario y empresa no forman una membresía activa.
    """
    membresia = obtener_membresia_activa(usuario, empresa_id)
    from crm.contexto_empresa import transaccion_empresa

    with transaccion_empresa(membresia.empresa_id):
        yield membresia
