"""
Bot ping — runs every hour.
Sends a Telegram nudge when a task has a missed schedule block today
(block end time has passed but the task is still active).
One notification per task per calendar day (per the user's local timezone).
"""
import logging
from datetime import datetime

from app.database import SessionLocal
from app.models import User, Task
from app.models.schedule import ScheduleBlock
from app.models.logs import NotificationLog
from app.services.task_service import ACTIVE_TASK_STATUSES
from app.services.time_utils import user_day_bounds_utc
from app.telegram.utils import esc as _esc

logger = logging.getLogger(__name__)


async def ping_procrastinating_users(_now: datetime = None):
    """
    Ping users who have a task with a missed schedule block today.
    Logs each notification before sending so a failed send doesn't cause re-pings.
    """
    from app.telegram.bot import get_application
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    now = _now or datetime.utcnow()

    # (chat_id, task_id, task_title, user_id) — collected while session is open
    to_ping: list[tuple[int, str, str, object]] = []

    with SessionLocal() as db:
        users = db.query(User).filter(User.telegram_chat_id.isnot(None)).all()

        for user in users:
            today_start, tomorrow_start = user_day_bounds_utc(user, now)

            # Tasks with a block that has already ended today (but task is still active)
            missed_tasks = (
                db.query(Task)
                .join(ScheduleBlock, ScheduleBlock.task_id == Task.id)
                .filter(
                    Task.user_id == user.id,
                    Task.status.in_(ACTIVE_TASK_STATUSES),
                    Task.parent_task_id.is_(None),
                    ScheduleBlock.end_time >= today_start,
                    ScheduleBlock.end_time < now,
                    ScheduleBlock.end_time < tomorrow_start,
                )
                .all()
            )

            for task in missed_tasks:
                already_logged = (
                    db.query(NotificationLog)
                    .filter(
                        NotificationLog.user_id == user.id,
                        NotificationLog.type == f"missed_block:{task.id}",
                        NotificationLog.sent_at >= today_start,
                        NotificationLog.sent_at < tomorrow_start,
                    )
                    .first()
                )
                if not already_logged:
                    to_ping.append((user.telegram_chat_id, str(task.id), task.title, user.id))

        # Commit logs before sending — prevents re-pings if send fails
        for chat_id, task_id, task_title, user_id in to_ping:
            db.add(NotificationLog(
                user_id=user_id,
                type=f"missed_block:{task_id}",
                sent_at=now,
            ))
        if to_ping:
            db.commit()

    if not to_ping:
        return

    app = get_application()
    for chat_id, task_id, task_title, user_id in to_ping:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Done", callback_data=f"done:{task_id}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{task_id}"),
            InlineKeyboardButton("📋 Steps", callback_data=f"steps:{task_id}"),
        ]])
        try:
            await app.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"👀 Hey — your scheduled block for *{_esc(task_title)}* just passed\\.\n\n"
                    f"Mark it done, add steps, or skip it\\."
                ),
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )
        except Exception as exc:
            logger.error("Failed to send pinger message to %s: %s", chat_id, exc)
