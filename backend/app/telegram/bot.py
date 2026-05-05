from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from app.config import settings

_application: Application | None = None


def create_application() -> Application:
    from app.telegram.handlers.commands import (
        menu_command, list_command, dump_command,
        done_command, skip_command, edit_command, web_command,
    )
    from app.telegram.handlers.today import today_command
    from app.telegram.handlers.message import handle_message
    from app.telegram.handlers.callbacks import handle_callback
    from app.telegram.handlers.voice import handle_voice
    from app.telegram.handlers.start import start_command

    application = Application.builder().token(settings.telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("dump", dump_command))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(CommandHandler("skip", skip_command))
    application.add_handler(CommandHandler("edit", edit_command))
    application.add_handler(CommandHandler("web", web_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return application


def get_application() -> Application:
    global _application
    if _application is None:
        _application = create_application()
    return _application
