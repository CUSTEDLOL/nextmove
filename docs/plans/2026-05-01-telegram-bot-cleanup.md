# Telegram Bot Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 3 runtime crashes and eliminate all duplicate/inconsistent code in the Telegram bot layer.

**Architecture:** Fixes are grouped by impact: crash bugs first, then shared utility extraction, then dead code removal and cleanup. Each task is independent once utilities exist.

**Tech Stack:** Python 3.12, python-telegram-bot v20+, SQLAlchemy, OpenAI async client

---

## Task 1: Fix crash — `edit` callback uses `update.message` (None in callback context)

**Files:**
- Modify: `backend/app/telegram/handlers/callbacks.py:221-223`

The `data == "edit"` branch calls `edit_command(update, context)`. That function calls
`update.message.reply_text(...)` but in a callback query context `update.message` is `None`.
The fix is to inline the edit-task list directly in the callback using `query.message`.

**Step 1: Replace the `edit` callback branch**

Find this in `callbacks.py` (lines 221–223):
```python
    elif data == "edit":
        from app.telegram.handlers.commands import edit_command
        await edit_command(update, context)
```

Replace with:
```python
    elif data == "edit":
        from app.telegram.db_helpers import list_tasks_for_chat_id
        tasks = await list_tasks_for_chat_id(chat_id)
        if tasks is None:
            await query.message.reply_text("You're not linked yet.")
            return
        if not tasks:
            await query.message.reply_text("📭 No tasks to edit.")
            return
        buttons = [
            [InlineKeyboardButton(
                t.title[:40] + ("…" if len(t.title) > 40 else ""),
                callback_data=f"edit_select:{t.id}"
            )]
            for t in tasks
        ]
        await query.message.reply_text(
            "✏️ Which task do you want to edit?",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
```

**Step 2: Verify manually**

The `edit_command` in `commands.py` remains unchanged and still handles the `/edit` slash command.
The `"edit"` callback now uses `query.message` which is always non-None in a callback context.

**Step 3: Commit**
```bash
git add backend/app/telegram/handlers/callbacks.py
git commit -m "fix: resolve AttributeError crash when edit menu button is tapped from callback"
```

---

## Task 2: Fix bug — `set_pending_steps` called on both branches in steps callback

**Files:**
- Modify: `backend/app/telegram/handlers/callbacks.py:155-162`

When a task already has steps (the `else` branch, line 143+), `set_pending_steps` is called at
line 157. This causes the user's next text message to be consumed as new-step input even though
they only viewed existing steps. The flag should only be set in the "no steps" branch.

**Step 1: Remove `set_pending_steps` from the `else` (has-steps) branch**

Find the `else` block starting at line 143 in the `steps:` handler:
```python
        else:
            done_count = sum(1 for s in steps if s["status"] == "completed")
            lines = [f"📋 *{_esc(parent.title)}* — {done_count}/{len(steps)} done\n"]
            buttons = []
            for s in steps:
                check = "✅" if s["status"] == "completed" else "⬜"
                lines.append(f"{check} {_esc(s['title'])}")
                if s["status"] != "completed":
                    buttons.append([
                        InlineKeyboardButton(
                            f"✅ {s['title'][:35]}",
                            callback_data=f"step_done:{s['id']}"
                        )
                    ])
            await set_pending_steps(chat_id, task_id)   # ← REMOVE THIS LINE
            await query.message.reply_text(
```

Remove only the `await set_pending_steps(chat_id, task_id)` line from the `else` branch.
The call in the `if not steps:` branch (line 141) stays.

**Step 2: Commit**
```bash
git add backend/app/telegram/handlers/callbacks.py
git commit -m "fix: don't set pending_steps flag when user is only viewing existing steps"
```

---

## Task 3: Create shared utility module `telegram/utils.py`

**Files:**
- Create: `backend/app/telegram/utils.py`

Consolidates `_esc()` which is currently defined identically in `message.py:21`,
`callbacks.py:7`, and `today.py:8`.

