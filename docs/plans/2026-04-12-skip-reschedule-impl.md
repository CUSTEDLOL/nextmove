# Skip & Reschedule Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Skip (permanent delete) and Reschedule (snooze) actions to the hero task card, with auto-expiry of overdue snoozed tasks.

**Architecture:** New `snoozed_until` Date column on tasks controls snooze state. Skip reuses the existing delete endpoint. Both `get_today` and `schedule_runner` gain two new exclusion filters: snoozed tasks and tasks past their deadline. The frontend `HeroTaskCard` gets two new buttons; the dashboard page wires up the handlers.

**Tech Stack:** Python/FastAPI/SQLAlchemy/Alembic (backend), Next.js/TypeScript/Tailwind/React (frontend), pytest (backend tests)

**Design doc:** `docs/plans/2026-04-12-skip-reschedule-design.md`

---

## Task 1: Add `snoozed_until` column to Task model + migration

**Files:**
- Modify: `backend/app/models/task.py`
- Create: `backend/alembic/versions/<hash>_add_snoozed_until_to_tasks.py` (auto-generated)

**Step 1: Add the column to the ORM model**

In `backend/app/models/task.py`, add after the `updated_at` line:

```python
from sqlalchemy import Column, String, Float, Integer, DateTime, Date, ForeignKey, Text
# (add Date to the existing import)

snoozed_until = Column(Date, nullable=True)
```

Full updated imports line (replace existing):
```python
from sqlalchemy import Column, String, Float, Integer, DateTime, Date, ForeignKey, Text
```

**Step 2: Generate the Alembic migration**

```bash
cd backend && alembic revision --autogenerate -m "add_snoozed_until_to_tasks"
```

Expected: new file created at `backend/alembic/versions/<hash>_add_snoozed_until_to_tasks.py`

Open that file and verify it contains:
```python
op.add_column('tasks', sa.Column('snoozed_until', sa.Date(), nullable=True))
```

**Step 3: Apply the migration**

```bash
cd backend && alembic upgrade head
```

Expected: `Running upgrade ... -> <hash>, add_snoozed_until_to_tasks`

**Step 4: Commit**

```bash
git add backend/app/models/task.py backend/alembic/versions/
git commit -m "feat(db): add snoozed_until column to tasks"
```

---

## Task 2: Snooze endpoint + schema updates

**Files:**
- Modify: `backend/app/schemas/tasks.py`
- Modify: `backend/app/routers/tasks.py`
- Test: `backend/tests/test_tasks_api.py`

**Step 1: Write the failing tests**

Append to `backend/tests/test_tasks_api.py`:

```python
def test_snooze_task(client):
    # Create a task to snooze
    resp = client.post("/api/tasks", json={"title": "Snooze me", "effort": "low", "importance": 3})
    assert resp.status_code == 200
    task_id = resp.json()["id"]

    # Snooze it for 1 day
    snooze_resp = client.post(f"/api/tasks/{task_id}/snooze", json={"days": 1})
    assert snooze_resp.status_code == 200
    data = snooze_resp.json()
    assert data["snoozed_until"] is not None

    # Verify it no longer appears in today's tasks
    today_resp = client.get("/api/tasks/today")
    assert today_resp.status_code == 200
    today_data = today_resp.json()
    all_ids = []
    if today_data.get("primary"):
        all_ids.append(today_data["primary"]["id"])
    all_ids += [t["id"] for t in today_data.get("secondary", [])]
    assert task_id not in all_ids


def test_snooze_task_invalid_days(client):
    resp = client.post("/api/tasks", json={"title": "Temp task", "effort": "low", "importance": 2})
    task_id = resp.json()["id"]
    bad_resp = client.post(f"/api/tasks/{task_id}/snooze", json={"days": 99})
    assert bad_resp.status_code == 422


def test_snooze_nonexistent_task(client):
    import uuid
    resp = client.post(f"/api/tasks/{uuid.uuid4()}/snooze", json={"days": 1})
    assert resp.status_code == 404
```

**Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_tasks_api.py::test_snooze_task tests/test_tasks_api.py::test_snooze_task_invalid_days tests/test_tasks_api.py::test_snooze_nonexistent_task -v
```

Expected: FAIL — `405 Method Not Allowed` or `404` (endpoint doesn't exist yet)

**Step 3: Add `SnoozeRequest` schema and update `TaskResponse`**

In `backend/app/schemas/tasks.py`:

Add import at top:
```python
from datetime import datetime, date
```
(replace existing `from datetime import datetime`)

Add new schema after `TaskUpdate`:
```python
class SnoozeRequest(BaseModel):
    days: int = Field(..., ge=1, le=7)
