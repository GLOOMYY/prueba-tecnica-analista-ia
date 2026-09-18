"""Pantallas comerciales con autorización y consultas compartidas."""

from uuid import uuid4

from cuentas.acceso import alcance_empresa, obtener_membresia_activa
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from crm.forms import AltaForm, GestionForm
from crm.historico import _consultar
from crm.models import CapturaEstructurada, GestionComercial
from crm.selectores import asignaciones_propias, estados_visibles, indicadores
from crm.services.alta import crear_lead
from crm.services.gestion import registrar_gestion


@login_required
def elegir_empresa(request):
    """Selecciona una membresía existente y revalida cada envío."""
    empresas = request.user.membresias.filter(
        activa=True, rol__in=["asesor", "supervisor"]
    )
    if request.method == "POST":
        miembro = obtener_membresia_activa(
            request.user, request.POST.get("empresa_id", "")
        )
        estados_visibles(miembro)
        request.session["empresa_id"] = miembro.empresa_id
        return redirect("tablero")
    return render(request, "crm/empresas.html", {"empresas": empresas})


@login_required
def alta(request):
    """Guarda una captura manual sin atribuirla a Gemini."""
    empresa = request.session.get("empresa_id")
    if not empresa:
        return redirect("elegir_empresa")
    with alcance_empresa(request.user, empresa) as miembro:
        estados_visibles(miembro)
    formulario = AltaForm(
        request.POST if request.method == "POST" else None,
        initial={"clave": str(uuid4())},
    )
    if request.method == "POST" and formulario.is_valid():
        datos = formulario.cleaned_data.copy()
        clave = datos.pop("clave")
        try:
            respuesta, codigo = crear_lead(
                usuario=request.user,
                empresa_id=empresa,
                clave=clave,
                datos=datos,
            )
        except ValueError as error:
            formulario.add_error(None, str(error))
        else:
            if respuesta.get("lead_consolidado_id"):
                messages.success(request, "Captura y prioridad guardadas.")
                return redirect(
                    "detalle", lead_id=respuesta["lead_consolidado_id"]
                )
            return render(
                request, "crm/revision.html", respuesta, status=codigo
            )
    return render(request, "crm/alta.html", {"formulario": formulario})


@login_required
def tablero(request):
    """Muestra métricas de cartera y acceso a sus leads."""
    empresa = request.session.get("empresa_id")
    if not empresa:
        return redirect("elegir_empresa")
    with alcance_empresa(request.user, empresa) as miembro:
        contexto = indicadores(miembro)
        contexto["leads"] = list(estados_visibles(miembro)[:100])
    return render(request, "crm/tablero.html", contexto)


@login_required
def mis_leads(request):
    """Materializa la cola antes de cerrar la transacción empresarial."""
    empresa = request.session.get("empresa_id")
    if not empresa:
        return redirect("elegir_empresa")
    with alcance_empresa(request.user, empresa) as miembro:
        filas = list(asignaciones_propias(miembro))
    return render(
        request,
        "crm/mis_leads.html",
        {"empresa_id": empresa, "asignaciones": filas},
    )


@login_required
def detalle(request, lead_id: str):
    """Muestra historia y registra gestiones con CSRF e idempotencia."""
    empresa = request.session.get("empresa_id")
    if not empresa:
        return redirect("elegir_empresa")
    with alcance_empresa(request.user, empresa) as miembro:
        estado = get_object_or_404(
            estados_visibles(miembro), lead_consolidado_id=lead_id
        )
        captura = (
            CapturaEstructurada.objects.filter(
                empresa_id=miembro.empresa_id, lead_consolidado_id=lead_id
            )
            .order_by("-capturada_en")
            .first()
        )
        prioridades = []
        if estado.priorizacion_vigente_id:
            prioridades = _consultar(
                "SELECT score_prioridad, temperatura, explicacion, "
                "accion_sugerida FROM priorizaciones "
                "WHERE empresa_id = %s AND lead_consolidado_id = %s "
                "AND priorizacion_id = %s",
                [miembro.empresa_id, lead_id, estado.priorizacion_vigente_id],
            )
        gestiones = list(
            GestionComercial.objects.filter(
                empresa_id=miembro.empresa_id, lead_consolidado_id=lead_id
            ).order_by("-registrada_en")[:100]
        )
    formulario = GestionForm(
        request.POST if request.method == "POST" else None,
        initial={"clave": str(uuid4())},
    )
    if request.method == "POST" and formulario.is_valid():
        try:
            registrar_gestion(
                usuario=request.user,
                empresa_id=empresa,
                lead_id=lead_id,
                **formulario.cleaned_data,
            )
        except ValueError as error:
            formulario.add_error(None, str(error))
        else:
            messages.success(request, "Gestión guardada.")
            return redirect("detalle", lead_id=lead_id)
    return render(
        request,
        "crm/detalle.html",
        {
            "estado": estado,
            "gestiones": gestiones,
            "formulario": formulario,
            "captura": captura,
            "prioridad": prioridades[0] if prioridades else None,
        },
    )