**Step 1: Create the file**
```python
from telegram.helpers import escape_markdown


def esc(text: str) -> str:
    """Escape text for MarkdownV2 Telegram messages."""
    return escape_markdown(str(text), version=2)
```

Note: function is named `esc` (no leading underscore) since it will be imported by name.

**Step 2: Update `today.py`**

Remove:
```python
from telegram.helpers import escape_markdown

def _esc(text: str) -> str:
    return escape_markdown(text, version=2)
```

Add at top of imports:
```python
from app.telegram.utils import esc as _esc
```

**Step 3: Update `message.py`**

Remove:
```python
from telegram.helpers import escape_markdown

def _esc(text: str) -> str:
    return escape_markdown(text, version=2)
```

Add:
```python
from app.telegram.utils import esc as _esc
```

**Step 4: Update `callbacks.py`**

Remove:
```python
from telegram.helpers import escape_markdown

def _esc(text: str) -> str:
    return escape_markdown(text, version=2)
```

Add:
```python
from app.telegram.utils import esc as _esc
```

**Step 5: Update `notifier.py`**

Remove:
```python
from telegram.helpers import escape_markdown

def _esc(text: str) -> str:
    return escape_markdown(text, version=2)
```

Add:
```python
from app.telegram.utils import esc as _esc
```

**Step 6: Run tests**
```bash
cd backend && pytest -v
```
Expected: all passing (no logic change, pure refactor).

**Step 7: Commit**
```bash
git add backend/app/telegram/utils.py \
        backend/app/telegram/handlers/today.py \
        backend/app/telegram/handlers/message.py \
        backend/app/telegram/handlers/callbacks.py \
        backend/app/services/notifier.py
git commit -m "refactor: extract shared _esc() helper to telegram/utils.py"
```

---

## Task 4: Create shared `services/time_utils.py` — deduplicate `_user_day_bounds_utc`

**Files:**
- Create: `backend/app/services/time_utils.py`
- Modify: `backend/app/services/pinger.py`
- Modify: `backend/app/workers/notification_jobs.py`

`_user_day_bounds_utc` and `_user_tz` are duplicated in `pinger.py:21-36` and
`notification_jobs.py:24-39`. The comment in `notification_jobs.py` even says "Mirrors pinger.py".

**Step 1: Create `time_utils.py`**
```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.user import User


def user_tz(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def user_day_bounds_utc(user: User, now: datetime) -> tuple[datetime, datetime]:
    """Return (today_start, tomorrow_start) as naive UTC for the user's local timezone."""
    tz = user_tz(user)
    utc = ZoneInfo("UTC")
    local_now = now.replace(tzinfo=utc).astimezone(tz)
    local_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc = local_today.astimezone(utc).replace(tzinfo=None)
    tomorrow_utc = (local_today + timedelta(days=1)).astimezone(utc).replace(tzinfo=None)
    return today_utc, tomorrow_utc
```

**Step 2: Update `pinger.py`**

Remove the local `_user_tz` and `_user_day_bounds_utc` functions (lines 21–36).

Add import at top:
```python
from app.services.time_utils import user_tz as _user_tz, user_day_bounds_utc as _user_day_bounds_utc
```

The rest of `pinger.py` uses `_user_tz(user)` and `_user_day_bounds_utc(user, now)` — same
call signatures, no other changes needed.

**Step 3: Update `notification_jobs.py`**

Remove the local `_user_day_bounds_utc` function (lines 24–39, including the docstring).

Add import at top:
```python
from app.services.time_utils import user_day_bounds_utc as _user_day_bounds_utc
```

**Step 4: Run tests**
```bash
cd backend && pytest -v
```

**Step 5: Commit**
```bash
git add backend/app/services/time_utils.py \
        backend/app/services/pinger.py \
        backend/app/workers/notification_jobs.py
git commit -m "refactor: extract user_day_bounds_utc to services/time_utils.py, remove duplication"
```

