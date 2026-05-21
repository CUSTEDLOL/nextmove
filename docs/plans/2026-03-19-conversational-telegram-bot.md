
# Conversational Telegram Bot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the Telegram bot as a pure conversational interface — no commands, just natural text — that classifies intent, routes to the right action, and never leaves the user confused.

**Architecture:** A single `MessageHandler` replaces all `ConversationHandler`s. An intent classifier (keyword-first, GPT fallback) routes each message. Steps-waiting state moves from ephemeral `context.user_data` to a `pending_steps_task_id` column on the User DB row, surviving server restarts. The Telegram `Application` is initialized once in FastAPI's lifespan, not per request.

**Tech Stack:** python-telegram-bot v20+, FastAPI lifespan, SQLAlchemy, Alembic, OpenAI gpt-4o-mini (classifier), gpt-4o (parser, already in place)

---

## Task 1: Add `pending_steps_task_id` to User model + migration

**Files:**
- Modify: `backend/app/models/user.py`
- Create: `backend/alembic/versions/<hash>_add_pending_steps_task_id.py` (auto-generated)

**Step 1: Write the failing test**

In `backend/tests/test_user_model.py`, add:

```python
def test_user_has_pending_steps_task_id(db_session):
    from app.models import User
    user = db_session.query(User).first()
    # Should not raise AttributeError
    assert hasattr(user, "pending_steps_task_id")
    assert user.pending_steps_task_id is None
```

**Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_user_model.py::test_user_has_pending_steps_task_id -v
```
Expected: `FAILED — AttributeError: pending_steps_task_id`

**Step 3: Add column to User model**

In `backend/app/models/user.py`, add after `telegram_chat_id`:

```python
pending_steps_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
```

Also add the import if not present: `from sqlalchemy import Column, String, Boolean, Integer, BigInteger, DateTime, ForeignKey`

**Step 4: Generate and apply migration**

```bash
cd backend
alembic revision --autogenerate -m "add pending_steps_task_id to users"
alembic upgrade head
```

Verify the new file appears in `alembic/versions/`.

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_user_model.py::test_user_has_pending_steps_task_id -v
```
Expected: `PASSED`

**Step 6: Commit**

```bash
git add backend/app/models/user.py backend/alembic/versions/
git commit -m "feat: add pending_steps_task_id column to users for persistent bot state"
```

---

## Task 2: Build intent classifier

**Files:**
- Create: `backend/app/telegram/intent.py`
- Create: `backend/tests/test_intent.py`

**Step 1: Write failing tests**

Create `backend/tests/test_intent.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_classifies_today_keywords():
    from app.telegram.intent import classify_intent
    assert await classify_intent("what should I do today", has_pending_steps=False) == "today"
    assert await classify_intent("what's my priority", has_pending_steps=False) == "today"
    assert await classify_intent("show me my schedule", has_pending_steps=False) == "today"

@pytest.mark.asyncio
async def test_classifies_complete_keywords():
    from app.telegram.intent import classify_intent
    assert await classify_intent("I'm done", has_pending_steps=False) == "complete"
    assert await classify_intent("just submitted my report", has_pending_steps=False) == "complete"
    assert await classify_intent("finished the lab", has_pending_steps=False) == "complete"

@pytest.mark.asyncio
async def test_classifies_skip_keywords():
    from app.telegram.intent import classify_intent
    assert await classify_intent("skip this", has_pending_steps=False) == "skip"
    assert await classify_intent("not doing that today", has_pending_steps=False) == "skip"
    assert await classify_intent("postpone the meeting", has_pending_steps=False) == "skip"

@pytest.mark.asyncio
async def test_classifies_list_keywords():
    from app.telegram.intent import classify_intent
    assert await classify_intent("show all my tasks", has_pending_steps=False) == "list"
    assert await classify_intent("list everything", has_pending_steps=False) == "list"

@pytest.mark.asyncio
async def test_steps_reply_takes_priority():
    from app.telegram.intent import classify_intent
    # Even "done" → steps_reply if waiting for steps
    assert await classify_intent("prepare slides, rehearse notes", has_pending_steps=True) == "steps_reply"

@pytest.mark.asyncio
async def test_gpt_fallback_dump(monkeypatch):
    from app.telegram import intent as intent_mod
    monkeypatch.setattr(intent_mod, "_gpt_classify", AsyncMock(return_value="dump"))
    from app.telegram.intent import classify_intent
    result = await classify_intent("I have a meeting Friday and an exam on Monday at 9am", has_pending_steps=False)
    assert result == "dump"

@pytest.mark.asyncio
async def test_gpt_fallback_unclear(monkeypatch):
    from app.telegram import intent as intent_mod
    monkeypatch.setattr(intent_mod, "_gpt_classify", AsyncMock(return_value="unclear"))
    from app.telegram.intent import classify_intent
    result = await classify_intent("haha nice", has_pending_steps=False)
    assert result == "unclear"
```

**Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_intent.py -v
```
Expected: `ModuleNotFoundError: app.telegram.intent`

**Step 3: Implement `intent.py`**

Create `backend/app/telegram/intent.py`:

```python
from openai import AsyncOpenAI
from app.config import settings

_TODAY = ["today", "what should i", "my priority", "what's next", "what do i do", "schedule", "show me today", "what's on"]
_COMPLETE = ["done", "finished", "completed", "submitted", "wrapped up", "handed in", "sent it", "just did"]
_SKIP = ["skip", "push", "reschedule", "postpone", "not today", "not doing", "later", "delay"]
_LIST = ["list", "all tasks", "show tasks", "show me everything", "everything i have", "all my tasks"]


async def classify_intent(text: str, has_pending_steps: bool) -> str:
    if has_pending_steps:
        return "steps_reply"

    lower = text.lower()

    if any(p in lower for p in _TODAY):
        return "today"
    if any(p in lower for p in _COMPLETE):
        return "complete"
    if any(p in lower for p in _SKIP):
        return "skip"
    if any(p in lower for p in _LIST):
        return "list"

    return await _gpt_classify(text)


async def _gpt_classify(text: str) -> str:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You classify student messages for a productivity bot. "
                    "Return exactly one word — either 'dump' or 'unclear'.\n"
                    "'dump' = message contains tasks, deadlines, events, assignments, or commitments to track.\n"
                    "'unclear' = chit-chat, greetings, questions about something else, or random text."
                )
            },
            {"role": "user", "content": text}
        ],
        max_tokens=5,
        temperature=0,
    )
    result = response.choices[0].message.content.strip().lower()
    return result if result in ("dump", "unclear") else "unclear"
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_intent.py -v
```
Expected: all 7 `PASSED` (GPT tests use mock so no real API call)

**Step 5: Commit**

```bash
git add backend/app/telegram/intent.py backend/tests/test_intent.py
git commit -m "feat: add hybrid intent classifier for conversational bot"
```

---

## Task 3: Fix `db_helpers.py` — lazy load bug + new helpers

**Files:**
- Modify: `backend/app/telegram/db_helpers.py`

**Context:** `get_steps_for_chat_id` returns raw SQLAlchemy `Task` objects after the session is closed. Accessing `.status` on them in `callbacks.py` triggers a lazy-load error. Fix: convert steps to dicts before closing. Also add: `set_pending_steps`, `clear_pending_steps`, `get_pending_steps_task_id`, `list_tasks_for_chat_id`, `complete_top_task_for_chat_id`, `skip_top_task_for_chat_id`.

**Step 1: Write failing tests**

Add to `backend/tests/test_db_helpers.py`:

```python
@pytest.mark.asyncio
async def test_get_steps_returns_serializable(linked_user, db_session):
    """Steps must be accessible after DB session closes."""
    from app.telegram.db_helpers import get_steps_for_chat_id
    result = await get_steps_for_chat_id(linked_user.telegram_chat_id, str(linked_user.tasks[0].id))
    if result:
        parent, steps = result
        # Must not raise DetachedInstanceError
        for s in steps:
            _ = s["status"]  # dict access, not ORM lazy load

