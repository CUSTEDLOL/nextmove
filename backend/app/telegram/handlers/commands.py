from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.config import settings
from app.telegram.utils import esc as _esc


async def _clear_conversation_state(chat_id: int):
    from app.telegram.db_helpers import clear_pending_state
    await clear_pending_state(chat_id)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.database import SessionLocal
    from app.models import User
    chat_id = update.effective_chat.id
    await _clear_conversation_state(chat_id)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()
    if not user:
        await update.message.reply_text(
            "You're not linked yet\\. Send your registered email to connect\\.",
            parse_mode="MarkdownV2",
        )
        return
    display_name = user.name or "there"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Today's task", callback_data="today")],
        [InlineKeyboardButton("🧠 Brain dump", callback_data="dump")],
        [InlineKeyboardButton("✅ All tasks", callback_data="tasks")],
        [InlineKeyboardButton("✏️ Edit a task", callback_data="edit")],
        [InlineKeyboardButton("🌐 Open dashboard", url=f"{settings.web_url}/dashboard")],
    ])
    await update.message.reply_text(
        f"👋 Hey *{_esc(display_name)}*\\! What do you want to do?",
        parse_mode="MarkdownV2",
        reply_markup=markup,
    )


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import list_tasks_for_chat_id
    chat_id = update.effective_chat.id
    await _clear_conversation_state(chat_id)
    target = update.effective_message
    tasks = await list_tasks_for_chat_id(chat_id)
    if tasks is None:
        await target.reply_text("You're not linked yet\\. Send your registered email\\.", parse_mode="MarkdownV2")
        return
    if not tasks:
        await target.reply_text("📭 No tasks yet\\. Use /dump to add some\\.", parse_mode="MarkdownV2")
        return

    lines = [f"📋 *Your tasks* \\({len(tasks)} total\\):\n"]
    for i, t in enumerate(tasks, 1):
        deadline_str = f" — due {_esc(t.deadline.strftime('%b %d'))}" if t.deadline else ""
        status_icon = "▶️ " if t.status == "in_progress" else ""
        lines.append(f"{i}\\. {status_icon}{_esc(t.title)}{deadline_str}")
    lines.append("\nTap a task to manage it, or use /today to see your \\#1 priority\\.")

    await target.reply_text(
        "\n".join(lines),
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{i}. {t.title[:30]}", callback_data=f"task_actions:{t.id}")]
            for i, t in enumerate(tasks[:8], 1)
        ])
    )


async def dump_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _clear_conversation_state(update.effective_chat.id)
    await update.message.reply_text(
        "🧠 Go ahead — tell me everything on your plate:\n"
        "_assignments, deadlines, meetings, anything_",
        parse_mode="MarkdownV2",
    )


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import complete_top_task_for_chat_id
    chat_id = update.effective_chat.id
    await _clear_conversation_state(chat_id)
    task = await complete_top_task_for_chat_id(chat_id)
    if task:
        await update.message.reply_text(
            f"✅ Marked *{_esc(task.title)}* as done\\. Nice work\\!",
            parse_mode="MarkdownV2",
        )
    else:
        await update.message.reply_text("🎉 No pending tasks — you're all clear\\!", parse_mode="MarkdownV2")


async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import skip_top_task_for_chat_id
    chat_id = update.effective_chat.id
    await _clear_conversation_state(chat_id)
    task = await skip_top_task_for_chat_id(chat_id)
    if task:
        await update.message.reply_text(
            f"⏭️ Pushed *{_esc(task.title)}* aside\\.",
            parse_mode="MarkdownV2",
        )
    else:
        await update.message.reply_text("Nothing to skip right now\\.", parse_mode="MarkdownV2")


async def web_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌐 Open your dashboard:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Open NextMove", url=f"{settings.web_url}/dashboard")
        ]])
    )


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import list_tasks_for_chat_id
    chat_id = update.effective_chat.id
    await _clear_conversation_state(chat_id)
    tasks = await list_tasks_for_chat_id(chat_id)
    if tasks is None:
        await update.message.reply_text("You're not linked yet\\.", parse_mode="MarkdownV2")
        return
    if not tasks:
        await update.message.reply_text("📭 No tasks to edit\\.", parse_mode="MarkdownV2")
        return
    buttons = [
        [InlineKeyboardButton(
            t.title[:40] + ("…" if len(t.title) > 40 else ""),
            callback_data=f"edit_select:{t.id}"
        )]
        for t in tasks
    ]
    await update.message.reply_text(
        "✏️ Which task do you want to edit?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