---

## Task 5: Deduplicate `ACTIVE_TASK_STATUSES` — import from single source

**Files:**
- Modify: `backend/app/services/pinger.py`

`ACTIVE_TASK_STATUSES = ["pending", "scheduled", "in_progress"]` is defined in both
`task_service.py:22` and `pinger.py:13`. `task_service.py` is the canonical location.

**Step 1: Update `pinger.py`**

Remove line 13:
```python
ACTIVE_TASK_STATUSES = ["pending", "scheduled", "in_progress"]
```

Add to imports:
```python
from app.services.task_service import ACTIVE_TASK_STATUSES
```

**Step 2: Commit**
```bash
git add backend/app/services/pinger.py
git commit -m "refactor: import ACTIVE_TASK_STATUSES from task_service instead of redefining"
```

---

## Task 6: Create shared OpenAI client singleton

**Files:**
- Create: `backend/app/services/openai_client.py`
- Modify: `backend/app/telegram/intent.py`
- Modify: `backend/app/services/ai_parser.py`

Three files each define their own lazy `AsyncOpenAI` singleton: `intent.py`, `ai_editor.py`,
`ai_parser.py`. `voice.py` even imports `_get_openai_client` from `intent` directly to piggyback.
Consolidate into one module. (`ai_editor.py` can be updated if it exists.)

**Step 1: Create `openai_client.py`**
```python
from openai import AsyncOpenAI
from app.config import settings

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client
```

**Step 2: Update `intent.py`**

Remove:
```python
from openai import AsyncOpenAI
from app.config import settings

_openai_client: AsyncOpenAI | None = None

def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client
```

Add import:
```python
from app.services.openai_client import get_openai_client as _get_openai_client
```

In `_gpt_classify`, the call `client = _get_openai_client()` continues to work unchanged.

**Step 3: Update `ai_parser.py`**

Locate the local `_openai_client` singleton and `_get_client()` function. Remove them.
Add:
```python
from app.services.openai_client import get_openai_client as _get_client
```

Replace internal calls to `_get_client()` — signature is the same, no other changes.

**Step 4: Update `ai_editor.py` (if it exists)**

Same pattern: remove local singleton, import `get_openai_client`.

**Step 5: Update `voice.py`**

Change:
```python
from app.telegram.intent import _get_openai_client
```
to:
```python
from app.services.openai_client import get_openai_client as _get_openai_client
```

**Step 6: Run tests**
```bash
cd backend && pytest -v
```

**Step 7: Commit**
```bash
git add backend/app/services/openai_client.py \
        backend/app/telegram/intent.py \
        backend/app/services/ai_parser.py \
        backend/app/telegram/handlers/voice.py
git commit -m "refactor: consolidate AsyncOpenAI singleton into services/openai_client.py"
```

---

## Task 7: Standardize all Telegram messages to MarkdownV2

**Files:**
- Modify: `backend/app/telegram/handlers/commands.py`
- Modify: `backend/app/telegram/handlers/voice.py`
- Modify: `backend/app/services/pinger.py`
- Modify: `backend/app/workers/notification_jobs.py`

`message.py`, `callbacks.py`, `today.py`, and `notifier.py` already use MarkdownV2.
`commands.py`, `voice.py`, `pinger.py`, and `notification_jobs.py` use old `parse_mode="Markdown"`.
Task titles with `.`, `!`, `-`, `(`, `)` corrupt or crash in v2 handlers.

**Step 1: Update `commands.py`**

Add import at top:
```python
from app.telegram.utils import esc as _esc
```

Update `menu_command` — change the reply:
```python
    await update.message.reply_text(
        f"👋 Hey *{_esc(display_name)}*\\! What do you want to do?",
        parse_mode="MarkdownV2",
        reply_markup=markup,
    )
```

