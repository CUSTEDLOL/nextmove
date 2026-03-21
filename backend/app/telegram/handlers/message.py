from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.database import SessionLocal
from app.models import User


def _get_user_by_chat_id(chat_id: int):
    """Synchronous user lookup — called before async work begins."""
    db = SessionLocal()
    try:
        return db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()

    user = _get_user_by_chat_id(chat_id)

    if not user:
        if "@" in text and "." in text:
            await _handle_email_link(update, text, chat_id)
        else:
            await update.effective_message.reply_text(
                "👋 Hey! I'm *NextMove* — your personal study planner.\n\n"
                "To get started, reply with the email you used to register on the web app:",
                parse_mode="Markdown"
            )
        return

    from app.telegram.db_helpers import get_pending_steps_task_id
    from app.telegram.intent import classify_intent

    pending_task_id = await get_pending_steps_task_id(chat_id)
    intent = await classify_intent(text, has_pending_steps=pending_task_id is not None)

    if intent == "today":
        from app.telegram.handlers.today import today_command
        await today_command(update, context)

    elif intent == "dump":
        await update.effective_message.reply_text("⏳ On it...")
        from app.telegram.db_helpers import process_dump_for_chat_id
        tasks = await process_dump_for_chat_id(chat_id, text)
        if not tasks:
            await update.effective_message.reply_text(
                "🤔 Hmm, I couldn't pull any tasks from that. "
                "Try something like: *'I have an essay due Friday and a lab report Monday'*",
                parse_mode="Markdown"
            )
        else:
            lines = [f"✅ Got it — added {len(tasks)} task{'s' if len(tasks) > 1 else ''}:\n"]
            for t in tasks:
                lines.append(f"• {t.title}")
            lines.append("\nWhat's next? I can show you *today's priority* or just keep going.")
            await update.effective_message.reply_text(
                "\n".join(lines),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🎯 Show today's task", callback_data="today")
                ]])
            )

    elif intent == "complete":
        from app.telegram.db_helpers import complete_top_task_for_chat_id
        task = await complete_top_task_for_chat_id(chat_id)
        if task:
            await update.effective_message.reply_text(
                f"✅ Marked *{task.title}* as done. Nice work!\n\nSend me what's next on your plate, or ask what to focus on.",
                parse_mode="Markdown"
            )
        else:
            await update.effective_message.reply_text("🎉 No pending tasks — you're all clear!")

    elif intent == "skip":
        from app.telegram.db_helpers import skip_top_task_for_chat_id
        task = await skip_top_task_for_chat_id(chat_id)
        if task:
            await update.effective_message.reply_text(
                f"⏭️ Pushed *{task.title}* aside. It'll come back when the time is right.",
                parse_mode="Markdown"
            )
        else:
            await update.effective_message.reply_text("Nothing to skip right now.")

    elif intent == "list":
        from app.telegram.db_helpers import list_tasks_for_chat_id
        tasks = await list_tasks_for_chat_id(chat_id)
        if not tasks:
            await update.effective_message.reply_text(
                "📭 No tasks yet. Tell me what's on your plate and I'll track it."
            )
        else:
            lines = [f"📋 *Your tasks* ({len(tasks)} pending):\n"]
            for i, t in enumerate(tasks, 1):
                deadline_str = f" — due {t.deadline.strftime('%b %d')}" if t.deadline else ""
                lines.append(f"{i}. {t.title}{deadline_str}")
            await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")

    elif intent == "steps_reply":
        from app.telegram.db_helpers import add_steps_for_chat_id, clear_pending_steps
        created = await add_steps_for_chat_id(chat_id, str(pending_task_id), text)
        await clear_pending_steps(chat_id)
        if not created:
            await update.effective_message.reply_text(
                "🤔 Couldn't parse steps from that. Try: `prepare slides, review notes`"
            )
        else:
            lines = [f"✅ Added {len(created)} step{'s' if len(created) != 1 else ''}:\n"]
            for s in created:
                lines.append(f"• {s}")
            await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")

    else:  # unclear
        await update.effective_message.reply_text(
            "Tell me what's on your plate — assignments, meetings, deadlines — and I'll sort it out for you."
        )


async def _handle_email_link(update, email: str, chat_id: int):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.strip().lower()).first()
        if not user:
            await update.effective_message.reply_text(
                "⚠️ No account found with that email. Make sure you've registered at the web app first, then try again."
            )
            return
        user.telegram_chat_id = chat_id
        db.commit()
        await update.effective_message.reply_text(
            f"✅ Linked! Welcome, *{user.name}*.\n\n"
            "Just tell me what's on your plate and I'll take it from there.",
            parse_mode="Markdown"
        )
    finally:
        db.close()