```

Add `snoozed_until` field to `TaskResponse`:
```python
snoozed_until: Optional[date] = None
```

**Step 4: Update `_serialize_task` to include `snoozed_until`**

In `backend/app/routers/tasks.py`, update the `_serialize_task` return to include:
```python
snoozed_until=task.snoozed_until,
```

Also update imports at top of `routers/tasks.py`:
```python
from app.schemas.tasks import (
    TaskCreate, TaskUpdate, TaskResponse, BrainDumpRequest, BrainDumpResponse,
    TodayResponse, StepsDumpRequest, SnoozeRequest
)
```

**Step 5: Add the snooze endpoint**

In `backend/app/routers/tasks.py`, add after the `reschedule_task` function:

```python
@router.post("/{task_id}/snooze", response_model=TaskResponse)
def snooze_task(
    task_id: str,
    req: SnoozeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    from datetime import date, timedelta
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.snoozed_until = date.today() + timedelta(days=req.days)
    db.commit()
    db.refresh(task)
    return _serialize_task(task, db)
```

**Step 6: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_tasks_api.py::test_snooze_task tests/test_tasks_api.py::test_snooze_task_invalid_days tests/test_tasks_api.py::test_snooze_nonexistent_task -v
```

Expected: all 3 PASS

**Step 7: Commit**

```bash
git add backend/app/schemas/tasks.py backend/app/routers/tasks.py backend/tests/test_tasks_api.py
git commit -m "feat(api): add snooze endpoint for tasks"
```

---

## Task 3: Filter snoozed + overdue tasks from `get_today` and scheduler

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/app/services/schedule_runner.py`
- Test: `backend/tests/test_tasks_api.py`

**Step 1: Write failing tests**

Append to `backend/tests/test_tasks_api.py`:

```python
def test_overdue_task_not_in_today(client):
    from datetime import datetime, timedelta
    # Create a task with a deadline in the past
    past_deadline = (datetime.utcnow() - timedelta(days=3)).isoformat()
    resp = client.post("/api/tasks", json={
        "title": "Overdue task",
        "effort": "low",
        "importance": 3,
        "deadline": past_deadline,
    })
    assert resp.status_code == 200
    task_id = resp.json()["id"]

    today_resp = client.get("/api/tasks/today")
    assert today_resp.status_code == 200
    today_data = today_resp.json()
    all_ids = []
    if today_data.get("primary"):
        all_ids.append(today_data["primary"]["id"])
    all_ids += [t["id"] for t in today_data.get("secondary", [])]
    assert task_id not in all_ids
```

**Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_tasks_api.py::test_overdue_task_not_in_today -v
```

Expected: FAIL — overdue task currently appears in today's queue

**Step 3: Add shared filter helper in `routers/tasks.py`**

Add this import at the top of `backend/app/routers/tasks.py`:
```python
from datetime import datetime, timedelta, date
```
(replace existing `from datetime import datetime, timedelta`)

Add a helper function after the `ACTIVE_TASK_STATUSES` line:

```python
def _active_task_filters():
    """Exclusion filters: snoozed tasks and tasks past their deadline."""
    from sqlalchemy import or_
    today = date.today()
    now = datetime.utcnow()
    return [
        or_(Task.snoozed_until.is_(None), Task.snoozed_until <= today),
        or_(Task.deadline.is_(None), Task.deadline >= now),
    ]
```

**Step 4: Apply filters to `get_today`**

In the `get_today` function, update the query:

```python
@router.get("/today", response_model=TodayResponse)
def get_today(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user.id,
            Task.parent_task_id.is_(None),
            Task.status.in_(ACTIVE_TASK_STATUSES),
            *_active_task_filters(),
        )
        .order_by(Task.priority_index.desc())
        .limit(4)
        .all()
    )
    primary = tasks[0] if tasks else None
    secondary = tasks[1:4] if len(tasks) > 1 else []
    scheduled_today_ids = _scheduled_today_ids(db, user.id)
    return TodayResponse(
        primary=_serialize_task(primary, db, scheduled_today_ids=scheduled_today_ids) if primary else None,
        secondary=[
            _serialize_task(task, db, scheduled_today_ids=scheduled_today_ids)
            for task in secondary
        ],
    )
```

**Step 5: Apply filters to `schedule_runner.py`**

In `backend/app/services/schedule_runner.py`, update the task query in `run_schedule_for_user`:

```python
from datetime import datetime, date
from sqlalchemy import or_

# Inside run_schedule_for_user, replace the existing tasks query with:
today = date.today()
now = datetime.utcnow()
tasks = (
    db.query(Task)
    .filter(
        Task.user_id == user.id,
        Task.parent_task_id.is_(None),
        Task.status.in_(ACTIVE_SCHEDULE_STATUSES),
        or_(Task.snoozed_until.is_(None), Task.snoozed_until <= today),
        or_(Task.deadline.is_(None), Task.deadline >= now),
    )
    .order_by(Task.priority_index.desc())
    .all()
)
```

**Step 6: Run all tests**

```bash
cd backend && pytest tests/test_tasks_api.py -v
```

Expected: all tests PASS including `test_overdue_task_not_in_today` and `test_snooze_task`

**Step 7: Commit**

```bash
git add backend/app/routers/tasks.py backend/app/services/schedule_runner.py backend/tests/test_tasks_api.py
git commit -m "feat(scheduler): filter snoozed and overdue tasks from today view and schedule"
```

---

## Task 4: Frontend — types, API client

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/tasks.ts`

**Step 1: Add `snoozed_until` to Task type**

In `frontend/src/types/index.ts`, update the `Task` interface:

```ts
export interface Task {
  id: string;
  title: string;
  effort: "low" | "medium" | "high";
  deadline: string | null;
  state: TaskState;
  priority_score: number;
  is_primary: boolean;
  notes: string | null;
  created_at: string;
  snoozed_until: string | null;   // add this line
  steps?: Step[];
}
```

**Step 2: Add `snoozeTask` to `api.ts`**

In `frontend/src/lib/api.ts`, add inside the `api` object after `rescheduleTask`:

```ts
snoozeTask: (id: string, days: 1 | 2 | 7) =>
  authFetch(`/api/tasks/${id}/snooze`, { method: "POST", body: JSON.stringify({ days }) }),
```

**Step 3: Add `snoozed_until` to `mapApiTask`**

In `frontend/src/lib/tasks.ts`, update `mapApiTask` to include:

```ts
snoozed_until: raw.snoozed_until ? String(raw.snoozed_until) : null,
```

Add it after the `created_at` line in the returned object.

**Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors

**Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/api.ts frontend/src/lib/tasks.ts
git commit -m "feat(frontend): add snoozed_until type + snoozeTask API method"
```

---

## Task 5: Update `HeroTaskCard` with Skip + Reschedule buttons

**Files:**
- Modify: `frontend/src/components/dashboard/HeroTaskCard.tsx`

**Step 1: Update the component**

Replace the entire file content with:

```tsx
"use client";

import { useState } from "react";
import { Check, Clock, Flame, ChevronRight, SkipForward, CalendarClock } from "lucide-react";
import { Task } from "@/types";
import { cn } from "@/lib/utils";

interface HeroTaskCardProps {
  task: Task;
  onComplete: (id: string) => void;
  onSkip: (id: string) => void;
  onSnooze: (id: string, days: 1 | 2 | 7) => void;
  onEdit: (task: Task) => void;
}

function effortLabel(effort: Task["effort"]): string {
  if (effort === "low") return "1h";
  if (effort === "high") return "4h";
  return "2h";
}

function effortColor(effort: Task["effort"]): string {
  if (effort === "low") return "bg-sky-50 text-sky-700";
  if (effort === "high") return "bg-rose-50 text-rose-700";
  return "bg-amber-50 text-amber-700";
}

function formatDeadline(iso: string | null): string {
  if (!iso) return "No deadline";
  const d = new Date(iso);
  const today = new Date();
  const diff = Math.ceil((d.getTime() - today.getTime()) / 86400000);
  if (diff === 0) return "Due today";
  if (diff === 1) return "Due tomorrow";
  if (diff < 0) return `${Math.abs(diff)}d overdue`;
  return `Due in ${diff}d`;
}

export function HeroTaskCard({ task, onComplete, onSkip, onSnooze, onEdit }: HeroTaskCardProps) {
  const [snoozeOpen, setSnoozeOpen] = useState(false);

  function handleSnooze(days: 1 | 2 | 7) {
    setSnoozeOpen(false);
    onSnooze(task.id, days);
  }

  return (
    <div className="w-full bg-white border border-[var(--border)] rounded-2xl p-6 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-semibold text-emerald-600 uppercase tracking-wider">
          Today&apos;s #1 Task
        </span>
        <span className="text-xs font-medium text-gray-400">
          Score {task.priority_score.toFixed(1)}
        </span>
      </div>

      {/* Title */}
      <h2 className="text-xl font-semibold text-gray-900 leading-snug mb-4">
        {task.title}
      </h2>

      {/* Meta */}
      <div className="flex items-center gap-3 mb-6">
        <span className={cn("text-xs font-medium px-2.5 py-1 rounded-full", effortColor(task.effort))}>
          <Flame className="w-3 h-3 inline mr-1 -mt-0.5" />
          {effortLabel(task.effort)} effort
        </span>
        <span className="flex items-center gap-1 text-xs text-gray-500">
          <Clock className="w-3.5 h-3.5" />
          {formatDeadline(task.deadline)}
        </span>
      </div>

      {/* Notes */}
      {task.notes && (
        <p className="text-sm text-gray-500 mb-6 bg-gray-50 rounded-lg px-3 py-2">
          {task.notes}
        </p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => onComplete(task.id)}
          className="flex-1 flex items-center justify-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium rounded-xl py-3 transition-colors"
        >
          <Check className="w-4 h-4" strokeWidth={2.5} />
          Mark Complete
        </button>

        {/* Reschedule with inline popover */}
        <div className="relative">
          <button
            onClick={() => setSnoozeOpen((v) => !v)}
            className="flex items-center justify-center gap-1.5 px-3 py-3 rounded-xl border border-[var(--border)] text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
            title="Reschedule"
          >
            <CalendarClock className="w-4 h-4" />
          </button>
          {snoozeOpen && (
            <div className="absolute bottom-full right-0 mb-2 w-40 bg-white border border-[var(--border)] rounded-xl shadow-lg overflow-hidden z-10">
              {([
                { label: "Tomorrow", days: 1 },
                { label: "In 2 days", days: 2 },
                { label: "Next week", days: 7 },
              ] as { label: string; days: 1 | 2 | 7 }[]).map(({ label, days }) => (
                <button
                  key={days}
                  onClick={() => handleSnooze(days)}
                  className="w-full text-left px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Skip */}
        <button
          onClick={() => onSkip(task.id)}
          className="flex items-center justify-center gap-1.5 px-3 py-3 rounded-xl border border-[var(--border)] text-sm font-medium text-gray-500 hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition-colors"
          title="Skip — removes this task"
        >
          <SkipForward className="w-4 h-4" />
        </button>

        {/* Edit */}
        <button
          onClick={() => onEdit(task)}
          className="flex items-center justify-center gap-1.5 px-3 py-3 rounded-xl border border-[var(--border)] text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
          title="Edit"
        >
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors

**Step 3: Commit**

```bash
git add frontend/src/components/dashboard/HeroTaskCard.tsx
git commit -m "feat(ui): add skip and reschedule buttons to HeroTaskCard"
```

---

## Task 6: Wire up Skip + Snooze handlers in dashboard page

**Files:**
- Modify: `frontend/src/app/dashboard/page.tsx`

**Step 1: Add `handleSkip` and `handleSnooze` functions**

In `frontend/src/app/dashboard/page.tsx`, add these two handlers after `handleComplete`:

```ts
async function handleSkip(id: string) {
  setTasks((prev) => prev.filter((t) => t.id !== id));
  try {
    await api.deleteTask(id);
    await Promise.all([refreshDashboard(), rebuildAndRefresh()]);
  } catch {
    // Keep optimistic removal.
  }
}

async function handleSnooze(id: string, days: 1 | 2 | 7) {
  try {
    await api.snoozeTask(id, days);
    await Promise.all([refreshDashboard(), rebuildAndRefresh()]);
  } catch {
    // Refresh failed — silently ignore.
  }
}
```

**Step 2: Pass new props to `HeroTaskCard`**

In the JSX, update the `HeroTaskCard` usage:

```tsx
<HeroTaskCard
  task={primaryTask}
  onComplete={handleComplete}
  onSkip={handleSkip}
  onSnooze={handleSnooze}
  onEdit={handleEdit}
/>
```

**Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors

**Step 4: Run full backend test suite**

```bash
cd backend && pytest -v
```

Expected: all tests PASS

**Step 5: Commit**

```bash
git add frontend/src/app/dashboard/page.tsx
git commit -m "feat(dashboard): wire up skip and snooze handlers"
```

---

## Task 7: Manual smoke test

Start both servers and verify end-to-end:

```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload

# Terminal 2
cd frontend && npm run dev
```

Checklist:
- [ ] Hero card shows 4 buttons: Mark Complete, Reschedule (calendar icon), Skip (forward icon), Edit (chevron)
- [ ] Clicking Reschedule opens inline popover with Tomorrow / In 2 days / Next week
- [ ] Selecting a snooze option: card refreshes, next task becomes hero, snoozed task gone
- [ ] Clicking Skip: task disappears immediately, next task becomes hero
- [ ] After skipping, the task is gone from `GET /api/tasks` entirely
- [ ] After snoozing, task is still in `GET /api/tasks` but absent from `GET /api/tasks/today`
