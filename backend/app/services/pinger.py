"""
Bot ping — runs every hour, detects tasks stuck as primary for 2+ days,
sends a Telegram nudge to the user.
"""
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models import User, Task
from app.services.task_service import ACTIVE_TASK_STATUSES
from app.telegram.utils import esc as _esc


async def ping_procrastinating_users():
    from app.telegram.bot import get_application
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    cutoff = datetime.utcnow() - timedelta(days=2)

    with SessionLocal() as db:
        stale_tasks = (
            db.query(Task)
            .join(User, Task.user_id == User.id)
            .filter(
                Task.status.in_(ACTIVE_TASK_STATUSES),
                Task.parent_task_id.is_(None),
                Task.created_at <= cutoff,
                User.telegram_chat_id.isnot(None),
            )
            .order_by(Task.user_id, Task.priority_index.desc())
            .all()
        )

        seen_users: set = set()
        to_ping: list[tuple[int, Task]] = []
        for task in stale_tasks:
            user = db.get(User, task.user_id)
            if user and user.telegram_chat_id not in seen_users:
                seen_users.add(user.telegram_chat_id)
                to_ping.append((user.telegram_chat_id, task))

    if not to_ping:
        return

    app = get_application()

    for chat_id, task in to_ping:
        days_old = (datetime.utcnow() - task.created_at).days
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Done", callback_data=f"done:{task.id}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{task.id}"),
            InlineKeyboardButton("📋 Steps", callback_data=f"steps:{task.id}"),
        ]])
        await app.bot.send_message(
            chat_id=chat_id,
            text=(
                f"👀 Hey — *{_esc(task.title)}* has been sitting on your plate for {days_old} days\\.\n\n"
                f"Still relevant\\? Make a move on it or skip it\\."
            ),
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
        )
