"""Modelos operativos de CRM, separados de las tablas históricas importadas."""

from uuid import uuid4

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class EstadoComercial(models.TextChoices):
    """Define el estado actual de atención de un lead."""

    ABIERTO = "abierto", "Abierto"
    CERRADO = "cerrado", "Cerrado"
    DESCARTADO = "descartado", "Descartado"
    PERDIDO = "perdido", "Perdido"
    REVISION = "revision", "En revisión"


class EstadoAsignacion(models.TextChoices):
    """Define el avance de una asignación diaria."""

    ASIGNADA = "asignada", "Asignada"
    COMPLETADA = "completada", "Completada"
    PENDIENTE = "pendiente", "Pendiente"


class EstadoCapturaRevision(models.TextChoices):
    """Define el ciclo de vida de una captura que requiere revisión."""

    PENDIENTE = "pendiente", "Pendiente"
    RECHAZADA = "rechazada", "Rechazada"
    RESUELTA = "resuelta", "Resuelta"


class EstadoSolicitud(models.TextChoices):
    """Define el resultado de una solicitud idempotente."""

    COMPLETADA = "completada", "Completada"
    EN_PROCESO = "en_proceso", "En proceso"
    FALLIDA = "fallida", "Fallida"


class EstadoTrabajo(models.TextChoices):
    """Define el ciclo de vida de un trabajo durable."""

    COMPLETADO = "completado", "Completado"
    EJECUTANDO = "ejecutando", "Ejecutando"
    FALLIDO = "fallido", "Fallido"
    OBSOLETO = "obsoleto", "Obsoleto"
    PENDIENTE = "pendiente", "Pendiente"
    REINTENTO = "reintento", "Reintento"


class ModeloConTimestamps(models.Model):
    """Aporta marcas de creación y actualización a entidades operativas."""

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        """Evita crear una tabla solo para campos reutilizables."""

        abstract = True


class EstadoOperativoLead(ModeloConTimestamps):
    """Conserva estado, cartera y prioridad vigente por lead y empresa.

    Los identificadores de empresa, lead y prioridad pertenecen a las tablas
    históricas administradas por el cargador. La migración PostgreSQL de
    integración añadirá las referencias físicas y políticas correspondientes.
    """

    empresa_id = models.CharField(max_length=100)
    lead_consolidado_id = models.CharField(max_length=100)
    asesor_responsable = models.ForeignKey(
        "cuentas.MembresiaEmpresa",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="leads_responsables",
    )
    estado = models.CharField(
        choices=EstadoComercial.choices,
        default=EstadoComercial.ABIERTO,
        max_length=20,
    )
    proxima_accion_en = models.DateTimeField(blank=True, null=True)
    revision_entrada = models.PositiveIntegerField(default=1)
    priorizacion_vigente_id = models.CharField(max_length=100, blank=True)
    requiere_revision = models.BooleanField(default=False)

    class Meta:
        """Protege la unicidad del estado operativo de cada lead."""

        constraints = [
            models.UniqueConstraint(
                fields=["empresa_id", "lead_consolidado_id"],
                name="crm_estado_empresa_lead_unico",
            ),
        ]
        indexes = [
            models.Index(
                fields=["empresa_id", "estado", "proxima_accion_en"],
                name="crm_estado_empresa_accion_idx",
            ),
            models.Index(
                fields=["asesor_responsable", "estado"],
                name="crm_estado_asesor_estado_idx",
            ),
        ]
        verbose_name = "estado operativo de lead"
        verbose_name_plural = "estados operativos de leads"

    def __str__(self) -> str:
        """Devuelve una etiqueta segura para diagnósticos administrativos."""
        return (
            f"{self.empresa_id} · {self.lead_consolidado_id} · {self.estado}"
        )


