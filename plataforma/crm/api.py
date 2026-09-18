"""API autenticada sobre servicios comerciales compartidos."""

from cuentas.acceso import alcance_empresa
from cuentas.models import MembresiaEmpresa
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from crm import historico
from crm.forms import AltaForm, GestionForm
from crm.selectores import asignaciones_propias, estados_visibles, indicadores
from crm.services.alta import crear_lead
from crm.services.asignacion import generar_asignaciones
from crm.services.cartera import transferir_responsable
from crm.services.gestion import ConflictoIdempotencia, registrar_gestion


def _empresa(request) -> str:
    """Exige una selección que posteriormente se valida por membresía."""
    empresa = request.headers.get("X-Empresa-ID", "").strip()
    if not empresa:
        raise PermissionDenied("Se requiere X-Empresa-ID.")
    return empresa


def _estado(estado) -> dict:
    """Presenta estado operativo y desconocidos de forma explícita."""
    return {
        "lead_consolidado_id": estado.lead_consolidado_id,
        "estado": estado.estado,
        "requiere_revision": estado.requiere_revision,
        "revision_entrada": estado.revision_entrada,
        "priorizacion_vigente_id": estado.priorizacion_vigente_id or None,
        "proxima_accion_en": estado.proxima_accion_en,
        "asesor_responsable_id": estado.asesor_responsable_id,
    }


class MeApi(APIView):
    """Identidad propia sin secretos."""

    def get(self, request):
        """Devuelve membresías activas del usuario autenticado."""
        return Response(
            {
                "usuario": request.user.get_username(),
                "membresias": list(
                    request.user.membresias.filter(activa=True).values(
                        "empresa_id", "rol", "asesor_id"
                    )
                ),
            }
        )


class AsignacionApi(APIView):
    """Genera asignaciones persistidas respetando cupos del catálogo."""

    def post(self, request):
        """Exige membresía supervisora dentro del servicio transaccional."""
        return Response(
            generar_asignaciones(
                usuario=request.user, empresa_id=_empresa(request)
            )
        )


class DashboardApi(APIView):
    """Indicadores calculados sobre el conjunto autorizado."""

    def get(self, request):
        """Cuenta exclusivamente la cartera visible."""
        with alcance_empresa(request.user, _empresa(request)) as miembro:
            return Response(indicadores(miembro))


class MisLeadsApi(APIView):
    """Asignaciones propias de hoy."""

    def get(self, request):
        """Materializa resultados antes de cerrar el contexto SQL."""
        with alcance_empresa(request.user, _empresa(request)) as miembro:
            return Response(
                {
                    "results": list(
                        asignaciones_propias(miembro).values(
                            "lead_consolidado_id",
                            "posicion_inicial",
                            "estado",
                            "motivo",
                        )
                    )
                }
            )


class LeadsApi(APIView):
    """Lista paginada dentro de la cartera autorizada."""

    def get(self, request):
        """Filtra por estado antes de paginar."""
        with alcance_empresa(request.user, _empresa(request)) as miembro:
            filas = estados_visibles(miembro)
            estado = request.query_params.get("estado")
            if estado:
                filas = filas.filter(estado=estado)
            paginador = PageNumberPagination()
            pagina = paginador.paginate_queryset(filas, request)
            return paginador.get_paginated_response(
                [_estado(fila) for fila in pagina]
            )

    def post(self, request):
        """Crea lead, consulta y prioridad mediante una transacción común."""
        datos = request.data.copy()
        if set(datos) - (set(AltaForm.base_fields) - {"clave"}):
            return Response({"detail": "Campos desconocidos."}, status=400)
        datos["clave"] = request.headers.get("Idempotency-Key", "")
        formulario = AltaForm(datos)
        if not formulario.is_valid():
            return Response({"errors": formulario.errors}, status=400)
        datos = formulario.cleaned_data.copy()
        clave = datos.pop("clave")
        try:
            respuesta, codigo = crear_lead(
                usuario=request.user,
                empresa_id=_empresa(request),
                clave=clave,
                datos=datos,
            )
        except ConflictoIdempotencia as error:
            return Response({"detail": str(error)}, status=409)
        except ValueError as error:
            return Response({"detail": str(error)}, status=400)
        return Response(respuesta, status=codigo)


