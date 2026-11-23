"""Fechas y horas. Toda la aplicación trabaja en UTC y guarda datetimes "ingenuos" (sin zona)."""
from datetime import datetime, timezone


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
