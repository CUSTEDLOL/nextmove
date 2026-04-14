"""
APScheduler jobs for proactive Telegram notifications.
Scheduled in main.py lifespan alongside the existing pinger job.
"""
import logging
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.user import User
from app.models.task import Task
from app.services import task_service
from app.services.notifier import (
    build_morning_brief,
    build_evening_wrapup,
    build_weekly_summary,
)

logger = logging.getLogger(__name__)

_bot = None  # Set at startup via set_bot()


def set_bot(bot) -> None:
    global _bot
    _bot = bot


async def _send_telegram_message(chat_id: int, text: str) -> None:
    if _bot is None:
        logger.warning("Notification bot not set — skipping message to %s", chat_id)
        return
    try:
        await _bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error("Failed to send Telegram message to %s: %s", chat_id, e)


async def morning_brief_job() -> None:
    """8:00 UTC daily: Send today's #1 task to every linked user."""
    logger.info("Running morning_brief_job")
    with SessionLocal() as db:
        users = db.query(User).filter(User.telegram_chat_id.isnot(None)).all()
        for user in users:
            if not user.telegram_chat_id:
                continue
            try:
                today = task_service.get_today(db, user)
                msg = build_morning_brief(
                    user.name or "there",
                    today.primary,
                    today.secondary,
                )
                await _send_telegram_message(user.telegram_chat_id, msg)
            except Exception as e:
                logger.error("morning_brief failed for user %s: %s", user.id, e)


async def evening_wrapup_job() -> None:
    """21:00 UTC daily: Report completed vs missed tasks today."""
    logger.info("Running evening_wrapup_job")
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)

    with SessionLocal() as db:
        users = db.query(User).filter(User.telegram_chat_id.isnot(None)).all()
        for user in users:
            if not user.telegram_chat_id:
                continue
            try:
                completed = (
                    db.query(Task)
                    .filter(
                        Task.user_id == user.id,
                        Task.status == "completed",
                        Task.updated_at >= today_start,
                        Task.updated_at < tomorrow_start,
                        Task.parent_task_id.is_(None),
                    )
                    .count()
                )
                missed = (
                    db.query(Task)
                    .filter(
                        Task.user_id == user.id,
                        Task.status == "missed",
                        Task.updated_at >= today_start,
                        Task.updated_at < tomorrow_start,
                        Task.parent_task_id.is_(None),
                    )
                    .count()
                )
                msg = build_evening_wrapup(completed, missed)
                await _send_telegram_message(user.telegram_chat_id, msg)
            except Exception as e:
                logger.error("evening_wrapup failed for user %s: %s", user.id, e)


async def weekly_summary_job() -> None:
    """19:00 UTC Sunday: Weekly wrap-up stats."""
    logger.info("Running weekly_summary_job")
    week_start = datetime.utcnow() - timedelta(days=7)

    with SessionLocal() as db:
        users = db.query(User).filter(User.telegram_chat_id.isnot(None)).all()
        for user in users:
            if not user.telegram_chat_id:
                continue
            try:
                completed = (
                    db.query(Task)
                    .filter(
                        Task.user_id == user.id,
                        Task.status == "completed",
                        Task.updated_at >= week_start,
                        Task.parent_task_id.is_(None),
                    )
                    .count()
                )
                missed = (
                    db.query(Task)
                    .filter(
                        Task.user_id == user.id,
                        Task.status == "missed",
                        Task.updated_at >= week_start,
                        Task.parent_task_id.is_(None),
                    )
                    .count()
                )
                msg = build_weekly_summary(user.name or "there", completed, missed, [])
                await _send_telegram_message(user.telegram_chat_id, msg)
            except Exception as e:
                logger.error("weekly_summary failed for user %s: %s", user.id, e)
