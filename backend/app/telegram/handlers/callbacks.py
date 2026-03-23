from telegram import Update
from telegram.ext import ContextTypes


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id

    if data == "today":
        from app.telegram.handlers.today import today_command
        await today_command(update, context)

    elif data == "tasks":
        from app.telegram.db_helpers import list_tasks_for_chat_id
        tasks = await list_tasks_for_chat_id(chat_id)
        if not tasks:
            await query.message.reply_text("📭 No tasks yet. Tell me what's on your plate and I'll track it.")
        else:
            lines = [f"📋 *Your tasks* ({len(tasks)} pending):\n"]
            for i, t in enumerate(tasks, 1):
                deadline_str = f" — due {t.deadline.strftime('%b %d')}" if t.deadline else ""
                lines.append(f"{i}. {t.title}{deadline_str}")
            await query.message.reply_text("\n".join(lines), parse_mode="Markdown")

    elif data == "dump":
        await query.message.reply_text(
            "🧠 Go ahead — tell me everything on your plate:"
        )

    elif data.startswith("done:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import complete_task_for_chat_id
        ok = await complete_task_for_chat_id(chat_id, task_id)
        if ok:
            await query.edit_message_text("✅ Done! What's next?")
        else:
            await query.edit_message_text("⚠️ Couldn't find that task.")

    elif data.startswith("skip:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import reschedule_task_for_chat_id
        ok = await reschedule_task_for_chat_id(chat_id, task_id)
        if ok:
            await query.edit_message_text("⏭️ Pushed aside. Ask me what's next when you're ready.")
        else:
            await query.edit_message_text("⚠️ Couldn't reschedule that task.")

    elif data.startswith("steps:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import get_steps_for_chat_id, set_pending_steps
        result = await get_steps_for_chat_id(chat_id, task_id)
        if result is None:
            await query.answer("Couldn't find that task.", show_alert=True)
            return
        parent, steps = result
        if not steps:
            text = (
                f"📋 *{parent.title}*\n\n"
                "No steps yet. Reply with what needs to happen:\n"
                "_e.g. prepare slides, rehearse, send reminder_"
            )
        else:
            done = sum(1 for s in steps if s["status"] == "completed")
            lines = [f"📋 *{parent.title}* — {done}/{len(steps)} done\n"]
            for s in steps:
                check = "✅" if s["status"] == "completed" else "⬜"
                lines.append(f"{check} {s['title']}")
            text = "\n".join(lines)
        # Persist steps-waiting state to DB so it survives server restarts
        await set_pending_steps(chat_id, task_id)
        await query.message.reply_text(text, parse_mode="Markdown")

    elif data.startswith("why:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import why_task_for_chat_id
        explanation = await why_task_for_chat_id(chat_id, task_id)
        await query.answer(explanation or "Couldn't find that task.", show_alert=True)

    elif data.startswith("edit_select:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import set_pending_edit
        from app.database import SessionLocal
        from app.models import Task
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            title = task.title if task else "that task"
        finally:
            db.close()
        await set_pending_edit(chat_id, task_id)
        await query.message.reply_text(
            f"✏️ Editing: *{title}*\n\n"
            "What do you want to change?\n"
            "_e.g. 'deadline is Friday', 'rename to Study for finals', 'delete'_",
            parse_mode="Markdown",
        )

    elif data == "edit":
        from app.telegram.handlers.commands import edit_command
        await edit_command(update, context)
