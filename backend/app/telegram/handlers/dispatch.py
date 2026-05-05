"""
Shared intent dispatcher used by both message.py (text) and voice.py.
Returns True if the intent was handled; False signals fall-through to brain-dump.
"""
from telegram import Update
from telegram.ext import ContextTypes
from app.telegram.utils import esc as _esc


async def dispatch_intent(
    intent: str,
    text: str,
    chat_id: int,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    if intent == "complete":
        from app.telegram.handlers.commands import done_command
        await done_command(update, context)
        return True

    if intent == "skip":
        from app.telegram.handlers.commands import skip_command
        await skip_command(update, context)
        return True

    if intent == "today":
        from app.telegram.handlers.today import today_command
        await today_command(update, context)
        return True

    if intent == "list":
        from app.telegram.handlers.commands import list_command
        await list_command(update, context)
        return True

    if intent == "add_task":
        from app.telegram.db_helpers import add_single_task_for_chat_id
        task = await add_single_task_for_chat_id(chat_id, text)
        target = update.effective_message
        if task:
            deadline_str = f" — due {_esc(task.deadline.strftime('%a %b %d'))}" if task.deadline else ""
            await target.reply_text(
                f"✅ Added: *{_esc(task.title)}*{deadline_str}\n\nUse /today to see your priority\\.",
                parse_mode="MarkdownV2",
            )
        else:
            await target.reply_text(
                "🤔 Couldn't parse that\\. Try: _'add essay due Friday'_",
                parse_mode="MarkdownV2",
            )
        return True

    if intent == "unclear":
        await update.effective_message.reply_text(
            "🤔 Not sure what to do with that\\.\n\n"
            "Try: _'essay due Friday'_ to add tasks, or use /menu to see all options\\.",
            parse_mode="MarkdownV2",
        )
        return True

    # intent == "dump" or unrecognized → caller handles brain-dump
    return False
