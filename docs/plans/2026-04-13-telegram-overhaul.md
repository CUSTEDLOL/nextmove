# Telegram Bot Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix every known Telegram bot issue, eliminate duplicated business logic between the bot and API, and add proactive notifications — making Telegram a first-class interface with full parity to the web app.

**Architecture:** Extract a shared `services/task_service.py` layer that both `routers/tasks.py` and `telegram/db_helpers.py` call. The Telegram bot never touches the DB directly for business logic — it always goes through the service layer. Notifications run via APScheduler embedded in the FastAPI lifespan.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, python-telegram-bot v20+, APScheduler 3.x, OpenAI (Whisper + GPT-4o-mini), pytest

---

## Problems → Solutions Summary

| Problem | Solution |
|---|---|
| `db_helpers.py` duplicates router logic | Extract `services/task_service.py`; both router + bot consume it |
| `_generate_why` duplicated in two files | Lives only in `task_service.py` |
| `_apply_task_scores` duplicated in two files | Lives only in `task_service.py` |
| Skip just sets `rescheduled` with no date | Skip = delete task; Reschedule = ask "when?" → update deadline |
| `why:` button uses popup (200 char limit) | Send as a reply_text message |
| `/list` sends one message per task | Single formatted message, "Manage" button per task |
| Post-done/skip shows nothing | Immediately send updated today view |
| `tasks` callback ≠ `/list` UX | Unify: both use the same render function |
| Voice goes straight to brain dump | Run intent classifier on transcribed text first |
| No step completion buttons | Add `step_done:{step_id}` callback |
| No `in_progress` state from Telegram | Add `[▶️ Start]` button on today view |
| No proactive notifications | APScheduler: morning brief, evening wrap-up, weekly summary |
| No "add single task" from natural language | Intent `add_task` → task_service.create_task |

---

## Task 1: Extract `services/task_service.py`

This is the foundation. Everything else in this plan depends on it.

**Files:**
- Create: `backend/app/services/task_service.py`
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/app/telegram/db_helpers.py`
- Test: `backend/tests/test_task_service.py`

**What goes in `task_service.py`:**
- `apply_task_scores(task, *, recompute_urgency, recompute_importance)` — moved from both files
- `serialize_task(task, db, *, scheduled_today_ids, include_steps)` — the richer version from router
- `generate_why(task) -> str` — moved from both files (they're identical)
- `get_today(db, user) -> TodayResponse`
- `list_tasks(db, user) -> list[TaskResponse]`
- `complete_task(db, user, task_id) -> TaskResponse | None`
- `delete_task(db, user, task_id) -> bool`
- `reschedule_task(db, user, task_id, new_deadline: datetime) -> TaskResponse | None`
- `update_task(db, user, task_id, updates: dict) -> TaskResponse | None`
- `create_task(db, user, title, deadline, effort, importance, context) -> TaskResponse`
- `process_brain_dump(db, user, text) -> list[TaskResponse]`
- `get_steps(db, user, task_id) -> tuple[TaskResponse, list[dict]] | None`
- `add_steps(db, user, task_id, text) -> list[str] | None`
- `complete_step(db, user, step_id) -> bool`

**Step 1: Write the failing test**

```python
# backend/tests/test_task_service.py
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from app.services import task_service
from app.models import Task, User


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = "user-1"
    user.timezone = "UTC"
    user.study_start_hour = 9
    user.study_end_hour = 22
    return user


@pytest.fixture
def mock_task():
    task = MagicMock(spec=Task)
    task.id = "task-1"
    task.title = "Write essay"
    task.deadline = datetime.utcnow() + timedelta(days=2)
    task.effort = "high"
    task.importance = 4
    task.urgency_score = None
    task.importance_score = None
    task.priority_index = None
    task.parent_task_id = None
    task.status = "pending"
    return task


def test_apply_task_scores_sets_priority_index(mock_task):
    task_service.apply_task_scores(mock_task, recompute_urgency=True, recompute_importance=True)
    assert mock_task.urgency_score is not None
    assert mock_task.importance_score is not None
    assert mock_task.priority_index is not None


def test_generate_why_overdue():
    task = MagicMock(spec=Task)
    task.title = "Lab report"
    task.deadline = datetime.utcnow() - timedelta(days=2)
    task.importance = 3
    task.effort = "medium"
    result = task_service.generate_why(task)
    assert "overdue" in result
    assert "Lab report" in result


def test_generate_why_due_today():
    task = MagicMock(spec=Task)
    task.title = "Exam prep"
    task.deadline = datetime.utcnow() + timedelta(hours=3)
    task.importance = 5
    task.effort = "high"
    result = task_service.generate_why(task)
    assert "due today" in result
    assert "critically important" in result
```

**Step 2: Run to confirm it fails**

```bash
cd backend && pytest tests/test_task_service.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.services.task_service'`

**Step 3: Create `backend/app/services/task_service.py`**

