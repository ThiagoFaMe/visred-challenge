"""
Views for the insurance policy management system.

Uses Django class-based views (CBVs) for the standard CRUD operations
and function-based views where the logic is simpler or more explicit.
"""

import re
from datetime import timedelta

from django.contrib import messages
from django.db import models, transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import ClientForm, PolicyForm
from .models import Client, Policy, PolicyStatus, PolicyType


# ============================================================================
# Dashboard
# ============================================================================

class DashboardView(View):
    """Main dashboard showing summary statistics."""

    def get(self, request):
        today = __import__("datetime").date.today()

        total_policies = Policy.objects.count()
        active_count = Policy.objects.active().count()
        expired_count = Policy.objects.expired().count()
        renewed_count = Policy.objects.renewed().count()
        total_clients = Client.objects.count()
        total_premium = Policy.objects.active().aggregate(
            total=Sum("premium")
        )["total"] or 0

        context = {
            "total_policies": total_policies,
            "active_count": active_count,
            "expired_count": expired_count,
            "renewed_count": renewed_count,
            "total_clients": total_clients,
            "total_premium": total_premium,
            "recent_policies": Policy.objects.select_related("client", "policy_type")[:5],
        }
        return render(request, "dashboard.html", context)


# ============================================================================
# Client CRUD
# ============================================================================

