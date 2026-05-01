from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.database import SessionLocal
from app.models import User
from app.telegram.utils import esc as _esc


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

    # Unlinked user — check if they sent their email
    if not user:
        if "@" in text and "." in text:
            await _handle_email_link(update, text, chat_id)
        else:
            await update.message.reply_text(
                "👋 Hey\\! I'm *NextMove*\\.\n\n"
                "To get started, reply with the email you used to register on the web app:",
                parse_mode="MarkdownV2",
            )
        return

    from app.telegram.db_helpers import get_pending_steps_task_id, get_pending_edit_task_id

    # Priority 1: waiting for steps input
    pending_steps = await get_pending_steps_task_id(chat_id)
    if pending_steps is not None:
        from app.telegram.db_helpers import add_steps_for_chat_id, clear_pending_steps
        try:
            created = await add_steps_for_chat_id(chat_id, str(pending_steps), text)
        finally:
            await clear_pending_steps(chat_id)
        if not created:
            await update.message.reply_text(
                "🤔 Couldn't parse steps\\. Try: `prepare slides, review notes`",
                parse_mode="MarkdownV2",
            )
        else:
            lines = [f"✅ Added {len(created)} step{'s' if len(created) != 1 else ''}:\n"]
            for s in created:
                lines.append(f"• {_esc(s)}")
            await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")
        return

    # Priority 2: waiting for edit input
    pending_edit = await get_pending_edit_task_id(chat_id)
    if pending_edit is not None:
        from app.telegram.db_helpers import apply_task_edit, clear_pending_edit
        from app.services.ai_editor import parse_edit_instruction
        try:
            edit = await parse_edit_instruction(text)
            if edit is None:
                await update.message.reply_text(
                    "🤔 Couldn't understand that edit\\.\n"
                    "Try: _'deadline is Friday'_, _'rename to X'_, or _'delete'_",
                    parse_mode="MarkdownV2",
                )
                return
            ok = await apply_task_edit(chat_id, str(pending_edit), edit)
            if ok:
                if edit["field"] == "delete":
                    msg = "🗑️ Task deleted\\."
                elif edit["field"] == "deadline":
                    msg = f"✅ Deadline updated to *{_esc(edit['value'])}*\\."
                else:
                    msg = f"✅ Renamed to *{_esc(edit['value'])}*\\."
                await update.message.reply_text(msg, parse_mode="MarkdownV2")
            else:
                await update.message.reply_text(
                    "⚠️ Couldn't apply that edit\\. The task may have been deleted\\.",
                    parse_mode="MarkdownV2",
                )
        finally:
            await clear_pending_edit(chat_id)
        return

    # Priority 3: intent classification
    from app.telegram import intent as intent_module
    intent = await intent_module.classify_intent(text, has_pending_steps=False)

    if intent == "add_task":
        from app.telegram.db_helpers import add_single_task_for_chat_id
        task = await add_single_task_for_chat_id(chat_id, text)
        if task:
            deadline_str = f" — due {_esc(task.deadline.strftime('%a %b %d'))}" if task.deadline else ""
            await update.message.reply_text(
                f"✅ Added: *{_esc(task.title)}*{deadline_str}\n\nUse /today to see your priority\\.",
                parse_mode="MarkdownV2",
            )
        else:
            await update.message.reply_text(
                "🤔 Couldn't parse that\\. Try: _'add essay due Friday'_",
                parse_mode="MarkdownV2",
            )
        return

    if intent == "complete":
        from app.telegram.handlers.commands import done_command
        await done_command(update, context)
        return

    if intent == "skip":
        from app.telegram.handlers.commands import skip_command
        await skip_command(update, context)
        return

    if intent == "today":
        from app.telegram.handlers.today import today_command
        await today_command(update, context)
        return

    if intent == "list":
        from app.telegram.handlers.commands import list_command
        await list_command(update, context)
        return

    if intent == "unclear":
        await update.message.reply_text(
            "🤔 Not sure what to do with that\\.\n\n"
            "Try: _'essay due Friday'_ to add tasks, or use /menu to see all options\\.",
            parse_mode="MarkdownV2",
        )
        return

    # Default: brain dump
    await update.message.reply_text("⏳ On it\\.\\.\\.", parse_mode="MarkdownV2")
    from app.telegram.db_helpers import process_dump_for_chat_id
    tasks = await process_dump_for_chat_id(chat_id, text)
    if not tasks:
        await update.message.reply_text(
            "🤔 Couldn't find any tasks in that\\.\n"
            "Try: _'essay due Friday, lab report Monday'_\n\n"
            "Use /menu to see all options\\.",
            parse_mode="MarkdownV2",
        )
    else:
        lines = [f"✅ Added {len(tasks)} task{'s' if len(tasks) > 1 else ''}:\n"]
        for t in tasks:
            lines.append(f"• {_esc(t.title)}")
        lines.append("\nUse /today to see your priority\\.")
        await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")


async def _handle_email_link(update, email: str, chat_id: int):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.strip().lower()).first()
        if not user:
            await update.effective_message.reply_text(
                "📬 If that email is registered, your account is now linked\\. "
                "If nothing happens, make sure you've signed up at the web app first\\.",
                parse_mode="MarkdownV2",
            )
            return
        user.telegram_chat_id = chat_id
        db.commit()
    finally:
        db.close()

    await update.effective_message.reply_text(
        "📬 If that email is registered, your account is now linked\\. "
        "If nothing happens, make sure you've signed up at the web app first\\.",
        parse_mode="MarkdownV2",
    )
    await update.effective_message.reply_text(
        f"✅ You're all set, *{_esc(user.name or 'there')}*\\! What do you want to do?",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Today's task", callback_data="today")],
            [InlineKeyboardButton("🧠 Brain dump", callback_data="dump")],
            [InlineKeyboardButton("✅ All tasks", callback_data="tasks")],
        ])
    )