```python
"""
Shared business logic for tasks. Used by both routers/tasks.py and telegram/db_helpers.py.
Never import routers here — this layer has no HTTP concepts.
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.models import User, Task, ScheduleBlock
from app.schemas.tasks import TaskResponse, TodayResponse
from app.services.matrix_scorer import (
    normalized_importance_score,
    normalized_urgency_score,
    score_task_from_matrix,
)
from app.services.ai_parser import parse_brain_dump
from app.services.schedule_runner import run_schedule_for_user

ACTIVE_TASK_STATUSES = ["pending", "scheduled", "in_progress"]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def apply_task_scores(
    task: Task,
    *,
    recompute_urgency: bool = False,
    recompute_importance: bool = False,
) -> None:
    if recompute_urgency or task.urgency_score is None:
        task.urgency_score = normalized_urgency_score(task.deadline)
    if recompute_importance or task.importance_score is None:
        task.importance_score = normalized_importance_score(task.importance or 3)
    task.priority_index = score_task_from_matrix(
        task.urgency_score or 0,
        task.importance_score or 0,
        effort=task.effort or "medium",
    )


# ---------------------------------------------------------------------------
# Why explanation
# ---------------------------------------------------------------------------

def generate_why(task: Task) -> str:
    reasons = []
    if task.deadline:
        now = datetime.utcnow()
        days = (task.deadline - now).days
        if days < 0:
            reasons.append(f"it's already overdue by {abs(days)} day{'s' if abs(days) != 1 else ''}")
        elif days == 0:
            reasons.append("it's due today")
        elif days == 1:
            reasons.append("it's due tomorrow")
        elif days <= 3:
            reasons.append(f"it's due in {days} days")
        elif days <= 7:
            reasons.append(f"it's due this week ({task.deadline.strftime('%A')})")
        else:
            reasons.append(f"it's due {task.deadline.strftime('%b %d')}")
    else:
        reasons.append("it has no deadline but has been waiting")

    importance = task.importance or 3
    if importance >= 5:
        reasons.append("you marked it as critically important")
    elif importance >= 4:
        reasons.append("you rated it high importance")
    elif importance <= 2:
        reasons.append("it's lower importance but still needs doing")

    effort = task.effort or "medium"
    if effort == "high":
        reasons.append("it's a heavy task that needs focus — best tackled now while your energy is fresh")
    elif effort == "low":
        reasons.append("it's a quick win that'll clear your head")

    reasons_str = (
        ", and ".join(reasons) if len(reasons) <= 2
        else ", ".join(reasons[:-1]) + ", and " + reasons[-1]
    )
    return f"'{task.title}' is your top priority because {reasons_str}."


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _scheduled_today_ids(db: Session, user_id) -> set:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    return {
        task_id
        for (task_id,) in db.query(ScheduleBlock.task_id)
        .filter(
            ScheduleBlock.user_id == user_id,
            ScheduleBlock.start_time >= today_start,
            ScheduleBlock.start_time < tomorrow_start,
        )
        .all()
    }


def serialize_task(
    task: Task,
    db: Session,
    *,
    scheduled_today_ids: Optional[set] = None,
    include_steps: bool = True,
) -> TaskResponse:
    if scheduled_today_ids is None:
        scheduled_today_ids = _scheduled_today_ids(db, task.user_id)
    steps = []
    if include_steps:
        child_steps = (
            db.query(Task)
            .filter(Task.parent_task_id == task.id)
            .order_by(Task.created_at)
            .all()
        )
        steps = [
            serialize_task(s, db, scheduled_today_ids=scheduled_today_ids, include_steps=False)
            for s in child_steps
        ]
    return TaskResponse(
        id=task.id,
        title=task.title,
        deadline=task.deadline,
        effort=task.effort,
        importance=task.importance,
        context=task.context,
        notes=task.notes,
        urgency_score=task.urgency_score,
        importance_score=task.importance_score,
        priority_index=task.priority_index,
        status=task.status,
        created_at=task.created_at,
        scheduled_today=task.id in scheduled_today_ids,
        steps=steps,
    )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def get_today(db: Session, user: User) -> TodayResponse:
    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user.id,
            Task.parent_task_id.is_(None),
            Task.status.in_(ACTIVE_TASK_STATUSES),
        )
        .order_by(Task.priority_index.desc())
        .limit(4)
        .all()
    )
    scheduled_today_ids = _scheduled_today_ids(db, user.id)
    primary = serialize_task(tasks[0], db, scheduled_today_ids=scheduled_today_ids) if tasks else None
    secondary = [
        serialize_task(t, db, scheduled_today_ids=scheduled_today_ids)
        for t in tasks[1:4]
    ]
    return TodayResponse(primary=primary, secondary=secondary)


def list_tasks(db: Session, user: User) -> list[TaskResponse]:
    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user.id,
            Task.parent_task_id.is_(None),
        )
        .order_by(Task.priority_index.desc())
        .all()
    )
    scheduled_today_ids = _scheduled_today_ids(db, user.id)
    return [serialize_task(t, db, scheduled_today_ids=scheduled_today_ids) for t in tasks]


def get_steps(
    db: Session, user: User, task_id: str
) -> Optional[tuple[TaskResponse, list[dict]]]:
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        return None
    steps = db.query(Task).filter(Task.parent_task_id == task.id).order_by(Task.created_at).all()
    parent_data = serialize_task(task, db)
    steps_data = [{"id": str(s.id), "title": s.title, "status": s.status} for s in steps]
    return parent_data, steps_data


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def create_task(
    db: Session,
    user: User,
    *,
    title: str,
    deadline: Optional[datetime] = None,
    effort: str = "medium",
    importance: int = 3,
    context: Optional[str] = None,
    raw_input: Optional[str] = None,
) -> TaskResponse:
    task = Task(
        user_id=user.id,
        title=title,
        deadline=deadline,
        effort=effort,
        importance=importance,
        context=context,
        raw_input=raw_input,
        status="pending",
    )
    apply_task_scores(task, recompute_urgency=True, recompute_importance=True)
    db.add(task)
    db.commit()
    db.refresh(task)
    run_schedule_for_user(user, db)
    db.refresh(task)
    return serialize_task(task, db)


def complete_task(db: Session, user: User, task_id: str) -> Optional[TaskResponse]:
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        return None
    task.status = "completed"
    db.commit()
    run_schedule_for_user(user, db)
    db.refresh(task)
    return serialize_task(task, db)


def delete_task(db: Session, user: User, task_id: str) -> bool:
    """Permanently remove a task and all its schedule blocks and steps."""
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        return False
    step_ids = [
        sid for (sid,) in db.query(Task.id).filter(Task.parent_task_id == task.id).all()
    ]
    all_ids = [task.id, *step_ids]
    db.query(ScheduleBlock).filter(ScheduleBlock.task_id.in_(all_ids)).delete(synchronize_session=False)
    if step_ids:
        db.query(Task).filter(Task.id.in_(step_ids)).delete(synchronize_session=False)
    db.delete(task)
    db.commit()
    run_schedule_for_user(user, db)
    return True


def reschedule_task(
    db: Session, user: User, task_id: str, new_deadline: datetime
) -> Optional[TaskResponse]:
    """Push a task to a new deadline and re-score."""
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        return None
    task.deadline = new_deadline
    task.status = "pending"
    apply_task_scores(task, recompute_urgency=True)
    db.commit()
    run_schedule_for_user(user, db)
    db.refresh(task)
    return serialize_task(task, db)


def update_task(
    db: Session, user: User, task_id: str, updates: dict
) -> Optional[TaskResponse]:
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        return None
    recompute_urgency = "deadline" in updates
    recompute_importance = "importance" in updates
    for field, value in updates.items():
        setattr(task, field, value)
    apply_task_scores(task, recompute_urgency=recompute_urgency, recompute_importance=recompute_importance)
    db.commit()
    db.refresh(task)
    run_schedule_for_user(user, db)
    db.refresh(task)
    return serialize_task(task, db)


def add_steps(
    db: Session, user: User, task_id: str, text: str
) -> Optional[list[str]]:
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
        created.append(step)
    db.commit()
    return [s.title for s in created]


def complete_step(db: Session, user: User, step_id: str) -> bool:
    step = db.query(Task).filter(Task.id == step_id, Task.user_id == user.id).first()
    if not step or step.parent_task_id is None:
        return False
    step.status = "completed"
    db.commit()
    return True


def start_task(db: Session, user: User, task_id: str) -> Optional[TaskResponse]:
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        return None
    task.status = "in_progress"
    db.commit()
    db.refresh(task)
    return serialize_task(task, db)


async def process_brain_dump(
    db: Session, user: User, text: str
) -> list[TaskResponse]:
    parsed = await parse_brain_dump(text, user_timezone=user.timezone)
    tasks_to_add = []
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
        apply_task_scores(task, recompute_urgency=True, recompute_importance=True)
        tasks_to_add.append((task, p))

    for task, _ in tasks_to_add:
        db.add(task)
    db.flush()

    for task, p in tasks_to_add:
        for step_title in p.steps:
            step = Task(
                user_id=user.id,
                title=step_title,
                parent_task_id=task.id,
                deadline=task.deadline,
                effort=task.effort,
                importance=task.importance,
                context=task.context,
                status="pending",
            )
            apply_task_scores(step, recompute_urgency=True, recompute_importance=True)
            db.add(step)

    db.commit()
    run_schedule_for_user(user, db)

    result = []
    for task, _ in tasks_to_add:
        db.refresh(task)
        result.append(serialize_task(task, db))
    return result
```

