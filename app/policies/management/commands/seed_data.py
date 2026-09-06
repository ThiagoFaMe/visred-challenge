"""
Management command to populate the database with sample data.

Usage:
    python manage.py seed_data

Idempotent: checks for existing data before creating.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from policies.models import Client, Policy, PolicyStatus, PolicyType


class Command(BaseCommand):
    help = "Populate the database with sample clients, policy types, and policies."

    def handle(self, *args, **options):
        self.stdout.write("Creando datos de prueba...")

        # -- Policy Types ---------------------------------------------------
        types_data = [
            ("Auto", "Cobertura para vehículos automotores."),
            ("Hogar", "Cobertura para viviendas y contenido."),
            ("Vida", "Seguro de vida individual."),
            ("Salud", "Cobertura médica y hospitalaria."),
            ("Comercio", "Cobertura para locales y actividades comerciales."),
        ]
        policy_types = {}
        for name, desc in types_data:
            pt, created = PolicyType.objects.get_or_create(
                name=name, defaults={"description": desc}
            )
            policy_types[name] = pt
            status = "creado" if created else "ya existía"
            self.stdout.write(f"  Tipo: {name} — {status}")

        # -- Clients --------------------------------------------------------
        clients_data = [
            ("María García", "maria.garcia@example.com", "+54 351 4567890", "30123456"),
            ("Juan Pérez", "juan.perez@example.com", "+54 11 98765432", "28765432"),
            ("Ana López", "ana.lopez@example.com", "+54 261 5551234", "35987654"),
            ("Carlos Rodríguez", "carlos.rodriguez@example.com", "+54 341 4443210", "27654321"),
            ("Laura Fernández", "laura.fernandez@example.com", "+54 351 7778899", "33456789"),
        ]
        clients = {}
        for name, email, phone, doc in clients_data:
            c, created = Client.objects.get_or_create(
                document_number=doc,
                defaults={"name": name, "email": email, "phone": phone},
            )
            clients[doc] = c
            status = "creado" if created else "ya existía"
            self.stdout.write(f"  Cliente: {name} — {status}")

        # -- Policies -------------------------------------------------------
        today = date.today()
        policies_data = [
            # (number, client_doc, type_name, start_offset_days, end_offset_days, premium, status)
            # Active policies (end_date in the future)
            ("POL-2026-0001", "30123456", "Auto", -180, 185, "45000.00", PolicyStatus.ACTIVE),
            ("POL-2026-0002", "28765432", "Hogar", -90, 275, "32000.00", PolicyStatus.ACTIVE),
            ("POL-2026-0003", "35987654", "Vida", -30, 335, "18500.00", PolicyStatus.ACTIVE),
            ("POL-2026-0004", "33456789", "Salud", -60, 305, "55000.00", PolicyStatus.ACTIVE),
            # Expired policies (end_date in the past, still stored as ACTIVE → computed as expired)
            ("POL-2025-0010", "27654321", "Auto", -400, -35, "38000.00", PolicyStatus.ACTIVE),
            ("POL-2025-0011", "30123456", "Comercio", -500, -135, "72000.00", PolicyStatus.ACTIVE),
            # Explicitly expired
            ("POL-2025-0012", "28765432", "Vida", -600, -235, "15000.00", PolicyStatus.EXPIRED),
            # Renewed policy chain
            ("POL-2025-0020", "35987654", "Hogar", -730, -365, "28000.00", PolicyStatus.RENEWED),
            ("POL-2025-0020-R1", "35987654", "Hogar", -365, 0, "28000.00", PolicyStatus.RENEWED),
            ("POL-2025-0020-R2", "35987654", "Hogar", 0, 365, "30000.00", PolicyStatus.ACTIVE),
        ]

        for number, doc, type_name, start_off, end_off, premium, stat in policies_data:
            p, created = Policy.objects.get_or_create(
                policy_number=number,
                defaults={
                    "client": clients[doc],
                    "policy_type": policy_types[type_name],
                    "start_date": today + timedelta(days=start_off),
                    "end_date": today + timedelta(days=end_off),
                    "premium": Decimal(premium),
                    "status": stat,
                },
            )
            status = "creada" if created else "ya existía"
            self.stdout.write(f"  Póliza: {number} ({stat}) — {status}")

        self.stdout.write(self.style.SUCCESS("\n✓ Datos de prueba cargados exitosamente."))
