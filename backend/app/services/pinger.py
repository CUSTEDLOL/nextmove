"""
Bot ping — runs every hour, detects tasks with missed schedule blocks today
(in the user's local timezone), and sends a single Telegram nudge per task per day.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import uuid

from app.database import SessionLocal
from app.models import NotificationLog, ScheduleBlock, Task, User


ACTIVE_TASK_STATUSES = ["pending", "scheduled", "in_progress"]
_MISSED_BLOCK_PREFIX = "missed_block:"


def _notification_type(task_id: uuid.UUID) -> str:
    return f"{_MISSED_BLOCK_PREFIX}{task_id}"


def _user_tz(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _user_day_bounds_utc(user: User, now: datetime) -> tuple[datetime, datetime]:
    """Return (today_start, tomorrow_start) as naive UTC for the user's local timezone."""
    tz = _user_tz(user)
    utc = ZoneInfo("UTC")
    local_now = now.replace(tzinfo=utc).astimezone(tz)
    local_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc = local_today.astimezone(utc).replace(tzinfo=None)
    tomorrow_utc = (local_today + timedelta(days=1)).astimezone(utc).replace(tzinfo=None)
    return today_utc, tomorrow_utc


def _format_block_end(block_end_time: datetime, user: User) -> str:
    """Format a naive-UTC datetime as local time for the user (no timezone label)."""
    tz = _user_tz(user)
    local_dt = block_end_time.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    hour = local_dt.hour % 12 or 12
    ampm = "AM" if local_dt.hour < 12 else "PM"
    return f"{hour}:{local_dt.minute:02d} {ampm}"


def _already_pinged_today(
    db,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    today_start: datetime,
    tomorrow_start: datetime,
) -> bool:
    return (
        db.query(NotificationLog.id)
        .filter(
            NotificationLog.user_id == user_id,
            NotificationLog.type == _notification_type(task_id),
            NotificationLog.sent_at >= today_start,
            NotificationLog.sent_at < tomorrow_start,
        )
        .first()
        is not None
    )


async def ping_procrastinating_users(*, _now: datetime | None = None) -> None:
    """
    _now is injectable for testing; production callers omit it.
    """
    db = SessionLocal()
    try:
        now = _now or datetime.now(timezone.utc).replace(tzinfo=None)

        # Widen the query window by one full day so users in far-east timezones
        # whose local "today" started up to ~14 h before UTC midnight are included.
        # Python-level timezone filtering below narrows it to each user's local day.
        window_start = now - timedelta(days=1)

        missed_task_rows = (
            db.query(Task, User, ScheduleBlock.end_time)
            .join(User, Task.user_id == User.id)
            .join(ScheduleBlock, ScheduleBlock.task_id == Task.id)
            .filter(
                Task.status.in_(ACTIVE_TASK_STATUSES),
                Task.parent_task_id.is_(None),
                ScheduleBlock.end_time >= window_start,
                ScheduleBlock.end_time <= now,
                User.telegram_chat_id.isnot(None),
            )
            .order_by(ScheduleBlock.end_time.desc(), Task.priority_index.desc())
            .all()
        )

        seen_tasks: set[uuid.UUID] = set()
        to_ping: list[tuple[User, Task, datetime]] = []
        for task, user, block_end_time in missed_task_rows:
            if task.id in seen_tasks:
                continue
            today_start, tomorrow_start = _user_day_bounds_utc(user, now)
            if not (today_start <= block_end_time < tomorrow_start):
                continue
            seen_tasks.add(task.id)
            if _already_pinged_today(db, user.id, task.id, today_start, tomorrow_start):
                continue
            to_ping.append((user, task, block_end_time))

        if not to_ping:
            return

        # Write all notification logs before sending. If a Telegram send fails,
        # the log already exists and prevents a re-ping on the next hourly run.
        for user, task, _ in to_ping:
            db.add(NotificationLog(
                user_id=user.id,
                type=_notification_type(task.id),
            ))
        db.commit()

        from app.telegram.bot import get_application
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        app = get_application()

        for user, task, block_end_time in to_ping:
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Done", callback_data=f"done:{task.id}"),
                InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{task.id}"),
                InlineKeyboardButton("📋 Steps", callback_data=f"steps:{task.id}"),
            ]])
            try:
                await app.bot.send_message(
                    chat_id=user.telegram_chat_id,
                    text=(
                        f"👀 You missed your scheduled block for *{task.title}*.\n\n"
                        f"It was supposed to wrap at {_format_block_end(block_end_time, user)}. "
                        f"Mark it done, add steps, or skip it."
                    ),
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            except Exception:
                continue
    finally:
        db.close()