**Step 4: Run tests to confirm they pass**

```bash
cd backend && pytest tests/test_task_service.py -v
```
Expected: 3 tests PASS

**Step 5: Refactor `routers/tasks.py` to use the service layer**

Replace all inline logic with calls to `task_service.*`. The router keeps only HTTP concerns (auth, request parsing, HTTP errors). For example:

```python
# routers/tasks.py — after refactor
from app.services import task_service

@router.get("/today", response_model=TodayResponse)
def get_today(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return task_service.get_today(db, user)

@router.post("/{task_id}/complete", response_model=TaskResponse)
def complete_task(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = task_service.complete_task(db, user, task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result

# ... same pattern for all other endpoints
```

Remove the now-redundant `_generate_why`, `_apply_task_scores`, `_serialize_task`, `_scheduled_today_ids`, `_compute_score` from `routers/tasks.py`.

**Step 6: Refactor `telegram/db_helpers.py` to use the service layer**

```python
# telegram/db_helpers.py — after refactor
from app.database import SessionLocal
from app.models import User
from app.services import task_service


def _get_user(chat_id: int):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()


async def get_today_for_chat_id(chat_id: int):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        if not user:
            return None
        return task_service.get_today(db, user)
    finally:
        db.close()


async def complete_task_for_chat_id(chat_id: int, task_id: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        if not user:
            return False
        return task_service.complete_task(db, user, task_id) is not None
    finally:
        db.close()

# ... same pattern for all other helpers
# delete_task_for_chat_id → task_service.delete_task
# reschedule_task_for_chat_id(chat_id, task_id, new_deadline) → task_service.reschedule_task
# why_task_for_chat_id → task_service.generate_why (after fetching task)
# etc.
```