@pytest.mark.asyncio
async def test_set_and_clear_pending_steps(linked_user):
    from app.telegram.db_helpers import set_pending_steps, clear_pending_steps, get_pending_steps_task_id
    task_id = "some-task-uuid"
    await set_pending_steps(linked_user.telegram_chat_id, task_id)
    result = await get_pending_steps_task_id(linked_user.telegram_chat_id)
    assert str(result) == task_id
    await clear_pending_steps(linked_user.telegram_chat_id)
    assert await get_pending_steps_task_id(linked_user.telegram_chat_id) is None

@pytest.mark.asyncio
async def test_list_tasks_for_chat_id(linked_user):
    from app.telegram.db_helpers import list_tasks_for_chat_id
    tasks = await list_tasks_for_chat_id(linked_user.telegram_chat_id)
    assert isinstance(tasks, list)
```

**Step 2: Run to verify they fail**

```bash
pytest tests/test_db_helpers.py -v
```

**Step 3: Rewrite `db_helpers.py`**

Replace the entire file with:

```python
"""
Bridges Telegram chat_id → database user_id.
All bot handlers call these instead of touching the DB directly.
"""
from typing import Optional
from app.database import SessionLocal
from app.models import User, Task
from app.schemas.tasks import TaskResponse
from app.services.ai_parser import parse_brain_dump
from app.services.matrix_scorer import score_task, TaskInput
from datetime import datetime
import uuid


def _get_user(db, chat_id: int) -> Optional[User]:
    return db.query(User).filter(User.telegram_chat_id == chat_id).first()


async def get_today_for_chat_id(chat_id: int) -> Optional[tuple]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        tasks = (
            db.query(Task)
            .filter(
                Task.user_id == user.id,
                Task.status.in_(["pending", "scheduled", "in_progress"]),
                Task.parent_task_id == None,
            )
            .order_by(Task.priority_index.desc())
            .limit(4)
            .all()
        )
        primary = TaskResponse.model_validate(tasks[0]) if tasks else None
        secondary = [TaskResponse.model_validate(t) for t in tasks[1:4]]
        return primary, secondary
    finally:
        db.close()


async def list_tasks_for_chat_id(chat_id: int) -> Optional[list]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        tasks = (
            db.query(Task)
            .filter(
                Task.user_id == user.id,
                Task.status.in_(["pending", "scheduled", "in_progress"]),
                Task.parent_task_id == None,
            )
            .order_by(Task.priority_index.desc())
            .limit(10)
            .all()
        )
        return [TaskResponse.model_validate(t) for t in tasks]
    finally:
        db.close()


