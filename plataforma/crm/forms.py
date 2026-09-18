"""Validación compartida de los campos de gestión comercial."""

from django import forms

from crm.services.gestion import RESULTADOS


class BooleanoDeclarado(forms.Field):
    """Distingue sí, no y desconocido; rechaza valores no reconocidos."""

    widget = forms.Select(
        choices=[
            ("", "Desconocido"),
            ("true", "Sí"),
            ("false", "No"),
        ]
    )

    def to_python(self, value):
        """Convierte solo booleanos JSON o valores del selector HTML."""
        if value is None or value == "":
            return None
        if type(value) is bool:
            return value
        if value == "true":
            return True
        if value == "false":
            return False
        raise forms.ValidationError("Seleccione sí, no o desconocido.")


class AltaForm(forms.Form):
    """Valida la captura manual y conserva declaraciones independientes."""

    nombre_cliente = forms.CharField(
        max_length=200, label="Nombre del cliente"
    )
    telefono = forms.CharField(max_length=80, required=False, label="Teléfono")
    correo = forms.EmailField(required=False)
    sede_id = forms.CharField(max_length=100, label="Código de la sede")
    ciudad = forms.CharField(max_length=200, required=False)
    modelos_interes = forms.CharField(
        label="Motos de interés",
        max_length=4000,
        required=False,
        widget=forms.Textarea,
        help_text="Incluye todas las motos, incluso fuera del catálogo.",
    )
    modelo_sku = forms.CharField(
        max_length=100, required=False, label="Código de moto en catálogo"
    )
    presupuesto = forms.DecimalField(
        min_value=0, max_digits=18, decimal_places=2, required=False
    )
    cuota_inicial = forms.DecimalField(
        min_value=0, max_digits=18, decimal_places=2, required=False
    )
    moneda = forms.ChoiceField(
        choices=[("", "Desconocida"), ("COP", "COP")], required=False
    )
    forma_pago = forms.ChoiceField(
        label="Forma de pago declarada",
        choices=[
            ("", "Desconocida"),
            ("credito", "Crédito"),
            ("contado", "Contado"),
            ("mixto", "Mixto"),
        ],
        required=False,
    )
    cliente_pidio_cita = BooleanoDeclarado(
        required=False, label="¿El cliente pidió cita?"
    )
    cliente_pidio_credito = BooleanoDeclarado(
        required=False, label="¿El cliente pidió crédito?"
    )
    asesor_ofrecio_credito = BooleanoDeclarado(
        required=False, label="¿El asesor ofreció crédito?"
    )
    cliente_pidio_cotizacion = BooleanoDeclarado(
        required=False, label="¿El cliente pidió cotización?"
    )
    intencion_declarada = forms.CharField(
        max_length=1000, required=False, label="Intención declarada"
    )
    objecion_principal = forms.CharField(
        max_length=1000, required=False, label="Objeción principal"
    )
    nota = forms.CharField(
        max_length=2000, required=False, widget=forms.Textarea
    )
    clave = forms.CharField(max_length=255, widget=forms.HiddenInput)

    def clean(self):
        """Distingue presupuesto, inicial y contradicciones explícitas."""
        datos = super().clean()
        if any(
            datos.get(c) is not None for c in ["presupuesto", "cuota_inicial"]
        ):
            if datos.get("moneda") != "COP":
                self.add_error("moneda", "Declare COP para los importes.")
        if datos.get("forma_pago") == "contado" and datos.get(
            "cliente_pidio_credito"
        ):
            self.add_error(
                "forma_pago", "Revise contado y crédito solicitado."
            )
        inicial, presupuesto = (
            datos.get("cuota_inicial"),
            datos.get("presupuesto"),
        )
        if (
            inicial is not None
            and presupuesto is not None
            and inicial > presupuesto
        ):
            self.add_error(
                "cuota_inicial", "La inicial no puede superar el presupuesto."
            )
        return datos


class GestionForm(forms.Form):
    """Recoge hechos declarados sin convertir silencio en contacto."""

    resultado = forms.ChoiceField(choices=[(x, x) for x in RESULTADOS])
    nota = forms.CharField(
        max_length=2000, required=False, widget=forms.Textarea
    )
    proxima_accion_en = forms.DateTimeField(
        required=False,
        label="Próxima acción (hora de Bogotá)",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    confirmar_cierre = BooleanoDeclarado(
        required=False, label="¿Confirma el cierre declarado?"
    )
    clave = forms.CharField(max_length=255, widget=forms.HiddenInput)


class RevisionForm(forms.Form):
    """Valida una decisión supervisora sin inferir una identidad nueva."""

    accion = forms.ChoiceField(
        choices=[
            ("vincular", "Vincular"),
            ("rechazar", "Rechazar"),
            ("crear_distinto", "Crear cliente distinto"),
        ]
    )
    lead_consolidado_id = forms.CharField(max_length=100, required=False)
    nota = forms.CharField(max_length=500, required=False)

    def clean(self):
        """Exige la evidencia mínima correspondiente a cada decisión."""
        datos = super().clean()
        if datos.get("accion") == "vincular" and not datos.get(
            "lead_consolidado_id"
        ):
            self.add_error(
                "lead_consolidado_id", "Indique el lead de la misma empresa."
            )
        es_rechazo_sin_nota = (
            datos.get("accion") == "rechazar"
            and not datos.get("nota", "").strip()
        )
        if es_rechazo_sin_nota:
            self.add_error("nota", "Indique el motivo del rechazo.")
        return datos
