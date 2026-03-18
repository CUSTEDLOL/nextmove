from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, CallbackQueryHandler, filters
)
from app.config import settings
from app.telegram.handlers.dump import AWAITING_DUMP

_application = None


def create_application() -> Application:
    from app.telegram.handlers.start import start_command
    from app.telegram.handlers.today import today_command
    from app.telegram.handlers.dump import dump_command, receive_dump, cancel
    from app.telegram.handlers.callbacks import handle_callback

    application = Application.builder().token(settings.telegram_bot_token).build()

    # Brain dump conversation: /dump → user sends text → processed
    dump_conv = ConversationHandler(
        entry_points=[
            CommandHandler("dump", dump_command),
            MessageHandler(filters.Regex(r"(?i)^/dump"), dump_command),
        ],
        states={
            AWAITING_DUMP: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_dump)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(dump_conv)
    application.add_handler(CallbackQueryHandler(handle_callback))

    return application


def get_application() -> Application:
    global _application
    if _application is None:
        _application = create_application()
    return _application