Remove all duplicated `_generate_why`, `_apply_task_scores`, `_serialize_task` from `db_helpers.py`.

**Step 7: Run full test suite**

```bash
cd backend && pytest -v
```
Expected: all existing tests pass

**Step 8: Commit**

```bash
git add backend/app/services/task_service.py backend/app/routers/tasks.py backend/app/telegram/db_helpers.py backend/tests/test_task_service.py
git commit -m "refactor: extract task_service.py as shared business logic layer for API and Telegram bot"
```

---

## Task 2: Skip → Delete, Reschedule → Ask When

**Files:**
- Modify: `backend/app/telegram/handlers/today.py`
- Modify: `backend/app/telegram/handlers/callbacks.py`
- Modify: `backend/app/telegram/db_helpers.py`
- Test: `backend/tests/test_telegram_reschedule.py`

### The new button layout for today view

Old: `[✅ Done] [⏭️ Skip]` / `[📋 Steps] [❓ Why?]`

New: `[✅ Done] [🗑️ Skip]` / `[🔄 Reschedule] [▶️ Start]` / `[📋 Steps] [❓ Why?]`

- **Skip** (`skip:{id}`) = delete task permanently. Shows confirmation first.
- **Reschedule** (`reschedule:{id}`) = opens "when?" keyboard
- **Start** (`start:{id}`) = marks `in_progress`

### Reschedule "when?" keyboard

```
[📅 Tomorrow]      [📅 In 3 days]
[📅 This weekend]  [📅 Next week]
```
Callback data: `reschedule_pick:{task_id}:{offset_days}`
- Tomorrow = 1
- In 3 days = 3
- This weekend = days until Saturday
- Next week = 7

### Skip confirmation keyboard

```
[🗑️ Yes, remove it]   [Cancel]
```
Callback data: `skip_confirm:{task_id}` / `skip_cancel`

**Step 1: Write failing tests**

```python
# backend/tests/test_telegram_reschedule.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_reschedule_callback_sends_when_keyboard():
    """Clicking Reschedule sends a 'when?' message with date buttons."""
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.data = "reschedule:task-123"
    update.effective_chat.id = 42
    context = MagicMock()

    with patch("app.telegram.db_helpers.get_task_for_chat_id") as mock_get:
        mock_get.return_value = MagicMock(title="Essay", id="task-123")
        from app.telegram.handlers.callbacks import handle_callback
        await handle_callback(update, context)

    update.callback_query.message.reply_text.assert_called_once()
    call_args = update.callback_query.message.reply_text.call_args
    assert "when" in call_args[0][0].lower() or "when" in str(call_args).lower()


@pytest.mark.asyncio
async def test_skip_confirm_deletes_task():
    """Confirming skip calls delete_task_for_chat_id."""
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.data = "skip_confirm:task-123"
    update.effective_chat.id = 42
    context = MagicMock()

    with patch("app.telegram.db_helpers.delete_task_for_chat_id") as mock_del:
        mock_del.return_value = True
        from app.telegram.handlers.callbacks import handle_callback
        await handle_callback(update, context)

    mock_del.assert_called_once_with(42, "task-123")


@pytest.mark.asyncio
async def test_reschedule_pick_updates_deadline():
    """Picking 'In 3 days' calls reschedule_task_for_chat_id with correct deadline."""
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.data = "reschedule_pick:task-123:3"
    update.effective_chat.id = 42
    context = MagicMock()

    with patch("app.telegram.db_helpers.reschedule_task_for_chat_id") as mock_reschedule:
        mock_reschedule.return_value = MagicMock(title="Essay")
        from app.telegram.handlers.callbacks import handle_callback
        await handle_callback(update, context)

    mock_reschedule.assert_called_once()
    args = mock_reschedule.call_args[0]
    assert args[1] == "task-123"
    expected_date = datetime.utcnow() + timedelta(days=3)
    actual_date = args[2]
    assert abs((actual_date - expected_date).total_seconds()) < 60
```

**Step 2: Run to confirm they fail**

```bash
cd backend && pytest tests/test_telegram_reschedule.py -v
```

**Step 3: Add `delete_task_for_chat_id` and `reschedule_task_for_chat_id` to `db_helpers.py`**

