"""Validación compartida de los campos de gestión comercial."""

from django import forms

from crm.services.gestion import RESULTADOS


class AltaForm(forms.Form):
    """Valida la captura manual y conserva declaraciones independientes."""

    nombre_cliente = forms.CharField(max_length=200)
    telefono = forms.CharField(max_length=80, required=False)
    correo = forms.EmailField(required=False)
    sede_id = forms.CharField(max_length=100)
    ciudad = forms.CharField(max_length=200, required=False)
    modelos_interes = forms.CharField(
        max_length=4000,
        required=False,
        widget=forms.Textarea,
        help_text="Incluye todas las motos, incluso fuera del catálogo.",
    )
    modelo_sku = forms.CharField(max_length=100, required=False)
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
        choices=[
            ("", "Desconocida"),
            ("credito", "Crédito"),
            ("contado", "Contado"),
            ("mixto", "Mixto"),
        ],
        required=False,
    )
    cliente_pidio_cita = forms.NullBooleanField(required=False)
    cliente_pidio_credito = forms.NullBooleanField(required=False)
    asesor_ofrecio_credito = forms.NullBooleanField(required=False)
    cliente_pidio_cotizacion = forms.NullBooleanField(required=False)
    intencion_declarada = forms.CharField(max_length=1000, required=False)
    objecion_principal = forms.CharField(max_length=1000, required=False)
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
    confirmar_cierre = forms.BooleanField(required=False)
    clave = forms.CharField(max_length=255, widget=forms.HiddenInput)
