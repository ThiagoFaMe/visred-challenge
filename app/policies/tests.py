"""
Automated tests for the policies app.

Covers:
  • Model validations (Client, Policy)
  • Renewal business logic (atomic transaction)
  • View filtering & search
  • QuerySet helpers (active, expired, renewed)
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, RequestFactory
from django.urls import reverse

from .models import Client, Policy, PolicyStatus, PolicyType


class ClientModelTest(TestCase):
    """Tests for Client model validations."""

    def test_valid_client_creation(self):
        client = Client(
            name="María García",
            email="maria@example.com",
            phone="+54 351 4567890",
            document_number="30123456",
        )
        client.full_clean()  # should not raise
        client.save()
        self.assertEqual(Client.objects.count(), 1)

    def test_document_number_must_be_digits_only(self):
        client = Client(
            name="Test User",
            email="test@example.com",
            phone="123456",
            document_number="ABC123",
        )
        with self.assertRaises(ValidationError) as ctx:
            client.full_clean()
        self.assertIn("document_number", ctx.exception.message_dict)

    def test_name_cannot_contain_numbers(self):
        client = Client(
            name="John123",
            email="john@example.com",
            phone="123456",
            document_number="99999999",
        )
        with self.assertRaises(ValidationError) as ctx:
            client.full_clean()
        self.assertIn("name", ctx.exception.message_dict)

    def test_duplicate_email_raises_error(self):
        Client.objects.create(
            name="User One",
            email="same@example.com",
            phone="111",
            document_number="11111111",
        )
        client2 = Client(
            name="User Two",
            email="same@example.com",
            phone="222",
            document_number="22222222",
        )
        with self.assertRaises(Exception):
            client2.save()

    def test_duplicate_document_number_raises_error(self):
        Client.objects.create(
            name="User One",
            email="one@example.com",
            phone="111",
            document_number="11111111",
        )
        client2 = Client(
            name="User Two",
            email="two@example.com",
            phone="222",
            document_number="11111111",
        )
        with self.assertRaises(Exception):
            client2.save()


class PolicyModelTest(TestCase):
    """Tests for Policy model validations and computed properties."""

    def setUp(self):
        self.client_obj = Client.objects.create(
            name="Test Client",
            email="test@example.com",
            phone="+54 351 1234567",
            document_number="12345678",
        )
        self.policy_type = PolicyType.objects.create(
            name="Auto", description="Vehicle coverage"
        )

    def test_end_date_must_be_after_start_date(self):
        policy = Policy(
            policy_number="POL-TEST-001",
            client=self.client_obj,
            policy_type=self.policy_type,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 1, 1),  # before start!
            premium=Decimal("10000"),
            status=PolicyStatus.ACTIVE,
        )
        with self.assertRaises(ValidationError) as ctx:
            policy.full_clean()
        self.assertIn("end_date", ctx.exception.message_dict)

    def test_computed_status_expired_when_past_end_date(self):
        policy = Policy.objects.create(
            policy_number="POL-TEST-002",
            client=self.client_obj,
            policy_type=self.policy_type,
            start_date=date.today() - timedelta(days=400),
            end_date=date.today() - timedelta(days=35),
            premium=Decimal("20000"),
            status=PolicyStatus.ACTIVE,
        )
        self.assertEqual(policy.computed_status, PolicyStatus.EXPIRED)

    def test_computed_status_active_when_future_end_date(self):
        policy = Policy.objects.create(
            policy_number="POL-TEST-003",
            client=self.client_obj,
            policy_type=self.policy_type,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=335),
            premium=Decimal("15000"),
            status=PolicyStatus.ACTIVE,
        )
        self.assertEqual(policy.computed_status, PolicyStatus.ACTIVE)

    def test_is_renewable_for_active_and_expired(self):
        active = Policy.objects.create(
            policy_number="POL-REN-001",
            client=self.client_obj,
            policy_type=self.policy_type,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            premium=Decimal("10000"),
            status=PolicyStatus.ACTIVE,
        )
        self.assertTrue(active.is_renewable)

        renewed = Policy.objects.create(
            policy_number="POL-REN-002",
            client=self.client_obj,
            policy_type=self.policy_type,
            start_date=date.today() - timedelta(days=730),
            end_date=date.today() - timedelta(days=365),
            premium=Decimal("10000"),
            status=PolicyStatus.RENEWED,
        )
        self.assertFalse(renewed.is_renewable)


class PolicyQuerySetTest(TestCase):
    """Tests for the custom PolicyQuerySet methods."""

    def setUp(self):
        self.client_obj = Client.objects.create(
            name="QS Client",
            email="qs@example.com",
            phone="123",
            document_number="99998888",
        )
        self.ptype = PolicyType.objects.create(name="Hogar")

    def test_active_queryset_excludes_past_end_date(self):
        # Still stored as ACTIVE but end_date passed → should NOT appear in .active()
        Policy.objects.create(
            policy_number="POL-QS-001",
            client=self.client_obj,
            policy_type=self.ptype,
            start_date=date.today() - timedelta(days=400),
            end_date=date.today() - timedelta(days=35),
            premium=Decimal("5000"),
            status=PolicyStatus.ACTIVE,
        )
        self.assertEqual(Policy.objects.active().count(), 0)

    def test_expired_queryset_includes_auto_expired(self):
        Policy.objects.create(
            policy_number="POL-QS-002",
            client=self.client_obj,
            policy_type=self.ptype,
            start_date=date.today() - timedelta(days=400),
            end_date=date.today() - timedelta(days=35),
            premium=Decimal("5000"),
            status=PolicyStatus.ACTIVE,
        )
        self.assertEqual(Policy.objects.expired().count(), 1)


class PolicyRenewalTest(TestCase):
    """Tests for the policy renewal business logic."""

    def setUp(self):
        self.client_obj = Client.objects.create(
            name="Renewal Client",
            email="renew@example.com",
            phone="+54 11 1234567",
            document_number="44556677",
        )
        self.ptype = PolicyType.objects.create(name="Vida")
        self.original_policy = Policy.objects.create(
            policy_number="POL-2026-RENEW",
            client=self.client_obj,
            policy_type=self.ptype,
            start_date=date.today() - timedelta(days=180),
            end_date=date.today() + timedelta(days=185),
            premium=Decimal("25000.00"),
            status=PolicyStatus.ACTIVE,
        )

    def test_renewal_creates_new_policy_and_marks_original(self):
        url = reverse("policy-renew", kwargs={"pk": self.original_policy.pk})
        response = self.client.post(url)

        # Original should now be RENEWED
        self.original_policy.refresh_from_db()
        self.assertEqual(self.original_policy.status, PolicyStatus.RENEWED)

        # A new policy should exist
        new_policy = Policy.objects.get(policy_number="POL-2026-RENEW-R1")
        self.assertEqual(new_policy.status, PolicyStatus.ACTIVE)
        self.assertEqual(new_policy.client, self.client_obj)
        self.assertEqual(new_policy.policy_type, self.ptype)
        self.assertEqual(new_policy.premium, Decimal("25000.00"))
        self.assertEqual(new_policy.start_date, self.original_policy.end_date)
        self.assertEqual(
            new_policy.end_date,
            self.original_policy.end_date + timedelta(days=365),
        )

    def test_renewed_policy_cannot_be_renewed_again(self):
        # First renewal
        url = reverse("policy-renew", kwargs={"pk": self.original_policy.pk})
        self.client.post(url)

        # Try to renew the already-renewed original
        response = self.client.post(url)
        # Should redirect with an error, no new policy created
        self.assertEqual(Policy.objects.count(), 2)  # original + 1 renewal only


class PolicyViewFilterTest(TestCase):
    """Tests for the policy list view with filters."""

    def setUp(self):
        self.client_obj = Client.objects.create(
            name="Filter Client",
            email="filter@example.com",
            phone="555",
            document_number="77889900",
        )
        self.ptype = PolicyType.objects.create(name="Comercio")

        # Active policy
        Policy.objects.create(
            policy_number="POL-FILT-001",
            client=self.client_obj,
            policy_type=self.ptype,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=335),
            premium=Decimal("10000"),
            status=PolicyStatus.ACTIVE,
        )
        # Expired policy (auto-detected)
        Policy.objects.create(
            policy_number="POL-FILT-002",
            client=self.client_obj,
            policy_type=self.ptype,
            start_date=date.today() - timedelta(days=400),
            end_date=date.today() - timedelta(days=35),
            premium=Decimal("8000"),
            status=PolicyStatus.ACTIVE,
        )

    def test_filter_active_returns_only_active(self):
        response = self.client.get(reverse("policy-list"), {"status": "active"})
        self.assertEqual(response.status_code, 200)
        policies = response.context["policies"]
        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0].policy_number, "POL-FILT-001")

    def test_filter_expired_returns_auto_expired(self):
        response = self.client.get(reverse("policy-list"), {"status": "expired"})
        self.assertEqual(response.status_code, 200)
        policies = response.context["policies"]
        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0].policy_number, "POL-FILT-002")

    def test_search_by_client_name(self):
        response = self.client.get(
            reverse("policy-list"), {"search": "Filter"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["policies"]), 2)

    def test_search_by_policy_number(self):
        response = self.client.get(
            reverse("policy-list"), {"search": "FILT-001"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["policies"]), 1)
