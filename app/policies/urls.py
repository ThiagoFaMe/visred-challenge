"""URL configuration for the policies app."""

from django.urls import path

from . import views

urlpatterns = [
    # Dashboard
    path("", views.DashboardView.as_view(), name="dashboard"),

    # --- Clients -----------------------------------------------------------
    path("clientes/", views.ClientListView.as_view(), name="client-list"),
    path("clientes/nuevo/", views.ClientCreateView.as_view(), name="client-create"),
    path("clientes/<int:pk>/", views.ClientDetailView.as_view(), name="client-detail"),
    path("clientes/<int:pk>/editar/", views.ClientUpdateView.as_view(), name="client-update"),
    path("clientes/<int:pk>/eliminar/", views.ClientDeleteView.as_view(), name="client-delete"),

    # --- Policies ----------------------------------------------------------
    path("polizas/", views.PolicyListView.as_view(), name="policy-list"),
    path("polizas/nueva/", views.PolicyCreateView.as_view(), name="policy-create"),
    path("polizas/<int:pk>/editar/", views.PolicyUpdateView.as_view(), name="policy-update"),
    path("polizas/<int:pk>/eliminar/", views.PolicyDeleteView.as_view(), name="policy-delete"),
    path("polizas/<int:pk>/renovar/", views.PolicyRenewView.as_view(), name="policy-renew"),

    # --- API (Bonus: AJAX filtering) ---------------------------------------
    path("api/polizas/", views.PolicyApiListView.as_view(), name="api-policy-list"),
]