Update `list_command` — escape task titles and deadline strings, change `parse_mode`:
```python
    lines = [f"📋 *Your tasks* \\({len(tasks)} total\\):\n"]
    for i, t in enumerate(tasks, 1):
        deadline_str = f" — due {_esc(t.deadline.strftime('%b %d'))}" if t.deadline else ""
        status_icon = "▶️ " if t.status == "in_progress" else ""
        lines.append(f"{i}\\. {status_icon}{_esc(t.title)}{deadline_str}")
    lines.append("\nTap a task to manage it, or use /today to see your \\#1 priority\\.")

    await target.reply_text(
        "\n".join(lines),
        parse_mode="MarkdownV2",
        ...
    )
```

Update `dump_command`:
```python
    await update.message.reply_text(
        "🧠 Go ahead — tell me everything on your plate:\n"
        "_assignments, deadlines, meetings, anything_",
        parse_mode="MarkdownV2",
    )
```

Update `done_command`:
```python
        await update.message.reply_text(
            f"✅ Marked *{_esc(task.title)}* as done\\. Nice work\\!",
            parse_mode="MarkdownV2",
        )
    else:
        await update.message.reply_text("🎉 No pending tasks — you're all clear\\!")
```

Update `skip_command`:
```python
        await update.message.reply_text(
            f"⏭️ Pushed *{_esc(task.title)}* aside\\.",
            parse_mode="MarkdownV2",
        )
    else:
        await update.message.reply_text("Nothing to skip right now\\.")
```

Update `edit_command` — no user content in the prompt, but add `parse_mode="MarkdownV2"` to be consistent:
```python
    await update.message.reply_text(
        "✏️ Which task do you want to edit?",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
```

Update `web_command`:
```python
    await update.message.reply_text(
        "Open NextMove in your browser:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Open NextMove", url=settings.web_url)
        ]]),
    )
```
(No parse_mode needed — plain text, no markdown.)

Update `menu_command` — the unlinked user reply (line 21):
```python
        await update.message.reply_text(
            "You're not linked yet\\. Send your registered email to connect\\.",
            parse_mode="MarkdownV2",
        )
```

**Step 2: Update `voice.py`**

Add import at top:
```python
from app.telegram.utils import esc as _esc
```

Change `parse_mode="Markdown"` to `parse_mode="MarkdownV2"` in every `reply_text` call,
and escape all dynamic content (task.title, deadline, text):

Line 37 (transcript echo):
```python
    await update.message.reply_text(f"📝 Heard: _{_esc(text)}_", parse_mode="MarkdownV2")
```

`add_task` branch (~line 67):
```python
            deadline_str = f" — due {_esc(task.deadline.strftime('%a %b %d'))}" if task.deadline else ""
            await update.message.reply_text(
                f"✅ Added: *{_esc(task.title)}*{deadline_str}\n\nUse /today to see your priority\\.",
                parse_mode="MarkdownV2",
            )
        else:
            await update.message.reply_text(
                "🤔 Couldn't parse that\\. Try: _'add essay due Friday'_",
                parse_mode="MarkdownV2",
            )
```

Dump result block (~line 84):
```python
    await update.message.reply_text("⏳ Parsing tasks\\.\\.\\.", parse_mode="MarkdownV2")
    ...
    if not tasks:
        await update.message.reply_text("🤔 No tasks found in that\\. Try being more specific\\.", parse_mode="MarkdownV2")
        return

    lines = [f"✅ Got {len(tasks)} task{'s' if len(tasks) != 1 else ''}:\n"]
    for t in tasks:
        lines.append(f"• {_esc(t.title)}")
    lines.append("\nSend /today to see your priority task\\.")
    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")
```

Other static messages (error, unlinked warning): append `\\` to sentence-ending `!` and `.` as needed, add `parse_mode="MarkdownV2"`.

**Step 3: Update `notification_jobs.py` — fix `_send_telegram_message`**

