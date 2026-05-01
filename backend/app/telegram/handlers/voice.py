import io
from telegram import Update
from telegram.ext import ContextTypes


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import process_dump_for_chat_id, get_pending_steps_task_id
    from app.services.openai_client import get_openai_client as _get_openai_client

    chat_id = update.effective_chat.id
    await update.message.reply_text("🎙️ Transcribing your voice note...")

    # Download voice file from Telegram
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    buf = io.BytesIO()
    await file.download_to_memory(buf)
    buf.seek(0)
    buf.name = "voice.ogg"

    # Transcribe with Whisper
    client = _get_openai_client()
    try:
        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=buf,
        )
        text = transcript.text.strip()
    except Exception:
        await update.message.reply_text("⚠️ Couldn't transcribe that. Try again or type instead.")
        return

    if not text:
        await update.message.reply_text("🤔 Couldn't make out any words. Try again.")
        return

    await update.message.reply_text(f"📝 Heard: _{text}_", parse_mode="Markdown")

    # Check if we're waiting for steps
    pending_steps = await get_pending_steps_task_id(chat_id)
    has_pending_steps = pending_steps is not None

    # Run intent classifier — don't assume dump
    from app.telegram import intent as intent_module
    intent = await intent_module.classify_intent(text, has_pending_steps=has_pending_steps)

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
    if intent == "add_task":
        from app.telegram.db_helpers import add_single_task_for_chat_id
        task = await add_single_task_for_chat_id(chat_id, text)
        if task:
            deadline_str = f" — due {task.deadline.strftime('%a %b %d')}" if task.deadline else ""
            await update.message.reply_text(
                f"✅ Added: *{task.title}*{deadline_str}\n\nUse /today to see your priority.",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "🤔 Couldn't parse that. Try: _'add essay due Friday'_",
                parse_mode="Markdown",
            )
        return
    if intent == "steps_reply" and has_pending_steps:
        from app.telegram.handlers.message import handle_message
        await handle_message(update, context)
        return

    # Default: brain dump
    await update.message.reply_text("⏳ Parsing tasks...")
    tasks = await process_dump_for_chat_id(chat_id, text)

    if tasks is None:
        await update.message.reply_text("⚠️ Your account isn't linked. Send /start to connect.")
        return
    if not tasks:
        await update.message.reply_text("🤔 No tasks found in that. Try being more specific.")
        return

    lines = [f"✅ Got {len(tasks)} task{'s' if len(tasks) != 1 else ''}:\n"]
    for t in tasks:
        lines.append(f"• {t.title}")
    lines.append("\nSend /today to see your priority task.")
    await update.message.reply_text("\n".join(lines))
