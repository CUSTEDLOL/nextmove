# Telegram Commands Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the conversational-only Telegram bot with a command-driven hybrid bot (slash commands + inline buttons), with brain dump as the only free-text input and a GPT-powered edit flow.

**Architecture:** 8 slash commands registered with Telegram autocomplete. `message.py` simplified to 3 modes: edit > steps > brain dump. New `ai_editor.py` service parses natural-language edit instructions into structured changes. New `pending_edit_task_id` DB column tracks edit state.

**Tech Stack:** python-telegram-bot v21, FastAPI, SQLAlchemy 2.x, Alembic, OpenAI gpt-4o-mini

---

## Task 1: Add `pending_edit_task_id` to User model + migration

**Files:**
- Modify: `backend/app/models/user.py`
- Create: `backend/alembic/versions/<hash>_add_pending_edit_task_id.py` (auto-generated)

**Step 1: Add column to User model**

In `backend/app/models/user.py`, add after `pending_steps_task_id`:

```python
pending_edit_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
```

**Step 2: Generate migration**

```bash
cd backend
source venv/bin/activate
set -a && source ../.env && set +a
alembic revision --autogenerate -m "add pending_edit_task_id to users"
```

Expected: new file in `alembic/versions/` with `op.add_column('users', ...)`.

**Step 3: Apply migration**

```bash
alembic upgrade head
```

Expected output: `Running upgrade 9840cbf1e284 -> <new_hash>, add pending_edit_task_id to users`

**Step 4: Commit**

```bash
git add backend/app/models/user.py backend/alembic/versions/
git commit -m "feat: add pending_edit_task_id column to users"
```

---

## Task 2: Add `web_url` to config

**Files:**
- Modify: `backend/app/config.py`

**Step 1: Add field**

In `backend/app/config.py`, add to `Settings`:

```python
web_url: str = "http://localhost:3000"
```

**Step 2: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add web_url to settings"
```

---

## Task 3: Add edit-mode helpers to db_helpers.py

**Files:**
- Modify: `backend/app/telegram/db_helpers.py`

**Step 1: Write failing test**

In `backend/tests/test_db_helpers.py`, add to the existing test file:

```python
@pytest.mark.asyncio
async def test_set_and_get_pending_edit(db_user, db_task):
    await set_pending_edit(db_user.telegram_chat_id, str(db_task.id))
    result = await get_pending_edit_task_id(db_user.telegram_chat_id)
    assert result == db_task.id

@pytest.mark.asyncio
async def test_clear_pending_edit(db_user, db_task):
    await set_pending_edit(db_user.telegram_chat_id, str(db_task.id))
    await clear_pending_edit(db_user.telegram_chat_id)
    result = await get_pending_edit_task_id(db_user.telegram_chat_id)
    assert result is None

@pytest.mark.asyncio
async def test_apply_task_edit_deadline(db_user, db_task):
    from datetime import datetime
    new_deadline = datetime(2026, 4, 1)
    ok = await apply_task_edit(db_user.telegram_chat_id, str(db_task.id), {"field": "deadline", "value": "2026-04-01"})
    assert ok is True

@pytest.mark.asyncio
async def test_apply_task_edit_title(db_user, db_task):
    ok = await apply_task_edit(db_user.telegram_chat_id, str(db_task.id), {"field": "title", "value": "New Title"})
    assert ok is True

@pytest.mark.asyncio
async def test_apply_task_edit_delete(db_user, db_task):
    ok = await apply_task_edit(db_user.telegram_chat_id, str(db_task.id), {"field": "delete"})
    assert ok is True
```

**Step 2: Run tests to confirm they fail**

```bash
cd backend && source venv/bin/activate
pytest tests/test_db_helpers.py -k "edit" -v
```

Expected: ImportError or NameError — functions don't exist yet.

**Step 3: Add helpers to db_helpers.py**

Append to `backend/app/telegram/db_helpers.py`:

```python
async def set_pending_edit(chat_id: int, task_id: str) -> None:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if user:
            user.pending_edit_task_id = uuid.UUID(task_id)
            db.commit()
    finally:
        db.close()