The `notifier.py` builders already produce MarkdownV2-escaped content (they use `_esc`).
But `_send_telegram_message` sends with `parse_mode="Markdown"`. Fix:
```python
async def _send_telegram_message(chat_id: int, text: str) -> None:
    if _bot is None:
        logger.warning("Notification bot not set — skipping message to %s", chat_id)
        return
    try:
        await _bot.send_message(chat_id=chat_id, text=text, parse_mode="MarkdownV2")
    except Exception as e:
        logger.error("Failed to send Telegram message to %s: %s", chat_id, e)
```

**Step 4: Update `pinger.py` — escape task title, switch to MarkdownV2**

Add import at top:
```python
from app.telegram.utils import esc as _esc
```

Change the send_message call (~line 132):
```python
                await app.bot.send_message(
                    chat_id=user.telegram_chat_id,
                    text=(
                        f"👀 You missed your scheduled block for *{_esc(task.title)}*\\.\n\n"
                        f"It was supposed to wrap at {_esc(_format_block_end(block_end_time, user))}\\. "
                        f"Mark it done, add steps, or skip it\\."
                    ),
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
```

**Step 5: Run tests**
```bash
cd backend && pytest -v
```

**Step 6: Commit**
```bash
git add backend/app/telegram/handlers/commands.py \
        backend/app/telegram/handlers/voice.py \
        backend/app/services/pinger.py \
        backend/app/workers/notification_jobs.py
git commit -m "fix: standardize all Telegram messages to MarkdownV2, escape dynamic content"
```

---

## Task 8: Remove `commands.today_command` stub — wire bot.py directly

**Files:**
- Modify: `backend/app/telegram/bot.py`
- Modify: `backend/app/telegram/handlers/commands.py`

`commands.today_command` is a two-line stub that clears state then calls `today.today_command`.
`bot.py` registers the stub, but every other caller (callbacks, message, voice) imports
`today.today_command` directly — bypassing the state-clear. The stub adds no value.
The right fix: remove the stub and have `bot.py` register `today.today_command` directly, with
`_clear_conversation_state` absorbed into `today.today_command`.

**Step 1: Update `today.py` — add state clear at the start of `today_command`**
```python
async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import get_today_for_chat_id, clear_pending_state
    chat_id = update.effective_chat.id
    await clear_pending_state(chat_id)          # ← add this line
    result = await get_today_for_chat_id(chat_id)
    ...
```

**Step 2: Remove `today_command` from `commands.py`**

Delete the entire function (lines 41–44):
```python
async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _clear_conversation_state(update.effective_chat.id)
    from app.telegram.handlers.today import today_command as _today
    await _today(update, context)
```

**Step 3: Update `bot.py`**

Change the import in `create_application`:
```python
    from app.telegram.handlers.commands import (
        menu_command, list_command, dump_command,   # ← remove today_command here
        done_command, skip_command, edit_command, web_command,
    )
    from app.telegram.handlers.today import today_command   # ← add this import
```

The handler registration line stays the same:
```python
    application.add_handler(CommandHandler("today", today_command))
```

**Step 4: Run tests**
```bash
cd backend && pytest -v
```

**Step 5: Commit**
```bash
git add backend/app/telegram/bot.py \
        backend/app/telegram/handlers/commands.py \
        backend/app/telegram/handlers/today.py
git commit -m "refactor: remove commands.today_command stub, register today.today_command directly"
```

---

## Task 9: Move `callbacks.py` in-function imports to module level

**Files:**
- Modify: `backend/app/telegram/handlers/callbacks.py`

11 branches each do `from app.telegram.db_helpers import ...` inside the function body,
and `today_command` is imported 4 separate times. No circular import risk here — move all
db_helpers imports and today_command to module level.

**Step 1: Replace all in-function imports with module-level imports**

At the top of `callbacks.py`, after the existing imports, add:
```python
from app.telegram.handlers.today import today_command
from app.telegram.db_helpers import (
    complete_task_for_chat_id,
    delete_task_for_chat_id,
    get_task_for_chat_id,
    reschedule_task_for_chat_id,
    start_task_for_chat_id,
    get_steps_for_chat_id,
    set_pending_steps,
    complete_step_for_chat_id,
    why_task_for_chat_id,
    list_tasks_for_chat_id,
    set_pending_edit,
)
from app.telegram.handlers.commands import list_command
```