class CapturaEstructurada(models.Model):
    """Guarda hechos capturados manualmente y su procedencia verificable."""

    captura_id = models.UUIDField(
        default=uuid4, editable=False, primary_key=True
    )
    empresa_id = models.CharField(max_length=100)
    lead_consolidado_id = models.CharField(max_length=100, blank=True)
    lead_id_origen = models.CharField(max_length=100, blank=True)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="capturas_estructuradas",
    )
    origen = models.CharField(default="captura_manual", max_length=40)
    declaracion = models.JSONField(default=dict)
    incidencias = models.JSONField(default=list)
    revision_entrada = models.PositiveIntegerField(default=1)
    capturada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Facilita reconstruir la secuencia de capturas por lead."""

        indexes = [
            models.Index(
                fields=["empresa_id", "lead_consolidado_id", "capturada_en"],
                name="crm_captura_empresa_lead_idx",
            ),
        ]
        verbose_name = "captura estructurada"
        verbose_name_plural = "capturas estructuradas"


class SolicitudIdempotente(models.Model):
    """Registra resultados de escrituras repetibles sin duplicar efectos."""

    empresa_id = models.CharField(max_length=100)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="solicitudes_idempotentes",
    )
    operacion = models.CharField(max_length=80)
    clave = models.CharField(max_length=255)
    huella_cuerpo = models.CharField(max_length=64)
    estado = models.CharField(
        choices=EstadoSolicitud.choices,
        default=EstadoSolicitud.EN_PROCESO,
        max_length=20,
    )
    respuesta = models.JSONField(default=dict)
    creada_en = models.DateTimeField(auto_now_add=True)
    finalizada_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        """Evita repetir una operación del mismo actor y empresa."""

        constraints = [
            models.UniqueConstraint(
                fields=["empresa_id", "actor", "operacion", "clave"],
                name="crm_idempotencia_actor_operacion_unica",
            ),
        ]
        indexes = [
            models.Index(
                fields=["empresa_id", "estado", "creada_en"],
                name="crm_idemp_empresa_estado_idx",
            ),
        ]
        verbose_name = "solicitud idempotente"
        verbose_name_plural = "solicitudes idempotentes"


class TrabajoProcesamiento(ModeloConTimestamps):
    """Representa una unidad durable de extracción o cálculo diferido."""

    trabajo_id = models.UUIDField(
        default=uuid4, editable=False, primary_key=True
    )
    empresa_id = models.CharField(max_length=100)
    tipo_entidad = models.CharField(max_length=40)
    entidad_id = models.CharField(max_length=100)
    tipo_trabajo = models.CharField(max_length=80)
    revision_entrada = models.PositiveIntegerField(default=1)
    estado = models.CharField(
        choices=EstadoTrabajo.choices,
        default=EstadoTrabajo.PENDIENTE,
        max_length=20,
    )
    intentos = models.PositiveIntegerField(default=0)
    disponible_en = models.DateTimeField()
    lease_hasta = models.DateTimeField(blank=True, null=True)
    ultimo_error = models.CharField(max_length=500, blank=True)
    configuracion = models.JSONField(default=dict)

    class Meta:
        """Evita ejecutar dos veces un mismo trabajo lógico."""

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "empresa_id",
                    "tipo_entidad",
                    "entidad_id",
                    "tipo_trabajo",
                    "revision_entrada",
                ],
                name="crm_trabajo_logico_unico",
            ),
        ]
        indexes = [
            models.Index(
                fields=["estado", "disponible_en"],
                name="crm_trabajo_estado_disp_idx",
            ),
        ]
        verbose_name = "trabajo de procesamiento"
        verbose_name_plural = "trabajos de procesamiento"


class AsignacionDiaria(ModeloConTimestamps):
    """Asigna un lead a un asesor durante un día operativo de Bogotá."""

    empresa_id = models.CharField(max_length=100)
    lead_consolidado_id = models.CharField(max_length=100)
    asesor = models.ForeignKey(
        "cuentas.MembresiaEmpresa",
        on_delete=models.PROTECT,
        related_name="asignaciones_diarias",
    )
    fecha_operativa = models.DateField()
    posicion_inicial = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    estado = models.CharField(
        choices=EstadoAsignacion.choices,
        default=EstadoAsignacion.ASIGNADA,
        max_length=20,
    )
    ejecucion_id = models.CharField(max_length=100, blank=True)
    motivo = models.CharField(max_length=250, blank=True)

    class Meta:
        """Impide duplicar leads y posiciones de una asignación diaria."""

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "empresa_id",
                    "fecha_operativa",
                    "lead_consolidado_id",
                ],
                name="crm_asignacion_empresa_fecha_lead_unica",
            ),
            models.UniqueConstraint(
                fields=["asesor", "fecha_operativa", "posicion_inicial"],
                name="crm_asignacion_asesor_fecha_posicion_unica",
            ),
        ]
        indexes = [
            models.Index(
                fields=["asesor", "fecha_operativa", "estado"],
                name="crm_asig_asesor_fecha_idx",
            ),
        ]
        verbose_name = "asignación diaria"
        verbose_name_plural = "asignaciones diarias"


class GestionComercial(models.Model):
    """Conserva una gestión comercial inmutable registrada por un actor."""

    gestion_id = models.UUIDField(
        default=uuid4, editable=False, primary_key=True
    )
    empresa_id = models.CharField(max_length=100)
    lead_consolidado_id = models.CharField(max_length=100)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="gestiones_comerciales",
    )
    asignacion = models.ForeignKey(
        AsignacionDiaria,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="gestiones",
    )
    resultado = models.CharField(max_length=40)
    nota = models.CharField(max_length=2000, blank=True)
    proxima_accion_en = models.DateTimeField(blank=True, null=True)
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Optimiza la lectura cronológica de gestiones por lead."""

        indexes = [
            models.Index(
                fields=["empresa_id", "lead_consolidado_id", "registrada_en"],
                name="crm_gestion_empresa_lead_idx",
            ),
        ]
        verbose_name = "gestión comercial"
        verbose_name_plural = "gestiones comerciales"


