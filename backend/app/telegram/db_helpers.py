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
                Task.parent_task_id.is_(None),
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
                Task.parent_task_id.is_(None),
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
            tasks_to_add.append((task, p))

        # Add all tasks, flush to get IDs (no commit yet)
        for task, p in tasks_to_add:
            db.add(task)
        db.flush()  # assigns IDs without committing

        # Score and add steps
        for task, p in tasks_to_add:
            task.priority_index = score_task(TaskInput(
                deadline=task.deadline,
                effort=task.effort or "medium",
                importance=task.importance or 3,
                dependency_count=0,
            ))
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
                db.add(step)

        db.commit()  # single atomic commit

        created = []
        for task, _ in tasks_to_add:
            db.refresh(task)
            created.append(TaskResponse.model_validate(task))
        return created
    except Exception:
        db.rollback()
        raise
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
        steps = []
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
            steps.append(step)
        db.commit()
        return [s.title for s in steps]
    except Exception:
        db.rollback()
        raise
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


def _generate_why(task: Task) -> str:
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

    title = task.title
    reasons_str = ", and ".join(reasons) if len(reasons) <= 2 else ", ".join(reasons[:-1]) + ", and " + reasons[-1]
    return f"'{title}' is your top priority because {reasons_str}."


async def why_task_for_chat_id(chat_id: int, task_id: str) -> Optional[str]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
        if not task:
            return None
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
                Task.parent_task_id.is_(None),
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
                Task.parent_task_id.is_(None),
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
