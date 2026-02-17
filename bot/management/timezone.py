from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo
from bot.management.settings import get_settings


def get_timezone():
    settings = get_settings()
    return ZoneInfo(settings.timezone)


def now():
    return datetime.now(get_timezone())


def utcnow():
    return datetime.now(dt_timezone.utc)