Then remove every `from app.telegram...` local import inside `handle_callback`.

**Step 2: Run tests**
```bash
cd backend && pytest -v
```

**Step 3: Commit**
```bash
git add backend/app/telegram/handlers/callbacks.py
git commit -m "refactor: move all in-function imports in callbacks.py to module level"
```

---

## Task 10: Move `commands.py` settings import to module level

**Files:**
- Modify: `backend/app/telegram/handlers/commands.py`

`settings` is imported inside two separate function bodies (`menu_command` line 25,
`web_command` line 140). It should be a module-level import.

**Step 1: Add module-level import**

At the top of `commands.py`, add:
```python
from app.config import settings
```

**Step 2: Remove the two in-function imports**

Remove `from app.config import settings` from inside `menu_command` and `web_command`.

**Step 3: Commit**
```bash
git add backend/app/telegram/handlers/commands.py
git commit -m "refactor: move settings import to module level in commands.py"
```

---

## Task 11: Standardize `user.name` fallback to single idiom

**Files:**
- Modify: `backend/app/telegram/handlers/message.py`
- Modify: `backend/app/telegram/handlers/commands.py`

Three different idioms exist:
- `message.py:227`: `getattr(user, "name", None) or "there"` — `getattr` is unnecessary
- `commands.py:26`: `user.name if user.name else "there"` — verbose
- `notification_jobs.py:68,152`: `user.name or "there"` — correct idiom

Standardize to `user.name or "there"` everywhere.

**Step 1: Fix `message.py:227`**

Change:
```python
name = getattr(user, "name", None) or "there"
```
To:
```python
name = user.name or "there"
```

**Step 2: Fix `commands.py:26`**

Change:
```python
display_name = user.name if user.name else "there"
```
To:
```python
display_name = user.name or "there"
```

**Step 3: Commit**
```bash
git add backend/app/telegram/handlers/message.py \
        backend/app/telegram/handlers/commands.py
git commit -m "refactor: standardize user.name fallback to user.name or 'there' everywhere"
```

---

## Task 12: Remove dead code from `notifier.py`

**Files:**
- Modify: `backend/app/services/notifier.py`
- Modify: `backend/tests/test_notifier.py` (if it tests removed functions)

`build_procrastination_prompt` (line 32) and `build_pretask_nudge` (line 40) are never called
in production code — only in tests. The pre-task nudge job doesn't exist; pinger sends its own
hardcoded message. Remove both builders and their tests.

**Step 1: Remove from `notifier.py`**

Delete lines 32–44 (both functions):
```python
def build_procrastination_prompt(task: TaskResponse) -> str:
    ...

def build_pretask_nudge(task: TaskResponse) -> str:
    ...
```

**Step 2: Remove corresponding tests from `test_notifier.py`**

Remove the imports of and test functions for `build_procrastination_prompt` and
`build_pretask_nudge`.

**Step 3: Run tests**
```bash
cd backend && pytest -v
```
Expected: all passing (tests for removed dead builders also removed).

**Step 4: Commit**
```bash
git add backend/app/services/notifier.py backend/tests/test_notifier.py
git commit -m "chore: remove dead build_procrastination_prompt and build_pretask_nudge builders"
```

---

## Task 13: Standardize `SessionLocal` usage to context manager in `pinger.py`

**Files:**
- Modify: `backend/app/services/pinger.py`

`pinger.py` uses the manual `db = SessionLocal() / try: ... finally: db.close()` pattern
while `notification_jobs.py` uses `with SessionLocal() as db:`. Standardize to context manager.

**Step 1: Update `ping_procrastinating_users` in `pinger.py`**

Change:
```python
    db = SessionLocal()
    try:
        ...
    finally:
        db.close()
```

