import io
from telegram import Update
from telegram.ext import ContextTypes
from app.telegram.utils import esc as _esc


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import process_dump_for_chat_id, get_pending_steps_task_id
    from app.services.openai_client import get_openai_client

    chat_id = update.effective_chat.id
    await update.message.reply_text("🎙️ Transcribing your voice note\\.\\.\\.", parse_mode="MarkdownV2")

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    buf = io.BytesIO()
    await file.download_to_memory(buf)
    buf.seek(0)
    buf.name = "voice.ogg"

    client = get_openai_client()
    try:
        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=buf,
        )
        text = transcript.text.strip()
    except Exception:
        await update.message.reply_text(
            "⚠️ Couldn't transcribe that\\. Try again or type instead\\.",
            parse_mode="MarkdownV2",
        )
        return

    if not text:
        await update.message.reply_text("🤔 Couldn't make out any words\\. Try again\\.", parse_mode="MarkdownV2")
        return

    await update.message.reply_text(f"📝 Heard: _{_esc(text)}_", parse_mode="MarkdownV2")

    pending_steps = await get_pending_steps_task_id(chat_id)
    has_pending_steps = pending_steps is not None

    from app.telegram import intent as intent_module
    intent = await intent_module.classify_intent(text, has_pending_steps=has_pending_steps)

    if intent == "steps_reply" and has_pending_steps:
        from app.telegram.handlers.message import handle_message
        await handle_message(update, context)
        return

    from app.telegram.handlers.dispatch import dispatch_intent
    if await dispatch_intent(intent, text, chat_id, update, context):
        return

    # Default: brain dump
    await update.message.reply_text("⏳ Parsing tasks\\.\\.\\.", parse_mode="MarkdownV2")
    tasks = await process_dump_for_chat_id(chat_id, text)

    if tasks is None:
        await update.message.reply_text(
            "⚠️ Your account isn't linked\\. Send /start to connect\\.",
            parse_mode="MarkdownV2",
        )
        return
    if not tasks:
        await update.message.reply_text(
            "🤔 No tasks found in that\\. Try being more specific\\.",
            parse_mode="MarkdownV2",
        )
        return

    lines = [f"✅ Got {len(tasks)} task{'s' if len(tasks) != 1 else ''}:\n"]
    for t in tasks:
        lines.append(f"• {_esc(t.title)}")
    lines.append("\nSend /today to see your priority task\\.")
    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")
