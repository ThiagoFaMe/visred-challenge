import time

from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    """Block until the default database accepts connections."""

    help = "Waits for the database to be available."

    def handle(self, *args, **options):
        max_attempts = 30
        for attempt in range(1, max_attempts + 1):
            try:
                connections["default"].ensure_connection()
            except OperationalError:
                self.stdout.write(f"DB no disponible, reintentando ({attempt})...")
                time.sleep(1)
            else:
                self.stdout.write(self.style.SUCCESS("DB disponible."))
                return
        self.stderr.write("No se pudo conectar a la base de datos.")
        raise SystemExit(1)