async def process_dump_for_chat_id(chat_id: int, text: str) -> Optional[list]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        parsed = await parse_brain_dump(text, user_timezone=user.timezone)
        created = []
        for p in parsed:
            deadline = datetime.fromisoformat(p.deadline) if p.deadline else None
            task = Task(
                user_id=user.id,
                title=p.title,
                raw_input=text,
                deadline=deadline,
                effort=p.effort,
                importance=p.importance,
                context=p.context,
                status="pending",
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            task.priority_index = score_task(TaskInput(
                deadline=task.deadline,
                effort=task.effort or "medium",
                importance=task.importance or 3,
                dependency_count=0,
            ))
            db.commit()
            db.refresh(task)
            for step_title in p.steps:
                step = Task(
                    user_id=user.id,
                    title=step_title,
                    parent_task_id=task.id,
                    deadline=deadline,
                    effort=p.effort,
                    importance=p.importance,
                    context=p.context,
                    status="pending",
                )
                db.add(step)
            if p.steps:
                db.commit()
            created.append(TaskResponse.model_validate(task))
        return created
    finally:
        db.close()


async def get_steps_for_chat_id(chat_id: int, task_id: str) -> Optional[tuple]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
        if not task:
            return None
        steps = db.query(Task).filter(Task.parent_task_id == task.id).order_by(Task.created_at).all()
        # Convert to dicts before session closes to avoid DetachedInstanceError
        parent_data = TaskResponse.model_validate(task)
        steps_data = [{"title": s.title, "status": s.status, "id": str(s.id)} for s in steps]
        return parent_data, steps_data
    finally:
        db.close()


async def add_steps_for_chat_id(chat_id: int, task_id: str, text: str) -> Optional[list]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        parent = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
        if not parent:
            return None
        raw = text.replace("\n", ",")
        titles = [s.strip().lstrip("-•*").strip() for s in raw.split(",")]
        titles = [t for t in titles if len(t) > 1]
        created = []
        for title in titles:
            step = Task(
                user_id=user.id,
                title=title,
                parent_task_id=parent.id,
                effort=parent.effort,
                importance=parent.importance,
                deadline=parent.deadline,
                context=parent.context,
                status="pending",
            )
            db.add(step)
            db.commit()
            db.refresh(step)
            created.append(step.title)
        return created
    finally:
        db.close()


async def set_pending_steps(chat_id: int, task_id: str) -> None:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if user:
            user.pending_steps_task_id = uuid.UUID(task_id)
            db.commit()
    finally:
        db.close()


async def clear_pending_steps(chat_id: int) -> None:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if user:
            user.pending_steps_task_id = None
            db.commit()
    finally:
        db.close()


async def get_pending_steps_task_id(chat_id: int) -> Optional[uuid.UUID]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        return user.pending_steps_task_id if user else None
    finally:
        db.close()


async def why_task_for_chat_id(chat_id: int, task_id: str) -> Optional[str]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
        if not task:
            return None
        from app.routers.tasks import _generate_why
        return _generate_why(task)
    finally:
        db.close()


async def complete_task_for_chat_id(chat_id: int, task_id: str) -> bool:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return False
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
        if not task:
            return False
        task.status = "completed"
        db.commit()
        return True
    finally:
        db.close()


async def complete_top_task_for_chat_id(chat_id: int) -> Optional[TaskResponse]:
    """Mark the highest-priority pending task complete. Returns the task or None."""
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        task = (
            db.query(Task)
            .filter(
                Task.user_id == user.id,
                Task.status.in_(["pending", "scheduled", "in_progress"]),
                Task.parent_task_id == None,
            )
            .order_by(Task.priority_index.desc())
            .first()
        )
        if not task:
            return None
        task.status = "completed"
        db.commit()
        db.refresh(task)
        return TaskResponse.model_validate(task)
    finally:
        db.close()


async def reschedule_task_for_chat_id(chat_id: int, task_id: str) -> bool:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return False
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
        if not task:
            return False
        task.status = "rescheduled"
        db.commit()
        return True
    finally:
        db.close()


async def skip_top_task_for_chat_id(chat_id: int) -> Optional[TaskResponse]:
    """Reschedule the highest-priority pending task. Returns the task or None."""
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        task = (
            db.query(Task)
            .filter(
                Task.user_id == user.id,
                Task.status.in_(["pending", "scheduled", "in_progress"]),
                Task.parent_task_id == None,
            )
            .order_by(Task.priority_index.desc())
            .first()
        )
        if not task:
            return None
        task.status = "rescheduled"
        db.commit()
        db.refresh(task)
        return TaskResponse.model_validate(task)
    finally:
        db.close()
```

**Step 4: Run tests**

```bash
pytest tests/test_db_helpers.py -v
```
Expected: PASSED

**Step 5: Commit**

```bash
git add backend/app/telegram/db_helpers.py backend/tests/test_db_helpers.py
git commit -m "fix: db_helpers — fix lazy load bug, add persistent steps state, new helpers"
```

---

## Task 4: Build the central message handler

**Files:**
- Create: `backend/app/telegram/handlers/message.py`

This is the heart of the conversational bot. Every text message routes through here.

**Step 1: Write failing tests**

Create `backend/tests/test_message_handler.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

def _make_update(text, chat_id=12345):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_message.reply_text = AsyncMock()
    update.message = update.effective_message
    update.message.text = text
    update.callback_query = None
    return update

def _make_context():
    ctx = MagicMock()
    return ctx

@pytest.mark.asyncio
async def test_unknown_user_prompted_for_email():
    from app.telegram.handlers.message import handle_message
    update = _make_update("hello", chat_id=99999)
    ctx = _make_context()
    with patch("app.telegram.db_helpers.get_pending_steps_task_id", AsyncMock(return_value=None)), \
         patch("app.telegram.db_helpers.get_today_for_chat_id", AsyncMock(return_value=None)):
        await handle_message(update, ctx)
    call_args = update.effective_message.reply_text.call_args[0][0]
    assert "email" in call_args.lower() or "link" in call_args.lower()

@pytest.mark.asyncio
async def test_today_intent_calls_today(monkeypatch):
    from app.telegram.handlers import message as msg_mod
    monkeypatch.setattr("app.telegram.intent.classify_intent", AsyncMock(return_value="today"))
    from app.telegram.handlers.message import handle_message
    update = _make_update("what should I do today", chat_id=12345)
    ctx = _make_context()
    today_mock = AsyncMock()
    with patch("app.telegram.db_helpers.get_pending_steps_task_id", AsyncMock(return_value=None)), \
         patch("app.telegram.handlers.today.today_command", today_mock):
        await handle_message(update, ctx)
    today_mock.assert_called_once()
```

**Step 2: Run to verify they fail**

```bash
pytest tests/test_message_handler.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Implement `message.py`**

Create `backend/app/telegram/handlers/message.py`:

```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

AWAITING_EMAIL = 10  # shared constant for onboarding state


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()

    # --- Onboarding: unknown user ---
    from app.database import SessionLocal
    from app.models import User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()

    if not user:
        # Check if this looks like an email (onboarding reply)
        if "@" in text and "." in text:
            await _handle_email_link(update, text, chat_id)
        else:
            await update.effective_message.reply_text(
                "👋 Hey! I'm *NextMove* — your personal study planner.\n\n"
                "To get started, reply with the email you used to register on the web app:",
                parse_mode="Markdown"
            )
        return

    # --- Classify intent ---
    from app.telegram.db_helpers import get_pending_steps_task_id
    from app.telegram.intent import classify_intent

    pending_task_id = await get_pending_steps_task_id(chat_id)
    intent = await classify_intent(text, has_pending_steps=pending_task_id is not None)

    if intent == "today":
        from app.telegram.handlers.today import today_command
        await today_command(update, context)

    elif intent == "dump":
        await update.effective_message.reply_text("⏳ On it...")
        from app.telegram.db_helpers import process_dump_for_chat_id
        tasks = await process_dump_for_chat_id(chat_id, text)
        if not tasks:
            await update.effective_message.reply_text(
                "🤔 Hmm, I couldn't pull any tasks from that. "
                "Try something like: *'I have an essay due Friday and a lab report Monday'*",
                parse_mode="Markdown"
            )
        else:
            lines = [f"✅ Got it — added {len(tasks)} task{'s' if len(tasks) > 1 else ''}:\n"]
            for t in tasks:
                lines.append(f"• {t.title}")
            lines.append("\nWhat's next? I can show you *today's priority* or just keep going.")
            await update.effective_message.reply_text(
                "\n".join(lines),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🎯 Show today's task", callback_data="today")
                ]])
            )

    elif intent == "complete":
        from app.telegram.db_helpers import complete_top_task_for_chat_id
        task = await complete_top_task_for_chat_id(chat_id)
        if task:
            await update.effective_message.reply_text(
                f"✅ Marked *{task.title}* as done. Nice work!\n\nSend me what's next on your plate, or ask what to focus on.",
                parse_mode="Markdown"
            )
        else:
            await update.effective_message.reply_text("🎉 No pending tasks — you're all clear!")

    elif intent == "skip":
        from app.telegram.db_helpers import skip_top_task_for_chat_id
        task = await skip_top_task_for_chat_id(chat_id)
        if task:
            await update.effective_message.reply_text(
                f"⏭️ Pushed *{task.title}* aside. It'll come back when the time is right.",
                parse_mode="Markdown"
            )
        else:
            await update.effective_message.reply_text("Nothing to skip right now.")

    elif intent == "list":
        from app.telegram.db_helpers import list_tasks_for_chat_id
        tasks = await list_tasks_for_chat_id(chat_id)
        if not tasks:
            await update.effective_message.reply_text(
                "📭 No tasks yet. Tell me what's on your plate and I'll track it."
            )
        else:
            lines = [f"📋 *Your tasks* ({len(tasks)} pending):\n"]
            for i, t in enumerate(tasks, 1):
                deadline_str = f" — due {t.deadline.strftime('%b %d')}" if t.deadline else ""
                lines.append(f"{i}. {t.title}{deadline_str}")
            await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")

    elif intent == "steps_reply":
        from app.telegram.db_helpers import add_steps_for_chat_id, clear_pending_steps
        created = await add_steps_for_chat_id(chat_id, str(pending_task_id), text)
        await clear_pending_steps(chat_id)
        if not created:
            await update.effective_message.reply_text("🤔 Couldn't parse steps from that. Try: `prepare slides, review notes`")
        else:
            lines = [f"✅ Added {len(created)} step{'s' if len(created) != 1 else ''}:\n"]
            for s in created:
                lines.append(f"• {s}")
            await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")

    else:  # unclear
        await update.effective_message.reply_text(
            "Tell me what's on your plate — assignments, meetings, deadlines — and I'll sort it out for you.",
        )


async def _handle_email_link(update, email: str, chat_id: int):
    from app.database import SessionLocal
    from app.models import User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.strip().lower()).first()
        if not user:
            await update.effective_message.reply_text(
                "⚠️ No account found with that email. Make sure you've registered at the web app first, then try again."
            )
            return
        user.telegram_chat_id = chat_id
        db.commit()
        await update.effective_message.reply_text(
            f"✅ Linked! Welcome, *{user.name}*.\n\n"
            "Just tell me what's on your plate and I'll take it from there.",
            parse_mode="Markdown"
        )
    finally:
        db.close()
```

**Step 4: Run tests**

```bash
pytest tests/test_message_handler.py -v
```
Expected: PASSED

**Step 5: Commit**

```bash
git add backend/app/telegram/handlers/message.py backend/tests/test_message_handler.py
git commit -m "feat: conversational message handler — routes by intent, no commands needed"
```

---

## Task 5: Fix callbacks — wire "all tasks", fix steps flow

**Files:**
- Modify: `backend/app/telegram/handlers/callbacks.py`

The `tasks` callback was never handled. Steps now use DB state instead of `context.user_data`. Update accordingly.

**Step 1: Rewrite `callbacks.py`**

```python
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
        # Persist steps state to DB (survives restarts)
        await set_pending_steps(chat_id, task_id)
        await query.message.reply_text(text, parse_mode="Markdown")

    elif data.startswith("why:"):
        task_id = data.split(":", 1)[1]
        from app.telegram.db_helpers import why_task_for_chat_id
        explanation = await why_task_for_chat_id(chat_id, task_id)
        await query.answer(explanation or "Couldn't find that task.", show_alert=True)
```

**Step 2: Commit**

```bash
git add backend/app/telegram/handlers/callbacks.py
git commit -m "fix: callbacks — wire all tasks button, fix steps to use DB state"
```

---

## Task 6: Rewrite `bot.py` and `telegram.py` — fix initialization

**Files:**
- Modify: `backend/app/telegram/bot.py`
- Modify: `backend/app/routers/telegram.py`
- Modify: `backend/app/main.py`

**Context:** `application.initialize()` is called on every webhook hit — this is the root cause of unreliable conversation state. Fix: initialize once in FastAPI's lifespan. Also remove all `ConversationHandler`s (no commands, pure text routing).

**Step 1: Rewrite `bot.py`**

```python
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, filters
from app.config import settings

_application: Application | None = None


def create_application() -> Application:
    from app.telegram.handlers.message import handle_message
    from app.telegram.handlers.callbacks import handle_callback
    from app.telegram.handlers.voice import handle_voice

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT, handle_message))
    return application


def get_application() -> Application:
    global _application
    if _application is None:
        _application = create_application()
    return _application
```

**Step 2: Rewrite `telegram.py` router**

```python
from fastapi import APIRouter, Request, Response
from telegram import Update

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(request: Request):
    from app.telegram.bot import get_application
    body = await request.json()
    application = get_application()
    update = Update.de_json(body, application.bot)
    await application.process_update(update)
    return Response(status_code=200)
```

**Step 3: Initialize bot in FastAPI lifespan**

In `backend/app/main.py`, update the lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Telegram bot once at startup
    from app.telegram.bot import get_application
    application = get_application()
    await application.initialize()

    from app.services.pinger import ping_procrastinating_users
    scheduler.add_job(ping_procrastinating_users, "interval", hours=1, id="pinger")
    scheduler.start()

    yield

    scheduler.shutdown()
    await application.shutdown()
```

**Step 4: Verify server starts cleanly**

```bash
cd backend && uvicorn app.main:app --reload --port 8000
```

Watch logs — should see:
```
INFO: Application startup complete.
```
with no errors. Check `GET /health` returns `{"status": "ok"}`.

**Step 5: Commit**

```bash
git add backend/app/telegram/bot.py backend/app/routers/telegram.py backend/app/main.py
git commit -m "fix: initialize Telegram app once at startup, remove ConversationHandlers"
```

---

## Task 7: Update `start.py` — simplify to just show main menu for known users

**Files:**
- Modify: `backend/app/telegram/handlers/start.py`

`/start` is now the only remaining command — used only for the initial menu on returning users (edge case). New users are onboarded through natural text. Simplify accordingly.

**Step 1: Rewrite `start.py`**

```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


def _main_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Today's task", callback_data="today")],
        [InlineKeyboardButton("🧠 Brain dump", callback_data="dump")],
        [InlineKeyboardButton("✅ All tasks", callback_data="tasks")],
    ])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.database import SessionLocal
    from app.models import User
    chat_id = update.effective_chat.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()

    if user:
        await update.message.reply_text(
            f"👋 Hey *{user.name}* — what's going on?",
            reply_markup=_main_menu_markup(),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "👋 Hey! I'm *NextMove*.\n\nReply with your registered email to link your account:",
            parse_mode="Markdown"
        )
