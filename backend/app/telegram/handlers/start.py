from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.config import settings
    from app.database import SessionLocal
    from app.models.user import User
    from app.telegram.handlers.commands import menu_command

    chat_id = update.effective_chat.id
    args = context.args  # tokens passed after /start

    if args:
        token = args[0]
        from app.telegram.link_service import consume_web_link_token
        user_id = consume_web_link_token(token)
        if user_id:
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.telegram_chat_id = chat_id
                    db.commit()
            finally:
                db.close()
            await update.message.reply_text(
                "✅ Your account is connected\\! Here's your menu:",
                parse_mode="MarkdownV2",
            )
            await menu_command(update, context)
            return
        await update.message.reply_text(
            "❌ That link has expired\\. Go to Settings in the web app and click *Connect Telegram* again\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🌐 Open Settings", url=f"{settings.web_url}/settings")
            ]])
        )
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()

    if user:
        await menu_command(update, context)
        return

    await update.message.reply_text(
        "👋 Welcome to *NextMove*\\!\n\n"
        "To connect your account, open the web app and click *Connect Telegram* in Settings\\.",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Open NextMove", url=f"{settings.web_url}/settings")
        ]])
    )
