"""
Shared business logic for tasks.
Used by both routers/tasks.py and telegram/db_helpers.py.
Never import routers here — this layer has no HTTP concepts.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.schedule import ScheduleBlock
from app.models.user import User
from app.schemas.tasks import TaskResponse, TodayResponse
from app.services.matrix_scorer import score_task, TaskInput
from app.services.ai_parser import parse_brain_dump
from app.services.schedule_runner import run_schedule_for_user

logger = logging.getLogger(__name__)

ACTIVE_TASK_STATUSES = ["pending", "scheduled", "in_progress"]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def apply_task_scores(task: Task, *, recompute: bool = False) -> None:
    """Compute and set task.priority_index. Skips if already set and recompute=False."""
    if task.priority_index is not None and not recompute:
        return
    task.priority_index = score_task(TaskInput(
        deadline=task.deadline,
        effort=task.effort or "medium",
        importance=task.importance or 3,
        dependency_count=0,
    ))


# ---------------------------------------------------------------------------
# Why explanation
# ---------------------------------------------------------------------------

def generate_why(task: Task) -> str:
    reasons = []
    if task.deadline:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
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

def serialize_task(task: Task, db: Session, *, include_steps: bool = True) -> TaskResponse:
    steps = []
    if include_steps:
        child_steps = (
            db.query(Task)
            .filter(Task.parent_task_id == task.id)
            .order_by(Task.created_at)
            .all()
        )
        steps = [serialize_task(s, db, include_steps=False) for s in child_steps]

    # C-1: Determine whether any schedule block for this task falls within today (UTC).
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    scheduled_today = (
        db.query(ScheduleBlock.id)
        .filter(
            ScheduleBlock.task_id == task.id,
            ScheduleBlock.start_time < tomorrow_start,
            ScheduleBlock.end_time > today_start,
        )
        .first()
    ) is not None

    result = TaskResponse.model_validate(task)
    result.steps = steps
    result.scheduled_today = scheduled_today
    return result


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
    primary = serialize_task(tasks[0], db) if tasks else None
    secondary = [serialize_task(t, db) for t in tasks[1:4]]
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
    return [serialize_task(t, db) for t in tasks]


def get_steps(
    db: Session, user: User, task_id: str
) -> Optional[tuple[TaskResponse, list[dict]]]:
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        return None
    steps = db.query(Task).filter(Task.parent_task_id == task.id).order_by(Task.created_at).all()
    parent_data = serialize_task(task, db, include_steps=False)
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
    apply_task_scores(task, recompute=True)
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
    """Permanently remove a task, its schedule blocks, and all its steps."""
    from app.models.schedule import ScheduleBlock
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        return False
    step_ids = [
        sid for (sid,) in db.query(Task.id).filter(Task.parent_task_id == task.id).all()
    ]
    all_ids = [task.id, *step_ids]
    db.query(ScheduleBlock).filter(ScheduleBlock.task_id.in_(all_ids)).delete(
        synchronize_session=False
    )
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
    apply_task_scores(task, recompute=True)
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
    recompute = "deadline" in updates or "importance" in updates or "effort" in updates
    for field, value in updates.items():
        setattr(task, field, value)
    apply_task_scores(task, recompute=recompute)
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

    # H-12: Recompute priority on the parent task now that one of its steps is done.
    parent_task = db.query(Task).filter(Task.id == step.parent_task_id).first()
    if parent_task:
        apply_task_scores(parent_task, recompute=True)
        db.commit()
        run_schedule_for_user(user, db)

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

    # H-6: Interpret naive deadlines from the AI as local midnight in user's timezone,
    # then convert to naive UTC for storage (DB columns are naive DateTime).
    tz = ZoneInfo(user.timezone or "UTC")

    tasks_to_add = []
    all_titles = {p.title for p in parsed}

    for p in parsed:
        deadline: Optional[datetime] = None
        if p.deadline:
            raw_dl = datetime.fromisoformat(p.deadline)
            if raw_dl.tzinfo is None:
                # Treat as local time in user's timezone and convert to UTC.
                deadline = raw_dl.replace(tzinfo=tz).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
            else:
                deadline = raw_dl.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

        # H-7: Count how many of this task's declared dependencies are present in
        # this same brain dump (as a proxy for blocking-task weight).
        dep_count = sum(1 for dep in p.dependencies if dep in all_titles)
        if p.dependencies and not hasattr(Task, "dependency_count"):
            logger.debug(
                "Task '%s' has %d dependencies %s — Task model has no dependency_count column; "
                "dependency weight applied via priority scorer only.",
                p.title,
                len(p.dependencies),
                p.dependencies,
            )

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
        # Score with dependency count derived from this dump.
        task.priority_index = score_task(TaskInput(
            deadline=task.deadline,
            effort=task.effort or "medium",
            importance=task.importance or 3,
            dependency_count=dep_count,
        ))
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
            apply_task_scores(step, recompute=True)
            db.add(step)

    db.commit()
    run_schedule_for_user(user, db)

    result = []
    for task, _ in tasks_to_add:
        db.refresh(task)
        result.append(serialize_task(task, db))
    return result