```python
# In db_helpers.py — add these two functions

async def delete_task_for_chat_id(chat_id: int, task_id: str) -> bool:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return False
        return task_service.delete_task(db, user, task_id)
    finally:
        db.close()


async def reschedule_task_for_chat_id(
    chat_id: int, task_id: str, new_deadline: datetime
) -> Optional[TaskResponse]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        return task_service.reschedule_task(db, user, task_id, new_deadline)
    finally:
        db.close()


async def start_task_for_chat_id(chat_id: int, task_id: str) -> Optional[TaskResponse]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        return task_service.start_task(db, user, task_id)
    finally:
        db.close()


async def get_task_for_chat_id(chat_id: int, task_id: str) -> Optional[TaskResponse]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
        if not task:
            return None
        return task_service.serialize_task(task, db)
    finally:
        db.close()
```

**Step 4: Update `today.py` to use new button layout**

```python
# handlers/today.py — updated keyboard block

if primary:
    keyboard = [
        [
            InlineKeyboardButton("✅ Done", callback_data=f"done:{primary.id}"),
            InlineKeyboardButton("🗑️ Skip", callback_data=f"skip:{primary.id}"),
        ],
        [
            InlineKeyboardButton("🔄 Reschedule", callback_data=f"reschedule:{primary.id}"),
            InlineKeyboardButton("▶️ Start", callback_data=f"start:{primary.id}"),
        ],
        [
            InlineKeyboardButton("📋 Steps", callback_data=f"steps:{primary.id}"),
            InlineKeyboardButton("❓ Why?", callback_data=f"why:{primary.id}"),
        ],
    ]
```

**Step 5: Add new callback handlers in `callbacks.py`**

```python
# In handle_callback, replace the skip: and add new handlers:

elif data.startswith("skip:"):
    task_id = data.split(":", 1)[1]
    # Fetch task title for confirmation
    task = await get_task_for_chat_id(chat_id, task_id)
    title = task.title if task else "this task"
    await query.message.reply_text(
        f"🗑️ Remove *{title}* from your list permanently?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Yes, remove it", callback_data=f"skip_confirm:{task_id}"),
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
        # Show updated today view
        from app.telegram.handlers.today import today_command
        await today_command(update, context)
    else:
        await query.edit_message_text("⚠️ Couldn't remove that task.")

elif data == "skip_cancel":
    await query.edit_message_text("Okay, keeping it on your list.")

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
```

**Step 6: Run tests**

```bash
cd backend && pytest tests/test_telegram_reschedule.py -v
```
Expected: 3 PASS

**Step 7: Commit**

```bash
git add backend/app/telegram/ backend/tests/test_telegram_reschedule.py
git commit -m "feat: telegram skip=delete with confirmation, reschedule=pick date, start task button"
```

---

## Task 3: Fix Telegram UX Bugs

**Files:**
- Modify: `backend/app/telegram/handlers/callbacks.py`
- Modify: `backend/app/telegram/handlers/commands.py`
- Modify: `backend/app/telegram/handlers/today.py`
- Modify: `backend/app/telegram/handlers/voice.py`

### Bug 1: "Why?" sends a message, not a popup

In `callbacks.py`, replace:
```python
# OLD
await query.answer(explanation or "...", show_alert=True)

# NEW
await query.answer()  # dismiss the loading spinner
await query.message.reply_text(explanation or "Couldn't explain that task.", parse_mode="Markdown")
```

### Bug 2: `/list` — single message, not per-task flood

In `commands.py`, replace the per-task loop with:

```python
async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.telegram.db_helpers import list_tasks_for_chat_id
    chat_id = update.effective_chat.id
    await _clear_conversation_state(chat_id)
    tasks = await list_tasks_for_chat_id(chat_id)
    if tasks is None:
        await update.message.reply_text("You're not linked yet. Send your registered email.")
        return
    if not tasks:
        await update.message.reply_text("📭 No tasks yet. Use /dump to add some.")
        return

    lines = [f"📋 *Your tasks* ({len(tasks)} pending):\n"]
    for i, t in enumerate(tasks, 1):
        deadline_str = f" — due {t.deadline.strftime('%b %d')}" if t.deadline else ""
        status_icon = "▶️ " if t.status == "in_progress" else ""
        lines.append(f"{i}. {status_icon}{t.title}{deadline_str}")

    lines.append("\nTap a number or use /today to see your #1 priority.")
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{i}. {t.title[:30]}", callback_data=f"task_actions:{t.id}")]
            for i, t in enumerate(tasks[:8], 1)
        ])
    )
```

Add `task_actions:{task_id}` callback in `callbacks.py`:

```python
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
```

### Bug 3: Unify `tasks` callback with `/list`

In `callbacks.py`, replace the `elif data == "tasks":` block:

```python
elif data == "tasks":
    from app.telegram.handlers.commands import list_command
    await list_command(update, context)
```

### Bug 4: Post-done and post-task-actions show next task

After every successful done/complete callback, add:

```python
# After edit_message_text("✅ Done!...")
from app.telegram.handlers.today import today_command
await today_command(update, context)
```

### Bug 5: Voice messages run intent classifier first

