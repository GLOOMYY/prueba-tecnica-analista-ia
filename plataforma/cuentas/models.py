"""Modelos de identidad y pertenencia a empresas de la plataforma."""

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """Representa a una persona que accede a la plataforma.

    La empresa no pertenece directamente al usuario porque una misma persona
    puede participar en más de una empresa. El ámbito comercial se obtiene de
    una :class:`MembresiaEmpresa` activa y autorizada.
    """

    class Meta:
        """Configuración de presentación del usuario."""

        verbose_name = "usuario"
        verbose_name_plural = "usuarios"


class RolMembresia(models.TextChoices):
    """Define las capacidades comerciales de una membresía."""

    ASESOR = "asesor", "Asesor"
    SUPERVISOR = "supervisor", "Supervisor"
    OPERADOR = "operador", "Operador técnico"


class MembresiaEmpresa(models.Model):
    """Vincula un usuario con una empresa y el rol que ejerce en ella.

    ``empresa_id`` y ``asesor_id`` referenciarán al modelo histórico de CRM en
    la migración de integración PostgreSQL. Se conservan como textos en esta
    primera migración para evitar que Django administre tablas históricas.
    Las rutas comerciales deberán verificar esas referencias antes de usarlas.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membresias",
    )
    empresa_id = models.CharField(max_length=100)
    rol = models.CharField(max_length=20, choices=RolMembresia.choices)
    asesor_id = models.CharField(max_length=100, blank=True)
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        """Impide duplicar una membresía para la misma empresa."""

        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "empresa_id"],
                name="cuentas_membresia_usuario_empresa_unica",
            ),
        ]
        indexes = [
            models.Index(
                fields=["usuario", "activa"],
                name="cta_memb_usuario_activa_idx",
            ),
            models.Index(
                fields=["empresa_id", "activa"],
                name="cta_memb_empresa_activa_idx",
            ),
        ]
        verbose_name = "membresía de empresa"
        verbose_name_plural = "membresías de empresa"

    def __str__(self) -> str:
        """Devuelve texto seguro para interfaces administrativas."""
        return f"{self.usuario} · {self.empresa_id} · {self.rol}"
