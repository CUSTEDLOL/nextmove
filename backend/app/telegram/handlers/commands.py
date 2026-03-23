from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.database import SessionLocal
    from app.models import User
    chat_id = update.effective_chat.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()
    if not user:
        await update.message.reply_text(
            "You're not linked yet. Send your registered email to connect."
        )
        return
    from app.config import settings
    display_name = user.name if user.name else "there"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Today's task", callback_data="today")],
        [InlineKeyboardButton("🧠 Brain dump", callback_data="dump")],
        [InlineKeyboardButton("✅ All tasks", callback_data="tasks")],
        [InlineKeyboardButton("✏️ Edit a task", callback_data="edit")],
        [InlineKeyboardButton("🌐 Open on web", url=settings.web_url)],
    ])
    await update.message.reply_text(
        f"👋 Hey *{display_name}*! What do you want to do?",
        parse_mode="Markdown",
        reply_markup=markup,
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.handlers.today import today_command as _today
    await _today(update, context)


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import list_tasks_for_chat_id
    chat_id = update.effective_chat.id
    tasks = await list_tasks_for_chat_id(chat_id)
    if tasks is None:
        await update.message.reply_text("You're not linked yet. Send your registered email.")
        return
    if not tasks:
        await update.message.reply_text("📭 No pending tasks. Use /dump to add some.")
        return
    await update.message.reply_text(f"📋 *Your tasks* ({len(tasks)} pending):", parse_mode="Markdown")
    for t in tasks:
        deadline_str = f" — due {t.deadline.strftime('%a %b %d')}" if t.deadline else ""
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Done", callback_data=f"done:{t.id}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{t.id}"),
        ]])
        await update.message.reply_text(
            f"*{t.title}*{deadline_str}",
            parse_mode="Markdown",
            reply_markup=markup,
        )


async def dump_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 Go ahead — tell me everything on your plate:\n"
        "_assignments, deadlines, meetings, anything_",
        parse_mode="Markdown",
    )


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import complete_top_task_for_chat_id
    chat_id = update.effective_chat.id
    task = await complete_top_task_for_chat_id(chat_id)
    if task:
        await update.message.reply_text(
            f"✅ Marked *{task.title}* as done. Nice work!",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("🎉 No pending tasks — you're all clear!")


async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import skip_top_task_for_chat_id
    chat_id = update.effective_chat.id
    task = await skip_top_task_for_chat_id(chat_id)
    if task:
        await update.message.reply_text(
            f"⏭️ Pushed *{task.title}* aside.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("Nothing to skip right now.")


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import list_tasks_for_chat_id
    chat_id = update.effective_chat.id
    tasks = await list_tasks_for_chat_id(chat_id)
    if tasks is None:
        await update.message.reply_text("You're not linked yet.")
        return
    if not tasks:
        await update.message.reply_text("📭 No tasks to edit.")
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


async def web_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.config import settings
    await update.message.reply_text(
        "Open NextMove in your browser:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Open NextMove", url=settings.web_url)
        ]]),
    )
