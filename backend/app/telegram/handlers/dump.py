from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

AWAITING_DUMP = 1


async def dump_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 *Brain dump mode*\n\n"
        "Tell me everything on your plate — assignments, deadlines, anything.\n\n"
        "Just type it all in one message:",
        parse_mode="Markdown"
    )
    return AWAITING_DUMP


async def receive_dump(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    await update.message.reply_text("⏳ Parsing your tasks...")

    from app.telegram.db_helpers import process_dump_for_chat_id
    tasks = await process_dump_for_chat_id(chat_id, text)

    if tasks is None:
        await update.message.reply_text(
            "⚠️ Your account isn't linked. Visit the web app to connect Telegram."
        )
        return ConversationHandler.END

    if not tasks:
        await update.message.reply_text("🤔 I couldn't find any tasks in that. Try being more specific.")
        return ConversationHandler.END

    lines = [f"✅ Got it! Added {len(tasks)} task{'s' if len(tasks) > 1 else ''}:\n"]
    for t in tasks:
        lines.append(f"• {t.title}")
    lines.append("\nUse /today to see your priority task.")
    await update.message.reply_text("\n".join(lines))
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END