In `voice.py`, replace the direct dump call:

```python
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... transcription code stays the same ...
    
    # After getting `text`:
    await update.message.reply_text(f"📝 Heard: _{text}_", parse_mode="Markdown")

    # Run intent classifier on the transcript — don't assume dump
    from app.telegram import intent as intent_module
    from app.telegram.handlers.commands import done_command, skip_command
    from app.telegram.handlers.today import today_command as _today_cmd

    intent = await intent_module.classify_intent(text, has_pending_steps=False)
    if intent == "complete":
        await done_command(update, context)
        return
    if intent == "skip":
        await skip_command(update, context)
        return
    if intent == "today":
        await _today_cmd(update, context)
        return

    # Default: brain dump
    await update.message.reply_text("⏳ Parsing tasks...")
    tasks = await process_dump_for_chat_id(chat_id, text)
    # ... rest of dump handling unchanged
```

### Bug 6: Step completion buttons

In `callbacks.py`, update the `steps:` handler to add completion buttons:

```python
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
```

Add to `db_helpers.py`:

```python
async def complete_step_for_chat_id(chat_id: int, step_id: str) -> bool:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return False
        return task_service.complete_step(db, user, step_id)
    finally:
        db.close()
```

**Step: Run existing tests**

```bash
cd backend && pytest -v
```
Expected: all pass

**Step: Commit**

```bash
git add backend/app/telegram/
git commit -m "fix: telegram UX — why as message, list as single msg, voice intent routing, step completion buttons, post-done shows next task"
```

---

## Task 4: Proactive Notifications with APScheduler

**Files:**
- Create: `backend/app/workers/notification_jobs.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_notification_jobs.py`

**Dependencies:** Add to `requirements.txt`:
```
APScheduler>=3.10.0
```

### What gets scheduled

| Job | Time (UTC) | Action |
|---|---|---|
| `morning_brief` | 08:00 daily | Query all linked users → get today → send via Telegram |
| `evening_wrapup` | 21:00 daily | Count completed/missed today → send via Telegram |
| `weekly_summary` | 19:00 Sunday | Count week's tasks → send via Telegram |

The message builders already exist in `services/notifier.py` — they just need to be called.

**Step 1: Write failing tests**

```python
# backend/tests/test_notification_jobs.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_morning_brief_sends_to_linked_users():
    """morning_brief_job sends a message to each user with a telegram_chat_id."""
    mock_user = MagicMock()
    mock_user.id = "user-1"
    mock_user.name = "Alice"
    mock_user.telegram_chat_id = 12345

    mock_primary = MagicMock()
    mock_primary.title = "Essay"
    mock_primary.effort = "high"
    mock_primary.deadline = datetime.utcnow() + timedelta(days=1)

    with patch("app.workers.notification_jobs.SessionLocal") as mock_session_cls, \
         patch("app.workers.notification_jobs.task_service.get_today") as mock_today, \
         patch("app.workers.notification_jobs._send_telegram_message") as mock_send:

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_user]

        mock_today.return_value = MagicMock(primary=mock_primary, secondary=[])
        mock_send.return_value = None

        from app.workers.notification_jobs import morning_brief_job
        await morning_brief_job()

        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert args[0] == 12345
        assert "Essay" in args[1]


@pytest.mark.asyncio
async def test_morning_brief_skips_unlinked_users():
    """morning_brief_job does not send to users without telegram_chat_id."""
    mock_user = MagicMock()
    mock_user.telegram_chat_id = None

    with patch("app.workers.notification_jobs.SessionLocal") as mock_session_cls, \
         patch("app.workers.notification_jobs._send_telegram_message") as mock_send:

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_user]

        from app.workers.notification_jobs import morning_brief_job
        await morning_brief_job()

        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_evening_wrapup_counts_completed():
    """evening_wrapup_job reports correct count of completed tasks today."""
    mock_user = MagicMock()
    mock_user.id = "user-1"
    mock_user.telegram_chat_id = 12345

    with patch("app.workers.notification_jobs.SessionLocal") as mock_session_cls, \
         patch("app.workers.notification_jobs._send_telegram_message") as mock_send:

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [mock_user],         # all linked users
            [MagicMock(), MagicMock()],  # 2 completed tasks today
            [],                  # 0 missed tasks
        ]

        from app.workers.notification_jobs import evening_wrapup_job
        await evening_wrapup_job()

        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert "2" in args[1]
```

**Step 2: Run to confirm failure**

```bash
cd backend && pytest tests/test_notification_jobs.py -v
```

**Step 3: Create `backend/app/workers/notification_jobs.py`**

