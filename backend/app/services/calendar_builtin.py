from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from app.services.scheduler import FreeSlot

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    import uuid


def get_builtin_free_slots(
    user_id: "uuid.UUID",
    date: datetime,
    study_start: int = 9,
    study_end: int = 22,
    db: "Session" = None,
    tz_str: str = "UTC",
) -> list[FreeSlot]:
    """Find free time blocks using the built-in calendar (no Google).

    `date` is a naive UTC datetime.  We convert it to the user's local
    timezone, compute the study window in local time, then convert back
    to naive UTC for storage — so blocks land at the correct wall-clock
    hours for the user.
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        tz = ZoneInfo(tz_str)
    except (ZoneInfoNotFoundError, KeyError):
        tz = ZoneInfo("UTC")

    utc_dt = date.replace(tzinfo=ZoneInfo("UTC"))
    local_dt = utc_dt.astimezone(tz)

    local_day_start = local_dt.replace(hour=study_start, minute=0, second=0, microsecond=0)
    local_day_end = local_dt.replace(hour=study_end, minute=0, second=0, microsecond=0)

    # Convert back to naive UTC for DB storage
    day_start = local_day_start.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    day_end = local_day_end.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    if db is None:
        return [FreeSlot(start=day_start, end=day_end)]

    from app.models import CalendarEvent
    events = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.user_id == user_id,
            CalendarEvent.start_time < day_end,
            CalendarEvent.end_time > day_start,
        )
        .order_by(CalendarEvent.start_time)
        .all()
    )

    free = []
    cursor = day_start
    for e in events:
        if cursor < e.start_time:
            free.append(FreeSlot(start=cursor, end=e.start_time))
        cursor = max(cursor, e.end_time)
    if cursor < day_end:
        free.append(FreeSlot(start=cursor, end=day_end))

    return free