```

**Step 2: Register `/start` in `bot.py`**

Add to `create_application()` in `bot.py`, before the text handler:

```python
from telegram.ext import CommandHandler
application.add_handler(CommandHandler("start", start_command))
```

(Handler order matters — CommandHandler must be added before the catch-all MessageHandler.)

**Step 3: Commit**

```bash
git add backend/app/telegram/handlers/start.py backend/app/telegram/bot.py
git commit -m "refactor: simplify start handler, register /start command in bot"
```

---

## Task 8: End-to-end smoke test via Telegram

**No code changes.** Verify everything works together.

**Step 1: Confirm ngrok is running and webhook is registered**

```bash
# Check ngrok is up
curl -s http://localhost:4040/api/tunnels | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])"

# Re-register webhook with current ngrok URL if needed
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<NGROK_URL>/api/telegram/webhook"

# Verify webhook is set
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

**Step 2: Test onboarding**

1. Open Telegram, find your bot
2. Send: `hello`
3. Expected: bot asks for email
4. Reply with your registered email
5. Expected: `✅ Linked! Welcome, <name>.`

**Step 3: Test brain dump**

Send: `I have an essay due this Friday and a meeting with Prof tomorrow at 2pm`

Expected: bot replies with parsed tasks listed, button to show today's task.