async def clear_pending_edit(chat_id: int) -> None:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if user:
            user.pending_edit_task_id = None
            db.commit()
    finally:
        db.close()


async def get_pending_edit_task_id(chat_id: int) -> Optional[uuid.UUID]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        return user.pending_edit_task_id if user else None
    finally:
        db.close()


async def apply_task_edit(chat_id: int, task_id: str, edit: dict) -> bool:
    """Apply a structured edit to a task. edit = {field: "deadline"|"title"|"delete", value: ...}"""
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return False
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
        if not task:
            return False
        field = edit.get("field")
        if field == "delete":
            db.delete(task)
        elif field == "title":
            task.title = edit["value"]
        elif field == "deadline":
            task.deadline = datetime.fromisoformat(edit["value"]) if edit.get("value") else None
        else:
            return False
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

**Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_db_helpers.py -k "edit" -v
```

Expected: 5 tests PASSED.

**Step 5: Commit**

```bash
git add backend/app/telegram/db_helpers.py backend/tests/test_db_helpers.py
git commit -m "feat: add edit-mode helpers to db_helpers"
```

---

## Task 4: Build ai_editor.py — parse natural language edit instructions

**Files:**
- Create: `backend/app/services/ai_editor.py`
- Create: `backend/tests/test_ai_editor.py`

**Step 1: Write failing test**

Create `backend/tests/test_ai_editor.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_parse_deadline_edit():
    from app.services.ai_editor import parse_edit_instruction
    with patch("app.services.ai_editor._get_openai_client") as mock:
        mock.return_value.chat.completions.create = AsyncMock(return_value=_mock_response('{"field":"deadline","value":"2026-04-04"}'))
        result = await parse_edit_instruction("deadline is this Friday")
    assert result["field"] == "deadline"

@pytest.mark.asyncio
async def test_parse_title_edit():
    from app.services.ai_editor import parse_edit_instruction
    with patch("app.services.ai_editor._get_openai_client") as mock:
        mock.return_value.chat.completions.create = AsyncMock(return_value=_mock_response('{"field":"title","value":"Study for finals"}'))
        result = await parse_edit_instruction("rename it to Study for finals")
    assert result["field"] == "title"
    assert result["value"] == "Study for finals"

@pytest.mark.asyncio
async def test_parse_delete_edit():
    from app.services.ai_editor import parse_edit_instruction
    with patch("app.services.ai_editor._get_openai_client") as mock:
        mock.return_value.chat.completions.create = AsyncMock(return_value=_mock_response('{"field":"delete"}'))
        result = await parse_edit_instruction("delete this")
    assert result["field"] == "delete"

@pytest.mark.asyncio
async def test_parse_invalid_returns_none():
    from app.services.ai_editor import parse_edit_instruction
    with patch("app.services.ai_editor._get_openai_client") as mock:
        mock.return_value.chat.completions.create = AsyncMock(return_value=_mock_response("not json"))
        result = await parse_edit_instruction("hello there")
    assert result is None

def _mock_response(content: str):
    from unittest.mock import MagicMock
    r = MagicMock()
    r.choices[0].message.content = content
    return r
```

**Step 2: Run to confirm fail**

```bash
pytest tests/test_ai_editor.py -v
```

Expected: ModuleNotFoundError.

**Step 3: Create ai_editor.py**

Create `backend/app/services/ai_editor.py`:

```python
import json
from datetime import datetime
from openai import AsyncOpenAI
from app.config import settings

_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