class ClientListView(ListView):
    model = Client
    template_name = "clients/client_list.html"
    context_object_name = "clients"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().annotate(policy_count=Count("policies"))
        search = self.request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(document_number__icontains=search)
                | Q(email__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search"] = self.request.GET.get("search", "")
        return ctx


class ClientDetailView(DetailView):
    model = Client
    template_name = "clients/client_detail.html"
    context_object_name = "client"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["policies"] = (
            self.object.policies.select_related("policy_type").all()
        )
        return ctx


class ClientCreateView(CreateView):
    model = Client
    form_class = ClientForm
    template_name = "clients/client_form.html"
    success_url = reverse_lazy("client-list")

    def form_valid(self, form):
        messages.success(self.request, "Cliente creado exitosamente.")
        return super().form_valid(form)


class ClientUpdateView(UpdateView):
    model = Client
    form_class = ClientForm
    template_name = "clients/client_form.html"
    success_url = reverse_lazy("client-list")

    def form_valid(self, form):
        messages.success(self.request, "Cliente actualizado exitosamente.")
        return super().form_valid(form)


class ClientDeleteView(DeleteView):
    model = Client
    template_name = "clients/client_confirm_delete.html"
    success_url = reverse_lazy("client-list")

    def form_valid(self, form):
        messages.success(self.request, "Cliente eliminado exitosamente.")
        return super().form_valid(form)


# ============================================================================
# Policy CRUD
# ============================================================================

class PolicyListView(ListView):
    model = Policy
    template_name = "policies/policy_list.html"
    context_object_name = "policies"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related("client", "policy_type")

        # -- Filter by status ------------------------------------------------
        status_filter = self.request.GET.get("status", "").strip()
        if status_filter == "active":
            qs = qs.active()          # uses our custom QuerySet method
        elif status_filter == "expired":
            qs = qs.expired()
        elif status_filter == "renewed":
            qs = qs.renewed()

        # -- Search ----------------------------------------------------------
        search = self.request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(policy_number__icontains=search)
                | Q(client__name__icontains=search)
                | Q(client__document_number__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search"] = self.request.GET.get("search", "")
        ctx["status_filter"] = self.request.GET.get("status", "")
        ctx["status_choices"] = [
            ("", "Todos"),
            ("active", "Vigentes"),
            ("expired", "Vencidas"),
            ("renewed", "Renovadas"),
        ]
        return ctx


class PolicyCreateView(CreateView):
    model = Policy
    form_class = PolicyForm
    template_name = "policies/policy_form.html"
    success_url = reverse_lazy("policy-list")

    def form_valid(self, form):
        messages.success(self.request, "Póliza creada exitosamente.")
        return super().form_valid(form)


class PolicyUpdateView(UpdateView):
    model = Policy
    form_class = PolicyForm
    template_name = "policies/policy_form.html"
    success_url = reverse_lazy("policy-list")

    def form_valid(self, form):
        messages.success(self.request, "Póliza actualizada exitosamente.")
        return super().form_valid(form)


class PolicyDeleteView(DeleteView):
    model = Policy
    template_name = "policies/policy_confirm_delete.html"
    success_url = reverse_lazy("policy-list")

    def form_valid(self, form):
        messages.success(self.request, "Póliza eliminada exitosamente.")
        return super().form_valid(form)


# ============================================================================
# Policy Renewal  (key business logic)
# ============================================================================

class PolicyRenewView(View):
    """
    Renew a policy in an atomic transaction:
      1. Mark the original policy as RENEWED.
      2. Create a new ACTIVE policy with extended dates (+1 year).
    """

    def post(self, request, pk):
        original = get_object_or_404(Policy, pk=pk)

        if not original.is_renewable:
            messages.error(
                request,
                f"La póliza {original.policy_number} no puede ser renovada "
                f"(estado actual: {original.computed_status_display}).",
            )
            return redirect("policy-list")

        with transaction.atomic():
            # 1) Flip the original to RENEWED
            original.status = PolicyStatus.RENEWED
            original.save(update_fields=["status"])

            # 2) Build the renewed copy
            new_start = original.end_date
            new_end = new_start + timedelta(days=365)

            # Generate renewal number
            match = re.match(r"^(.+)-R(\d+)$", original.policy_number)
            if match:
                base_number = match.group(1)
                next_num = int(match.group(2)) + 1
            else:
                base_number = original.policy_number
                next_num = 1

            # Ensure uniqueness: find the highest existing renewal number
            existing = Policy.objects.filter(
                policy_number__regex=rf"^{re.escape(base_number)}-R\d+$"
            )
            for p in existing:
                m = re.match(rf"^{re.escape(base_number)}-R(\d+)$", p.policy_number)
                if m:
                    next_num = max(next_num, int(m.group(1)) + 1)

            new_number = f"{base_number}-R{next_num}"

            Policy.objects.create(
                policy_number=new_number,
                client=original.client,
                policy_type=original.policy_type,
                start_date=new_start,
                end_date=new_end,
                premium=original.premium,
                status=PolicyStatus.ACTIVE,
            )

        messages.success(
            request,
            f"Póliza {original.policy_number} renovada exitosamente. "
            f"Nueva póliza: {new_number}.",
        )
        return redirect("policy-list")


# ============================================================================
# Bonus: JSON API endpoint for AJAX filtering
# ============================================================================

class PolicyApiListView(View):
    """Return policies as JSON for client-side dynamic filtering."""

    def get(self, request):
        qs = Policy.objects.select_related("client", "policy_type").all()

        status_filter = request.GET.get("status", "").strip()
        if status_filter == "active":
            qs = qs.active()
        elif status_filter == "expired":
            qs = qs.expired()
        elif status_filter == "renewed":
            qs = qs.renewed()

        search = request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(policy_number__icontains=search)
                | Q(client__name__icontains=search)
                | Q(client__document_number__icontains=search)
            )

        from datetime import date
        today = date.today()

        data = []
        for p in qs[:100]:
            data.append({
                "id": p.pk,
                "policy_number": p.policy_number,
                "client_name": p.client.name,
                "client_document": p.client.document_number,
                "policy_type": p.policy_type.name,
                "start_date": p.start_date.isoformat(),
                "end_date": p.end_date.isoformat(),
                "premium": str(p.premium),
                "status": p.computed_status,
                "status_display": p.computed_status_display,
                "is_renewable": p.is_renewable,
            })

        return JsonResponse({"results": data})
