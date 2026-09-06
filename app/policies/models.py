"""
Domain models for the insurance policy management system.

Three entities:
  • Client      – insured person / company
  • PolicyType  – catalogue of coverage categories (dynamic, DB-managed)
  • Policy      – an individual insurance policy linking a client to a type
"""

from datetime import date
from decimal import Decimal

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class Client(models.Model):
    """A person or company that holds one or more insurance policies."""

    name = models.CharField(
        "nombre completo",
        max_length=100,
        validators=[
            RegexValidator(
                regex=r"^[a-zA-ZÀ-ÿ\s\-']+$",
                message="El nombre solo puede contener letras, espacios, guiones y apóstrofes.",
            ),
        ],
    )
    email = models.EmailField("email", unique=True)
    phone = models.CharField(
        "teléfono",
        max_length=30,
        validators=[
            RegexValidator(
                regex=r"^\+?[\d\s\-()]+$",
                message="Ingresá un número de teléfono válido (dígitos, espacios, guiones, paréntesis).",
            ),
        ],
    )
    document_number = models.CharField(
        "nro. de documento",
        max_length=20,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^\d+$",
                message="El número de documento debe contener solo dígitos.",
            ),
        ],
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"

    def __str__(self):
        return f"{self.name} ({self.document_number})"


# ---------------------------------------------------------------------------
# PolicyType  (catalogue / master table)
# ---------------------------------------------------------------------------

class PolicyType(models.Model):
    """
    Catalogue of insurance coverage categories (e.g. Auto, Hogar, Vida).

    Stored in the database – instead of a hard-coded TextChoices enum – so
    that new types can be added or deactivated through the admin panel or
    a future management UI without code changes or re-deployments.
    """

    name = models.CharField("nombre", max_length=50, unique=True)
    description = models.TextField("descripción", blank=True, default="")
    is_active = models.BooleanField("activo", default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "tipo de póliza"
        verbose_name_plural = "tipos de póliza"

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

class PolicyStatus(models.TextChoices):
    """Lifecycle states for a policy."""

    ACTIVE = "vigente", "Vigente"
    EXPIRED = "vencida", "Vencida"
    RENEWED = "renovada", "Renovada"


class PolicyQuerySet(models.QuerySet):
    """Custom QuerySet that adds helpers for filtering by computed status."""

    def active(self):
        """Policies that are stored as ACTIVE **and** have not expired."""
        return self.filter(status=PolicyStatus.ACTIVE, end_date__gte=date.today())

    def expired(self):
        """Policies explicitly expired OR whose end_date has passed while
        still stored as ACTIVE (auto-detected expiration)."""
        return self.filter(
            models.Q(status=PolicyStatus.EXPIRED)
            | models.Q(status=PolicyStatus.ACTIVE, end_date__lt=date.today())
        )

    def renewed(self):
        return self.filter(status=PolicyStatus.RENEWED)


class Policy(models.Model):
    """An individual insurance policy."""

    policy_number = models.CharField("nro. de póliza", max_length=50, unique=True)

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="policies",
        verbose_name="cliente",
    )
    policy_type = models.ForeignKey(
        PolicyType,
        on_delete=models.PROTECT,
        related_name="policies",
        verbose_name="tipo de póliza",
    )

    start_date = models.DateField("fecha de inicio")
    end_date = models.DateField("fecha de vencimiento")

    premium = models.DecimalField(
        "prima",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    status = models.CharField(
        "estado",
        max_length=20,
        choices=PolicyStatus.choices,
        default=PolicyStatus.ACTIVE,
    )

    objects = PolicyQuerySet.as_manager()

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "póliza"
        verbose_name_plural = "pólizas"

    def __str__(self):
        return f"{self.policy_number} — {self.client.name}"

    # -- Computed helpers ----------------------------------------------------

    @property
    def computed_status(self):
        """Return the *real* status considering today's date.

        If the policy is stored as ACTIVE but end_date < today, it is
        effectively expired.  This avoids the need for a cron job or
        periodic task to flip statuses in the database.
        """
        if self.status == PolicyStatus.ACTIVE and self.end_date < date.today():
            return PolicyStatus.EXPIRED
        return self.status

    @property
    def computed_status_display(self):
        """Human-readable label for the computed status."""
        return dict(PolicyStatus.choices).get(self.computed_status, self.computed_status)

    @property
    def is_renewable(self):
        """A policy can be renewed only if it is active or has expired."""
        return self.computed_status in (PolicyStatus.ACTIVE, PolicyStatus.EXPIRED)

    # -- Validation ----------------------------------------------------------

    def clean(self):
        """Model-level validation: end_date must come after start_date."""
        from django.core.exceptions import ValidationError

        super().clean()
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError(
                {"end_date": "La fecha de vencimiento debe ser posterior a la fecha de inicio."}
            )