class LeadDetalleApi(APIView):
    """Detalle sin revelar objetos fuera de cartera."""

    def get(self, request, lead_id: str):
        """Devuelve 404 para cualquier identidad no visible."""
        with alcance_empresa(request.user, _empresa(request)) as miembro:
            return Response(
                _estado(
                    get_object_or_404(
                        estados_visibles(miembro), lead_consolidado_id=lead_id
                    )
                )
            )


class GestionApi(APIView):
    """Registra un evento mediante el mismo servicio del formulario."""

    def post(self, request, lead_id: str):
        """Valida el cuerpo y preserva el resultado de cada reintento."""
        datos = dict(request.data)
        desconocidos = set(datos) - (set(GestionForm.base_fields) - {"clave"})
        if desconocidos:
            return Response({"detail": "Campos desconocidos."}, status=400)
        datos["clave"] = request.headers.get("Idempotency-Key", "")
        formulario = GestionForm(datos)
        if not formulario.is_valid():
            return Response({"errors": formulario.errors}, status=400)
        try:
            respuesta, repetida = registrar_gestion(
                usuario=request.user,
                empresa_id=_empresa(request),
                lead_id=lead_id,
                **formulario.cleaned_data,
            )
        except ConflictoIdempotencia as error:
            return Response({"detail": str(error)}, status=409)
        except ValueError as error:
            return Response({"detail": str(error)}, status=400)
        return Response(respuesta, status=200 if repetida else 201)


class ResponsableApi(APIView):
    """Transferencia explícita por supervisor."""

    def post(self, request, lead_id: str):
        """Valida destino dentro de la misma empresa."""
        with alcance_empresa(request.user, _empresa(request)) as miembro:
            get_object_or_404(
                estados_visibles(miembro), lead_consolidado_id=lead_id
            )
            responsable = get_object_or_404(
                MembresiaEmpresa,
                empresa_id=miembro.empresa_id,
                pk=request.data.get("membresia_responsable_id"),
                activa=True,
            )
            estado = transferir_responsable(
                empresa_id=miembro.empresa_id,
                lead_consolidado_id=lead_id,
                supervisor=miembro,
                nuevo_responsable=responsable,
            )
            return Response({"estado": _estado(estado)})


class CatalogoApi(APIView):
    """Catálogo de modelos disponibles en sedes de la empresa."""

    def get(self, request):
        """Consulta el catálogo después de validar acceso comercial."""
        with alcance_empresa(request.user, _empresa(request)) as miembro:
            estados_visibles(miembro)
            return Response(
                {"results": historico.catalogo(miembro.empresa_id)}
            )


class SedesApi(APIView):
    """Sedes de la empresa activa."""

    def get(self, request):
        """No devuelve sedes de otras empresas."""
        with alcance_empresa(request.user, _empresa(request)) as miembro:
            estados_visibles(miembro)
            return Response({"results": historico.sedes(miembro.empresa_id)})


class HistoriaApi(APIView):
    """Hijos comerciales de un padre autorizado antes de consultar SQL."""

    tipo = "prioridades"

    def get(self, request, lead_id: str):
        """Restringe descartadas a supervisores de la misma empresa."""
        with alcance_empresa(request.user, _empresa(request)) as miembro:
            get_object_or_404(
                estados_visibles(miembro), lead_consolidado_id=lead_id
            )
            if self.tipo == "conversaciones":
                filas = historico.conversaciones(
                    miembro.empresa_id,
                    lead_id,
                    incluir_descartadas=miembro.rol == "supervisor",
                )
            else:
                filas = historico.prioridades(miembro.empresa_id, lead_id)
            return Response({"results": filas})
