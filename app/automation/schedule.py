"""Deterministic schedule contracts independent of runner-local time."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

ISTANBUL = ZoneInfo("Europe/Istanbul")
UTC = ZoneInfo("UTC")
FRIDAY_DIGEST_CRON = "0 6 * * 5"


def friday_digest_utc(local_date: datetime) -> datetime:
    """Return 09:00 Europe/Istanbul converted to UTC for the supplied Friday."""
    localized = datetime.combine(local_date.date(), time(9), tzinfo=ISTANBUL)
    if localized.weekday() != 4:
        raise ValueError("founder digest schedule requires a Friday")
    return localized.astimezone(UTC)
