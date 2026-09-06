from django.contrib import admin

from .models import Client, Policy, PolicyType


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "document_number", "email", "phone")
    search_fields = ("name", "document_number", "email")


@admin.register(PolicyType)
class PolicyTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ("policy_number", "client", "policy_type", "start_date", "end_date", "premium", "status")
    list_filter = ("status", "policy_type")
    search_fields = ("policy_number", "client__name", "client__document_number")
    raw_id_fields = ("client",)