```python
"""
APScheduler jobs for proactive Telegram notifications.
Scheduled in main.py lifespan.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import User, Task
from app.services import task_service
from app.services.notifier import (
    build_morning_brief,
    build_evening_wrapup,
    build_weekly_summary,
)

logger = logging.getLogger(__name__)

_bot = None  # Set at startup


def set_bot(bot):
    global _bot
    _bot = bot


async def _send_telegram_message(chat_id: int, text: str) -> None:
    if _bot is None:
        logger.warning("Notification bot not set — skipping message to %s", chat_id)
        return
    try:
        await _bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error("Failed to send Telegram message to %s: %s", chat_id, e)


async def morning_brief_job() -> None:
    """8:00 UTC: Send today's #1 task to every linked user."""
    logger.info("Running morning_brief_job")
    with SessionLocal() as db:
        users = db.query(User).filter(User.telegram_chat_id.isnot(None)).all()
        for user in users:
            try:
                today = task_service.get_today(db, user)
                msg = build_morning_brief(
                    user.name or "there",
                    today.primary,
                    today.secondary,
                )
                await _send_telegram_message(user.telegram_chat_id, msg)
            except Exception as e:
                logger.error("morning_brief failed for user %s: %s", user.id, e)


async def evening_wrapup_job() -> None:
    """21:00 UTC: Report completed vs missed tasks today."""
    logger.info("Running evening_wrapup_job")
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)

    with SessionLocal() as db:
        users = db.query(User).filter(User.telegram_chat_id.isnot(None)).all()
        for user in users:
            try:
                completed = (
                    db.query(Task)
                    .filter(
                        Task.user_id == user.id,
                        Task.status == "completed",
                        Task.updated_at >= today_start,
                        Task.updated_at < tomorrow_start,
                        Task.parent_task_id.is_(None),
                    )
                    .count()
                )
                missed = (
                    db.query(Task)
                    .filter(
                        Task.user_id == user.id,
                        Task.status == "missed",
                        Task.updated_at >= today_start,
                        Task.updated_at < tomorrow_start,
                        Task.parent_task_id.is_(None),
                    )
                    .count()
                )
                msg = build_evening_wrapup(completed, missed)
                await _send_telegram_message(user.telegram_chat_id, msg)
            except Exception as e:
                logger.error("evening_wrapup failed for user %s: %s", user.id, e)


async def weekly_summary_job() -> None:
    """19:00 UTC Sunday: Weekly wrap-up stats."""
    logger.info("Running weekly_summary_job")
    week_start = datetime.utcnow() - timedelta(days=7)

    with SessionLocal() as db:
        users = db.query(User).filter(User.telegram_chat_id.isnot(None)).all()
        for user in users:
            try:
                completed = (
                    db.query(Task)
                    .filter(
                        Task.user_id == user.id,
                        Task.status == "completed",
                        Task.updated_at >= week_start,
                        Task.parent_task_id.is_(None),
                    )
                    .count()
                )
                missed = (
                    db.query(Task)
                    .filter(
                        Task.user_id == user.id,
                        Task.status == "missed",
                        Task.updated_at >= week_start,
                        Task.parent_task_id.is_(None),
                    )
                    .count()
                )
                msg = build_weekly_summary(user.name or "there", completed, missed, [])
                await _send_telegram_message(user.telegram_chat_id, msg)
            except Exception as e:
                logger.error("weekly_summary failed for user %s: %s", user.id, e)


def _run_async_job(coro_fn):
    """Wrap an async job for APScheduler (which calls sync callables)."""
    asyncio.create_task(coro_fn())
```

Note: `Task.updated_at` needs to exist on the model. If it doesn't, add an Alembic migration to add it (see Task 4a below).

**Step 3a: Check if `Task.updated_at` exists**

```bash
cd backend && python -c "from app.models import Task; print([c.name for c in Task.__table__.columns])"
```

If `updated_at` is missing, create migration:

```bash
cd backend && alembic revision --autogenerate -m "add updated_at to tasks"
alembic upgrade head
```

And add to Task model in `app/models/task.py`:
```python
updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Step 4: Wire APScheduler into FastAPI lifespan in `main.py`**

```python
# main.py — add to lifespan context manager

from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Telegram bot ---
    from app.telegram.bot import get_application
    from app.workers import notification_jobs
    
    tg_app = get_application()
    await tg_app.initialize()
    await tg_app.start()
    notification_jobs.set_bot(tg_app.bot)

    # --- Scheduler ---
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        notification_jobs.morning_brief_job,
        CronTrigger(hour=8, minute=0),
        id="morning_brief",
    )
    scheduler.add_job(
        notification_jobs.evening_wrapup_job,
        CronTrigger(hour=21, minute=0),
        id="evening_wrapup",
    )
    scheduler.add_job(
        notification_jobs.weekly_summary_job,
        CronTrigger(day_of_week="sun", hour=19, minute=0),
        id="weekly_summary",
    )
    scheduler.start()

    yield

    scheduler.shutdown()
    await tg_app.stop()
    await tg_app.shutdown()
