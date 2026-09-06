"""
Django ModelForms for Client and Policy.

Each form:
  • Adds Tabler-compatible CSS classes to every widget.
  • Performs additional validation beyond what the model enforces.
"""

from django import forms

from .models import Client, Policy, PolicyType


# ---------------------------------------------------------------------------
# Reusable mixin
# ---------------------------------------------------------------------------

class TablerFormMixin:
    """Apply Tabler CSS classes to all visible widgets automatically."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            widget = field.widget
            css = widget.attrs.get("class", "")

            if isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css += " form-select"
            elif isinstance(widget, forms.CheckboxInput):
                css += " form-check-input"
            elif isinstance(widget, forms.Textarea):
                css += " form-control"
            else:
                css += " form-control"

            widget.attrs["class"] = css.strip()


# ---------------------------------------------------------------------------
# Client form
# ---------------------------------------------------------------------------

class ClientForm(TablerFormMixin, forms.ModelForm):
    class Meta:
        model = Client
        fields = ["name", "email", "phone", "document_number"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ej: Juan Pérez"}),
            "email": forms.EmailInput(attrs={"placeholder": "juan@example.com"}),
            "phone": forms.TextInput(attrs={"placeholder": "+54 351 1234567"}),
            "document_number": forms.TextInput(attrs={"placeholder": "12345678"}),
        }

    def clean_name(self):
        value = self.cleaned_data["name"].strip()
        if len(value) < 2:
            raise forms.ValidationError("El nombre debe tener al menos 2 caracteres.")
        return value

    def clean_document_number(self):
        value = self.cleaned_data["document_number"].strip()
        if not value.isdigit():
            raise forms.ValidationError("El número de documento debe contener solo dígitos.")
        return value


# ---------------------------------------------------------------------------
# Policy form
# ---------------------------------------------------------------------------

class PolicyForm(TablerFormMixin, forms.ModelForm):
    class Meta:
        model = Policy
        fields = [
            "policy_number",
            "client",
            "policy_type",
            "start_date",
            "end_date",
            "premium",
            "status",
        ]
        widgets = {
            "policy_number": forms.TextInput(attrs={"placeholder": "POL-2026-0001"}),
            "start_date": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "end_date": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "premium": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active policy types in the dropdown
        self.fields["policy_type"].queryset = PolicyType.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")
        if start and end and end <= start:
            self.add_error(
                "end_date",
                "La fecha de vencimiento debe ser posterior a la fecha de inicio.",
            )
        return cleaned_data
