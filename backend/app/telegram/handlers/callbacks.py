from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
        from app.telegram.handlers.commands import list_command
        await list_command(update, context)

    elif data == "dump":
        await query.message.reply_text(
            "🧠 Go ahead — tell me everything on your plate:"
        )

    # ---- Done ---------------------------------------------------------------
    elif data.startswith("done:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import complete_task_for_chat_id
        ok = await complete_task_for_chat_id(chat_id, task_id)
        if ok:
            await query.edit_message_text("✅ Done! Great work 💪")
            from app.telegram.handlers.today import today_command
            await today_command(update, context)
        else:
            await query.edit_message_text("⚠️ Couldn't find that task.")

    # ---- Skip (confirmation flow) -------------------------------------------
    elif data.startswith("skip:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import get_task_for_chat_id
        task = await get_task_for_chat_id(chat_id, task_id)
        title = task.title if task else "this task"
        await query.message.reply_text(
            f"🗑️ Remove *{title}* from your list permanently?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🗑️ Yes, remove it", callback_data=f"skip_confirm:{task_id}"),
                    InlineKeyboardButton("Cancel", callback_data="skip_cancel"),
                ]
            ])
        )

    elif data.startswith("skip_confirm:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import delete_task_for_chat_id
        ok = await delete_task_for_chat_id(chat_id, task_id)
        if ok:
            await query.edit_message_text("🗑️ Removed. What's next?")
            from app.telegram.handlers.today import today_command
            await today_command(update, context)
        else:
            await query.edit_message_text("⚠️ Couldn't remove that task.")

    elif data == "skip_cancel":
        await query.edit_message_text("Okay, keeping it on your list.")

    # ---- Reschedule (pick date flow) ----------------------------------------
    elif data.startswith("reschedule:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import get_task_for_chat_id
        task = await get_task_for_chat_id(chat_id, task_id)
        title = task.title if task else "this task"
        now = datetime.utcnow()
        days_to_saturday = (5 - now.weekday()) % 7 or 7
        await query.message.reply_text(
            f"📅 When should I push *{title}* to?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Tomorrow", callback_data=f"reschedule_pick:{task_id}:1"),
                    InlineKeyboardButton("In 3 days", callback_data=f"reschedule_pick:{task_id}:3"),
                ],
                [
                    InlineKeyboardButton("This weekend", callback_data=f"reschedule_pick:{task_id}:{days_to_saturday}"),
                    InlineKeyboardButton("Next week", callback_data=f"reschedule_pick:{task_id}:7"),
                ],
            ])
        )

    elif data.startswith("reschedule_pick:"):
        _, task_id, offset_str = data.split(":", 2)
        offset_days = int(offset_str)
        new_deadline = datetime.utcnow() + timedelta(days=offset_days)
        from app.telegram.db_helpers import reschedule_task_for_chat_id
        task = await reschedule_task_for_chat_id(chat_id, task_id, new_deadline)
        if task:
            label = new_deadline.strftime("%A %b %d")
            await query.edit_message_text(
                f"✅ *{task.title}* pushed to {label}.",
                parse_mode="Markdown"
            )
            from app.telegram.handlers.today import today_command
            await today_command(update, context)
        else:
            await query.edit_message_text("⚠️ Couldn't reschedule that task.")

    # ---- Start task ---------------------------------------------------------
    elif data.startswith("start:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import start_task_for_chat_id
        task = await start_task_for_chat_id(chat_id, task_id)
        if task:
            await query.edit_message_text(
                f"▶️ Started *{task.title}*. Go get it! 💪",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("⚠️ Couldn't find that task.")

    # ---- Steps --------------------------------------------------------------
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
            await set_pending_steps(chat_id, task_id)
            await query.message.reply_text(text, parse_mode="Markdown")
        else:
            done_count = sum(1 for s in steps if s["status"] == "completed")
            lines = [f"📋 *{parent.title}* — {done_count}/{len(steps)} done\n"]
            buttons = []
            for s in steps:
                check = "✅" if s["status"] == "completed" else "⬜"
                lines.append(f"{check} {s['title']}")
                if s["status"] != "completed":
                    buttons.append([
                        InlineKeyboardButton(
                            f"✅ {s['title'][:35]}",
                            callback_data=f"step_done:{s['id']}"
                        )
                    ])
            await set_pending_steps(chat_id, task_id)
            await query.message.reply_text(
                "\n".join(lines),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
            )

    elif data.startswith("step_done:"):
        step_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import complete_step_for_chat_id
        ok = await complete_step_for_chat_id(chat_id, step_id)
        if ok:
            await query.edit_message_text("✅ Step done!")
        else:
            await query.answer("Couldn't find that step.", show_alert=True)

    # ---- Why? ---------------------------------------------------------------
    elif data.startswith("why:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import why_task_for_chat_id
        explanation = await why_task_for_chat_id(chat_id, task_id)
        await query.message.reply_text(
            explanation or "Couldn't explain that task.",
            parse_mode="Markdown"
        )

    # ---- Task actions (from /list) ------------------------------------------
    elif data.startswith("task_actions:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import get_task_for_chat_id
        task = await get_task_for_chat_id(chat_id, task_id)
        if not task:
            await query.answer("Task not found.", show_alert=True)
            return
        deadline_str = f" — due {task.deadline.strftime('%a %b %d')}" if task.deadline else ""
        await query.message.reply_text(
            f"*{task.title}*{deadline_str}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Done", callback_data=f"done:{task_id}"),
                    InlineKeyboardButton("🗑️ Skip", callback_data=f"skip:{task_id}"),
                ],
                [
                    InlineKeyboardButton("🔄 Reschedule", callback_data=f"reschedule:{task_id}"),
                    InlineKeyboardButton("✏️ Edit", callback_data=f"edit_select:{task_id}"),
                ],
            ])
        )

    # ---- Edit ---------------------------------------------------------------
    elif data.startswith("edit_select:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import set_pending_edit, get_task_for_chat_id
        task = await get_task_for_chat_id(chat_id, task_id)
        title = task.title if task else "that task"
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
