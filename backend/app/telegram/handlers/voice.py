import io
from telegram import Update
from telegram.ext import ContextTypes


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import process_dump_for_chat_id
    from app.telegram.intent import _get_openai_client

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

    await update.message.reply_text(f"📝 Heard: _{text}_\n\n⏳ Parsing tasks...", parse_mode="Markdown")

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
