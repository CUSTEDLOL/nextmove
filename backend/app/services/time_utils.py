from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.user import User


def user_tz(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def user_day_bounds_utc(user: User, now: datetime) -> tuple[datetime, datetime]:
    """Return (today_start, tomorrow_start) as naive UTC for the user's local timezone."""
    tz = user_tz(user)
    utc = ZoneInfo("UTC")
    local_now = now.replace(tzinfo=utc).astimezone(tz)
    local_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc = local_today.astimezone(utc).replace(tzinfo=None)
    tomorrow_utc = (local_today + timedelta(days=1)).astimezone(utc).replace(tzinfo=None)
    return today_utc, tomorrow_utc
