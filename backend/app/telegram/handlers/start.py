from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


def _main_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Today's task", callback_data="today")],
        [InlineKeyboardButton("🧠 Brain dump", callback_data="dump")],
        [InlineKeyboardButton("✅ All tasks", callback_data="tasks")],
    ])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.database import SessionLocal
    from app.models import User
    chat_id = update.effective_chat.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()

    if user:
        await update.message.reply_text(
            f"👋 Welcome back, *{user.name}*!\n\nWhat do you want to do?",
            reply_markup=_main_menu_markup(),
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        "👋 Welcome to *NextMove*!\n\n"
        "To link your account, reply with the email you registered with on the web app:",
        parse_mode="Markdown"
    )
