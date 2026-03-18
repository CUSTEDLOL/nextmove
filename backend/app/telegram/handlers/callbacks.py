from telegram import Update
from telegram.ext import ContextTypes


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "today":
        from app.telegram.handlers.today import today_command
        await today_command(update, context)
    elif data == "dump":
        await query.message.reply_text(
            "🧠 Send me your brain dump — everything on your plate:"
        )
    elif data.startswith("done:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import complete_task_for_chat_id
        chat_id = update.effective_chat.id
        ok = await complete_task_for_chat_id(chat_id, task_id)
        if ok:
            await query.edit_message_text("✅ Marked complete! Use /today to see your next task.")
        else:
            await query.edit_message_text("⚠️ Couldn't find that task.")
    elif data.startswith("skip:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import reschedule_task_for_chat_id
        chat_id = update.effective_chat.id
        ok = await reschedule_task_for_chat_id(chat_id, task_id)
        if ok:
            await query.edit_message_text("⏭️ Task rescheduled. Use /today to see what's next.")
        else:
            await query.edit_message_text("⚠️ Couldn't reschedule that task.")