**Step 4: Test today intent**

Send: `what should I do today`

Expected: today's highest-priority task with Done / Skip / Steps / Why buttons.

**Step 5: Test complete intent**

Send: `just finished it`

Expected: bot marks top task complete and confirms.

**Step 6: Test steps flow**

Tap "📋 Steps" button → bot prompts for steps → reply with `read chapter 3, make notes, write outline` → bot confirms steps added.

Send another message (not steps) immediately after — bot should NOT treat it as steps (state cleared).

**Step 7: Test all tasks**

Tap "✅ All tasks" from main menu → numbered list appears.

**Step 8: Final commit**

```bash
git add .
git commit -m "test: telegram bot smoke test complete — all flows verified"
```

---

## Summary of bugs fixed

| Bug | Fix |
|---|---|
| `application.initialize()` on every request | Moved to lifespan startup (Task 6) |
| Steps state wiped on restart | Stored in DB `pending_steps_task_id` (Tasks 1, 3, 5) |
| Dump-via-button didn't capture reply | Removed ConversationHandlers entirely (Task 6) |
| `get_steps_for_chat_id` lazy load crash | Converted to dicts before session close (Task 3) |
| "All tasks" button silent | Wired in callbacks (Task 5) |
| `_get_user_by_chat_id` dead code | Replaced with `_get_user(db, chat_id)` inline (Task 3) |