async def parse_edit_instruction(text: str) -> dict | None:
    """
    Parse a natural-language edit instruction into a structured dict.
    Returns one of:
      {"field": "deadline", "value": "YYYY-MM-DD"}
      {"field": "title", "value": "New title"}
      {"field": "delete"}
    Returns None if the instruction can't be parsed.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    client = _get_openai_client()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"Today is {today}. Parse a task edit instruction into JSON.\n"
                    "Return exactly one of these JSON shapes (no markdown, no extra text):\n"
                    '  {"field":"deadline","value":"YYYY-MM-DD"}  — if changing deadline\n'
                    '  {"field":"title","value":"new title"}       — if renaming\n'
                    '  {"field":"delete"}                          — if deleting\n'
                    "If unsure, return null."
                ),
            },
            {"role": "user", "content": text},
        ],
        max_tokens=60,
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    try:
        result = json.loads(raw)
        if result is None:
            return None
        if result.get("field") not in ("deadline", "title", "delete"):
            return None
        return result
    except (json.JSONDecodeError, AttributeError):
        return None
```

**Step 4: Run tests**

```bash
pytest tests/test_ai_editor.py -v
```

Expected: 4 tests PASSED.

**Step 5: Commit**

```bash
git add backend/app/services/ai_editor.py backend/tests/test_ai_editor.py
git commit -m "feat: ai_editor — parse natural language edit instructions"
```

---

## Task 5: Build commands.py — all 8 command handlers

**Files:**
- Create: `backend/app/telegram/handlers/commands.py`

**Step 1: Create commands.py**

Create `backend/app/telegram/handlers/commands.py`:

```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


def _main_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Today's task", callback_data="today")],
        [InlineKeyboardButton("🧠 Brain dump", callback_data="dump")],
        [InlineKeyboardButton("✅ All tasks", callback_data="tasks")],
        [InlineKeyboardButton("✏️ Edit a task", callback_data="edit")],
        [InlineKeyboardButton("🌐 Open on web", url_callback="web")],
    ])


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.database import SessionLocal
    from app.models import User
    chat_id = update.effective_chat.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()
    if not user:
        await update.message.reply_text(
            "You're not linked yet. Send your registered email to connect."
        )
        return
    from app.config import settings
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Today's task", callback_data="today")],
        [InlineKeyboardButton("🧠 Brain dump", callback_data="dump")],
        [InlineKeyboardButton("✅ All tasks", callback_data="tasks")],
        [InlineKeyboardButton("✏️ Edit a task", callback_data="edit")],
        [InlineKeyboardButton("🌐 Open on web", url=settings.web_url)],
    ])
    await update.message.reply_text(
        f"👋 Hey *{user.name}*! What do you want to do?",
        parse_mode="Markdown",
        reply_markup=markup,
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.handlers.today import today_command as _today
    await _today(update, context)


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import list_tasks_for_chat_id
    chat_id = update.effective_chat.id
    tasks = await list_tasks_for_chat_id(chat_id)
    if tasks is None:
        await update.message.reply_text("You're not linked yet. Send your registered email.")
        return
    if not tasks:
        await update.message.reply_text("📭 No pending tasks. Use /dump to add some.")
        return
    await update.message.reply_text(f"📋 *Your tasks* ({len(tasks)} pending):", parse_mode="Markdown")
    for t in tasks:
        deadline_str = f" — due {t.deadline.strftime('%a %b %d')}" if t.deadline else ""
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Done", callback_data=f"done:{t.id}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{t.id}"),
        ]])
        await update.message.reply_text(
            f"*{t.title}*{deadline_str}",
            parse_mode="Markdown",
            reply_markup=markup,
        )


async def dump_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 Go ahead — tell me everything on your plate:\n"
        "_assignments, deadlines, meetings, anything_",
        parse_mode="Markdown",
    )


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import complete_top_task_for_chat_id
    chat_id = update.effective_chat.id
    task = await complete_top_task_for_chat_id(chat_id)
    if task:
        await update.message.reply_text(
            f"✅ Marked *{task.title}* as done. Nice work!",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("🎉 No pending tasks — you're all clear!")


async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import skip_top_task_for_chat_id
    chat_id = update.effective_chat.id
    task = await skip_top_task_for_chat_id(chat_id)
    if task:
        await update.message.reply_text(
            f"⏭️ Pushed *{task.title}* aside.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("Nothing to skip right now.")


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import list_tasks_for_chat_id
    chat_id = update.effective_chat.id
    tasks = await list_tasks_for_chat_id(chat_id)
    if tasks is None:
        await update.message.reply_text("You're not linked yet.")
        return
    if not tasks:
        await update.message.reply_text("📭 No tasks to edit.")
        return
    buttons = [
        [InlineKeyboardButton(
            t.title[:40] + ("…" if len(t.title) > 40 else ""),
            callback_data=f"edit_select:{t.id}"
        )]
        for t in tasks
    ]
    await update.message.reply_text(
        "✏️ Which task do you want to edit?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def web_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.config import settings
    await update.message.reply_text(
        "Open NextMove in your browser:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Open NextMove", url=settings.web_url)
        ]]),
    )
```

**Step 2: Commit**

```bash
git add backend/app/telegram/handlers/commands.py
git commit -m "feat: add all 8 command handlers"
```

---

## Task 6: Handle `edit_select` callback + edit input in callbacks.py and message.py

**Files:**
- Modify: `backend/app/telegram/handlers/callbacks.py`
- Modify: `backend/app/telegram/handlers/message.py`

**Step 1: Add `edit_select` to callbacks.py**

In `handle_callback`, add before the final `else`:

```python
    elif data.startswith("edit_select:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import set_pending_edit, get_today_for_chat_id
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
```

**Step 2: Simplify message.py**

Replace the entire `handle_message` function body with this cleaner version:

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()

    user = _get_user_by_chat_id(chat_id)

    # Unlinked user — check if they sent their email
    if not user:
        if "@" in text and "." in text:
            await _handle_email_link(update, text, chat_id)
        else:
            await update.message.reply_text(
                "👋 Hey! I'm *NextMove*.\n\n"
                "To get started, reply with the email you used to register on the web app:",
                parse_mode="Markdown",
            )
        return

    from app.telegram.db_helpers import get_pending_steps_task_id, get_pending_edit_task_id

    # Priority 1: waiting for steps input
    pending_steps = await get_pending_steps_task_id(chat_id)
    if pending_steps is not None:
        from app.telegram.db_helpers import add_steps_for_chat_id, clear_pending_steps
        try:
            created = await add_steps_for_chat_id(chat_id, str(pending_steps), text)
        finally:
            await clear_pending_steps(chat_id)
        if not created:
            await update.message.reply_text(
                "🤔 Couldn't parse steps. Try: `prepare slides, review notes`"
            )
        else:
            lines = [f"✅ Added {len(created)} step{'s' if len(created) != 1 else ''}:\n"]
            for s in created:
                lines.append(f"• {s}")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # Priority 2: waiting for edit input
    pending_edit = await get_pending_edit_task_id(chat_id)
    if pending_edit is not None:
        from app.telegram.db_helpers import apply_task_edit, clear_pending_edit
        from app.services.ai_editor import parse_edit_instruction
        try:
            edit = await parse_edit_instruction(text)
            if edit is None:
                await update.message.reply_text(
                    "🤔 Couldn't understand that edit.\n"
                    "Try: _'deadline is Friday'_, _'rename to X'_, or _'delete'_",
                    parse_mode="Markdown",
                )
                return
            ok = await apply_task_edit(chat_id, str(pending_edit), edit)
            if ok:
                if edit["field"] == "delete":
                    msg = "🗑️ Task deleted."
                elif edit["field"] == "deadline":
                    msg = f"✅ Deadline updated to *{edit['value']}*."
                else:
                    msg = f"✅ Renamed to *{edit['value']}*."
                await update.message.reply_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Couldn't apply that edit. The task may have been deleted.")
        finally:
            await clear_pending_edit(chat_id)
        return

    # Priority 3: brain dump (default for all free text)
    await update.message.reply_text("⏳ On it...")
    from app.telegram.db_helpers import process_dump_for_chat_id
    tasks = await process_dump_for_chat_id(chat_id, text)
    if not tasks:
        await update.message.reply_text(
            "🤔 Couldn't find any tasks in that.\n"
            "Try: _'essay due Friday, lab report Monday'_\n\n"
            "Use /menu to see all options.",
            parse_mode="Markdown",
        )
    else:
        lines = [f"✅ Added {len(tasks)} task{'s' if len(tasks) > 1 else ''}:\n"]
        for t in tasks:
            lines.append(f"• {t.title}")
        lines.append("\nUse /today to see your priority.")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
```

**Step 3: Commit**

```bash
git add backend/app/telegram/handlers/callbacks.py backend/app/telegram/handlers/message.py
git commit -m "feat: edit_select callback + simplify message handler to 3-mode pipeline"
```

---

## Task 7: Register commands in bot.py + setMyCommands at startup

**Files:**
- Modify: `backend/app/telegram/bot.py`
- Modify: `backend/app/main.py`

**Step 1: Update bot.py**

Replace `create_application()` with:

```python
def create_application() -> Application:
    from app.telegram.handlers.commands import (
        menu_command, today_command, list_command, dump_command,
        done_command, skip_command, edit_command, web_command,
    )
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
```

**Step 2: Register commands with Telegram in main.py lifespan**

In `main.py`, after `await tg_app.initialize()` add:

```python
    # Register commands in Telegram's autocomplete menu
    from telegram import BotCommand
    await tg_app.bot.set_my_commands([
        BotCommand("menu",  "Show main menu"),
        BotCommand("today", "Today's priority task"),
        BotCommand("list",  "All pending tasks"),
        BotCommand("dump",  "Add new tasks (brain dump)"),
        BotCommand("done",  "Mark top task complete"),
        BotCommand("skip",  "Skip top task"),
        BotCommand("edit",  "Edit or delete a task"),
        BotCommand("web",   "Open NextMove in browser"),
    ])
```

**Step 3: Commit**

```bash
git add backend/app/telegram/bot.py backend/app/main.py
git commit -m "feat: register 8 commands in bot + setMyCommands at startup"
```

---

## Task 8: Update start.py to reference /menu

**Files:**
- Modify: `backend/app/telegram/handlers/start.py`

**Step 1: Update start_command welcome text**

Replace the unlinked-user reply in `start_command` to mention `/menu`:

```python
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.database import SessionLocal
    from app.models import User
    from app.telegram.handlers.commands import menu_command
    chat_id = update.effective_chat.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()

    if user:
        await menu_command(update, context)
        return

    await update.message.reply_text(
        "👋 Welcome to *NextMove*!\n\n"
        "To link your account, reply with the email you registered with on the web app.\n\n"
        "_Already linked? Use /menu to get started._",
        parse_mode="Markdown",
    )
```

**Step 2: Commit**

```bash
git add backend/app/telegram/handlers/start.py
git commit -m "refactor: start_command delegates to menu_command for known users"
```

---

## Task 9: Smoke test the full flow

**Step 1: Restart the backend**

```bash
cd backend && source venv/bin/activate
set -a && source ../.env && set +a
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Check startup logs — should see `Application startup complete.` with no errors.

**Step 2: Verify commands appear in Telegram**

Open the bot in Telegram, type `/` — all 8 commands should appear in the autocomplete popup.

**Step 3: Test each flow**

- `/menu` → shows menu with web button
- `/list` → shows tasks with Done/Skip buttons per task
- `/dump` → prompt, then type tasks → confirms count
- `/done` → marks top task done
- `/skip` → skips top task
- `/edit` → shows task list → tap one → type "deadline is next Monday" → confirms update
- `/web` → shows Open NextMove button
- Free text → treated as brain dump

**Step 4: Commit any fixups found during smoke test**
