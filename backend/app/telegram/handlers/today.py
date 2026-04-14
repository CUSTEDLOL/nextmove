from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.schemas.tasks import TaskResponse


def format_today_message(primary: Optional[TaskResponse], secondary: list[TaskResponse]) -> str:
    if not primary:
        return "✅ All clear! No pending tasks. Send me a brain dump to get started."

    lines = [f"🎯 *Today's focus:*\n*{primary.title}*"]
    if primary.effort:
        lines.append(f"   ⚡ Effort: {primary.effort.capitalize()}")
    if primary.deadline:
        lines.append(f"   📅 Due: {primary.deadline.strftime('%a %b %d')}")

    if secondary:
        lines.append("\n📋 *Also on deck:*")
        for i, t in enumerate(secondary, 1):
            lines.append(f"   {i}. {t.title}")

    lines.append("\n_Say *done* when finished, or just tell me what else is on your plate._")
    return "\n".join(lines)


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import get_today_for_chat_id
    chat_id = update.effective_chat.id
    result = await get_today_for_chat_id(chat_id)
    target = update.effective_message
    if result is None:
        await target.reply_text(
            "⚠️ You're not linked yet. Visit the web app to connect your Telegram account.",
            parse_mode="Markdown"
        )
        return
    primary, secondary = result
    msg = format_today_message(primary, secondary)
    keyboard = []
    if primary:
        keyboard.append([
            InlineKeyboardButton("✅ Done", callback_data=f"done:{primary.id}"),
            InlineKeyboardButton("🗑️ Skip", callback_data=f"skip:{primary.id}"),
        ])
        keyboard.append([
            InlineKeyboardButton("🔄 Reschedule", callback_data=f"reschedule:{primary.id}"),
            InlineKeyboardButton("▶️ Start", callback_data=f"start:{primary.id}"),
        ])
        keyboard.append([
            InlineKeyboardButton("📋 Steps", callback_data=f"steps:{primary.id}"),
            InlineKeyboardButton("❓ Why?", callback_data=f"why:{primary.id}"),
        ])
    markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await target.reply_text(msg, parse_mode="Markdown", reply_markup=markup)