To:
```python
    with SessionLocal() as db:
        ...
```

Remove the `finally: db.close()` block. All code inside the `try` moves into the `with` block
at the same indentation.

**Step 2: Run tests**
```bash
cd backend && pytest -v
```

**Step 3: Commit**
```bash
git add backend/app/services/pinger.py
git commit -m "refactor: use context manager for SessionLocal in pinger.py"
```

---

## Task 14: Extract shared intent dispatcher — eliminate voice.py duplication

**Files:**
- Create: `backend/app/telegram/handlers/dispatch.py`
- Modify: `backend/app/telegram/handlers/message.py`
- Modify: `backend/app/telegram/handlers/voice.py`

`voice.py` duplicates the entire intent-dispatch switch from `message.py`. Extract a shared
`dispatch_intent` coroutine.

**Step 1: Create `dispatch.py`**
```python
"""
Shared intent dispatcher used by both text (message.py) and voice (voice.py) handlers.
Handles: complete, skip, today, list, add_task, steps_reply, dump.
Returns True if the intent was handled, False if it fell through to dump.
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
    """
    Dispatch a classified intent. Returns True if handled (caller should return).
    Returns False to signal: fall through to brain-dump processing.
    """
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

    # intent == "dump" or unrecognized → caller should run brain-dump
    return False
```

**Step 2: Update `message.py` — replace the dispatch block**

Remove the block from `if intent == "add_task":` through the `unclear` handler (lines 113–155).

Replace with:
```python
    from app.telegram.handlers.dispatch import dispatch_intent
    handled = await dispatch_intent(intent, text, chat_id, update, context)
    if handled:
        return
```

The dump/default block that follows (lines 157–173) stays unchanged.

**Step 3: Update `voice.py` — replace the dispatch block**

Remove the if-chain from `if intent == "complete":` through `if intent == "steps_reply"...`
(lines 47–81). Note: `steps_reply` with pending steps calls `handle_message` — keep that special
case before calling `dispatch_intent`.

Replace with:
```python
    if intent == "steps_reply" and has_pending_steps:
        from app.telegram.handlers.message import handle_message
        await handle_message(update, context)
        return

    from app.telegram.handlers.dispatch import dispatch_intent
    handled = await dispatch_intent(intent, text, chat_id, update, context)
    if handled:
        return
```

The dump/default block at the bottom of `voice.py` stays.

**Step 4: Run tests**
```bash
cd backend && pytest -v
```

**Step 5: Commit**
```bash
git add backend/app/telegram/handlers/dispatch.py \
        backend/app/telegram/handlers/message.py \
        backend/app/telegram/handlers/voice.py
git commit -m "refactor: extract shared intent dispatcher, eliminate voice.py duplication"
```

---

## Summary of Changes

| Task | Type | Files Changed |
|------|------|---------------|
| 1. Fix edit callback crash | Bug fix | callbacks.py |
| 2. Fix set_pending_steps bug | Bug fix | callbacks.py |
| 3. Extract _esc to utils.py | Refactor | +utils.py, today/message/callbacks/notifier |
| 4. Extract time_utils.py | Refactor | +time_utils.py, pinger, notification_jobs |
| 5. Deduplicate ACTIVE_TASK_STATUSES | Refactor | pinger.py |
| 6. Shared OpenAI singleton | Refactor | +openai_client.py, intent/ai_parser/voice |
| 7. Standardize MarkdownV2 | Bug fix | commands/voice/pinger/notification_jobs |
| 8. Remove today_command stub | Refactor | bot/commands/today |
| 9. Callbacks imports to module level | Refactor | callbacks.py |
| 10. Settings import to module level | Refactor | commands.py |
| 11. Standardize user.name fallback | Refactor | message/commands |
| 12. Remove dead notifier builders | Cleanup | notifier/test_notifier |
| 13. SessionLocal context manager | Refactor | pinger.py |
| 14. Shared intent dispatcher | Refactor | +dispatch.py, message/voice |