```

**Step 5: Run tests**

```bash
cd backend && pytest tests/test_notification_jobs.py -v
```
Expected: 3 PASS

**Step 6: Run full suite**

```bash
cd backend && pytest -v
```

**Step 7: Commit**

```bash
git add backend/app/workers/notification_jobs.py backend/app/main.py backend/tests/test_notification_jobs.py requirements.txt
git commit -m "feat: proactive telegram notifications via APScheduler — morning brief, evening wrap-up, weekly summary"
```

---

## Task 5: Add Single Task via Natural Language

**Files:**
- Modify: `backend/app/telegram/intent.py`
- Modify: `backend/app/telegram/handlers/message.py`
- Modify: `backend/app/telegram/db_helpers.py`
- Test: `backend/tests/test_intent.py`

**Goal:** "add essay due Friday" or "remind me about lab report on Monday" → create one task without going through the full brain dump pipeline.

**Step 1: Add `add_task` as a classifiable intent**

In `intent.py`, add to keyword lists:

```python
_ADD_TASK = ["add ", "remind me", "track ", "don't forget", "new task", "create task"]
```

And in `classify_intent`:
```python
if any(p in lower for p in _ADD_TASK):
    return "add_task"
```

Update `_gpt_classify` system prompt to include `'add_task'` as a valid return value:

```python
"content": (
    "You classify student messages for a productivity bot. "
    "Return exactly one word.\n"
    "'dump' = message contains multiple tasks, deadlines, events.\n"
    "'add_task' = message asks to add or track a single specific task.\n"
    "'unclear' = chit-chat, greetings, questions, or random text."
)
```

**Step 2: Handle `add_task` intent in `message.py`**

```python
if intent == "add_task":
    from app.telegram.db_helpers import add_single_task_for_chat_id
    task = await add_single_task_for_chat_id(chat_id, text)
    if task:
        deadline_str = f" — due {task.deadline.strftime('%a %b %d')}" if task.deadline else ""
        await update.message.reply_text(
            f"✅ Added: *{task.title}*{deadline_str}\n\nUse /today to see your priority.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "🤔 Couldn't parse that. Try: _'add essay due Friday'_",
            parse_mode="Markdown",
        )
    return
```

**Step 3: Add `add_single_task_for_chat_id` to `db_helpers.py`**

Re-use the existing brain dump parser but extract only the first task:

```python
async def add_single_task_for_chat_id(chat_id: int, text: str) -> Optional[TaskResponse]:
    """Parse a single-task instruction and create it. Returns the created task or None."""
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        # Reuse the AI parser — it handles deadline extraction, effort inference etc.
        tasks = await task_service.process_brain_dump(db, user, text)
        return tasks[0] if tasks else None
    finally:
        db.close()
```

**Step 4: Write tests**

```python
# backend/tests/test_intent.py
import pytest
from app.telegram.intent import classify_intent


@pytest.mark.asyncio
async def test_classify_add_task():
    result = await classify_intent("add essay due Friday", has_pending_steps=False)
    assert result == "add_task"


@pytest.mark.asyncio
async def test_classify_complete():
    result = await classify_intent("just finished my homework", has_pending_steps=False)
    assert result == "complete"


@pytest.mark.asyncio
async def test_classify_skip():
    result = await classify_intent("not doing that today", has_pending_steps=False)
    assert result == "skip"
```

**Step 5: Run tests**

```bash
cd backend && pytest tests/test_intent.py -v
```

**Step 6: Run full suite**

```bash
cd backend && pytest -v
```

**Step 7: Commit**

```bash
git add backend/app/telegram/ backend/tests/test_intent.py
git commit -m "feat: telegram understands 'add task' intent — single task creation from natural language"
```

---

## Final Verification

**Step 1: Run complete test suite**

```bash
cd backend && pytest -v --tb=short
```
Expected: all tests pass, no regressions

**Step 2: Manual smoke test checklist**

Start the server:
```bash
cd backend && uvicorn app.main:app --reload
```

In Telegram, verify:
- [ ] `/start` → welcome message if unlinked, menu if linked
- [ ] Send email → account links, menu appears
- [ ] `/today` → shows task with Done / Skip / Reschedule / Start / Steps / Why buttons
- [ ] Click **Done** → task marked complete, new today view appears automatically
- [ ] Click **Skip** → confirmation appears, confirm → task deleted, today view updates
- [ ] Click **Reschedule** → "when?" keyboard appears with 4 date options
- [ ] Click a date → task rescheduled, today view updates
- [ ] Click **Start** → task status set to in_progress
- [ ] Click **Why?** → explanation sent as a message (not popup)
- [ ] Click **Steps** → steps shown with individual ✅ buttons
- [ ] Click a step ✅ button → step marked done
- [ ] `/list` → single formatted message with inline "manage" buttons per task
- [ ] Brain dump (text) → tasks created, count confirmed
- [ ] Voice note: "done with my essay" → marks task complete (not creating a new task)
- [ ] Voice note: tasks dictated → brain dump flow
- [ ] "add lab report due Monday" → single task created
- [ ] `/menu` → all 5 options

**Step 3: Final commit**

```bash
git add .
git commit -m "feat: telegram bot overhaul complete — shared service layer, skip/reschedule, notifications, UX fixes"
```

---

## Dependency Notes

- `APScheduler>=3.10.0` must be added to `requirements.txt`
- `Task.updated_at` column required for evening wrap-up and weekly summary — run migration if missing
- No new env vars required — all config already in `.env.example`
- The `SessionLocal` context manager form (`with SessionLocal() as db`) requires SQLAlchemy session to support `__enter__`/`__exit__` — verify this in `database.py` and use `SessionLocal()` + manual `.close()` if not supported