class CapturaRevision(ModeloConTimestamps):
    """Almacena una captura sin revelar candidatos de una cartera ajena."""

    revision_id = models.UUIDField(
        default=uuid4, editable=False, primary_key=True
    )
    empresa_id = models.CharField(max_length=100)
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="capturas_pendientes_revision",
    )
    datos_propuestos = models.JSONField(default=dict)
    motivo = models.CharField(max_length=250)
    estado = models.CharField(
        choices=EstadoCapturaRevision.choices,
        default=EstadoCapturaRevision.PENDIENTE,
        max_length=20,
    )
    resolutor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="capturas_resueltas",
    )
    resolucion = models.CharField(max_length=500, blank=True)
    lead_consolidado_id_resuelto = models.CharField(max_length=100, blank=True)
    resuelta_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        """Permite consultar revisiones pendientes por empresa y fecha."""

        indexes = [
            models.Index(
                fields=["empresa_id", "estado", "creado_en"],
                name="crm_rev_empresa_estado_idx",
            ),
        ]
        verbose_name = "captura en revisión"
        verbose_name_plural = "capturas en revisión"


class EventoAuditoria(models.Model):
    """Registra efectos relevantes sin guardar secretos o textos completos."""

    evento_id = models.UUIDField(
        default=uuid4, editable=False, primary_key=True
    )
    empresa_id = models.CharField(max_length=100, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="eventos_auditoria",
    )
    accion = models.CharField(max_length=100)
    tipo_entidad = models.CharField(max_length=80)
    entidad_id = models.CharField(max_length=100)
    correlacion_id = models.UUIDField(blank=True, null=True)
    detalle = models.JSONField(default=dict)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Facilita auditar acciones por entidad y empresa."""

        indexes = [
            models.Index(
                fields=["empresa_id", "tipo_entidad", "entidad_id"],
                name="crm_audit_empresa_entidad_idx",
            ),
        ]
        verbose_name = "evento de auditoría"
        verbose_name_plural = "eventos de auditoría"
