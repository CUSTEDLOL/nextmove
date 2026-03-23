from telegram import Update
from telegram.ext import ContextTypes


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.database import SessionLocal
    from app.models import User
    from app.telegram.handlers.commands import menu_command
    chat_id = update.effective_chat.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()

    if user:
        await menu_command(update, context)
        return

    await update.message.reply_text(
        "👋 Welcome to *NextMove*!\n\n"
        "To link your account, reply with the email you registered with on the web app.\n\n"
        "_Already linked? Use /menu to get started._",
        parse_mode="Markdown",
    )
