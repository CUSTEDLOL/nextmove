from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from app.config import settings

_application: Application | None = None


def create_application() -> Application:
    from app.telegram.handlers.start import start_command
    from app.telegram.handlers.message import handle_message
    from app.telegram.handlers.callbacks import handle_callback
    from app.telegram.handlers.voice import handle_voice

    application = Application.builder().token(settings.telegram_bot_token).build()

    # /start is the only command — shows menu for known users, prompts email for new ones
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    # Catch-all text handler — pure conversational routing
    application.add_handler(MessageHandler(filters.TEXT, handle_message))

    return application


def get_application() -> Application:
    global _application
    if _application is None:
        _application = create_application()
    return _application
