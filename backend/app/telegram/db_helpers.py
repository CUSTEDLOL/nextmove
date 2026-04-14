"""
Bridges Telegram chat_id → database user_id.
All bot handlers call these instead of touching the DB directly.
Business logic lives in services/task_service.py — this is just the DB bridge.
"""
from datetime import datetime
from typing import Optional
import uuid

from app.database import SessionLocal
from app.models.user import User
from app.models.task import Task
from app.schemas.tasks import TaskResponse
from app.services import task_service


def _get_user(db, chat_id: int) -> Optional[User]:
    return db.query(User).filter(User.telegram_chat_id == chat_id).first()


# ---------------------------------------------------------------------------
# Today / task reads
# ---------------------------------------------------------------------------

async def get_today_for_chat_id(chat_id: int):
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        today = task_service.get_today(db, user)
        return today.primary, today.secondary
    finally:
        db.close()


async def list_tasks_for_chat_id(chat_id: int) -> Optional[list]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        return task_service.list_tasks(db, user)
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
        return task_service.serialize_task(task, db, include_steps=False)
    finally:
        db.close()


async def get_steps_for_chat_id(chat_id: int, task_id: str) -> Optional[tuple]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        return task_service.get_steps(db, user, task_id)
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
        return task_service.generate_why(task)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task writes
# ---------------------------------------------------------------------------

async def complete_task_for_chat_id(chat_id: int, task_id: str) -> bool:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return False
        return task_service.complete_task(db, user, task_id) is not None
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
        return task_service.complete_task(db, user, str(task.id))
    finally:
        db.close()


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


async def skip_top_task_for_chat_id(chat_id: int) -> Optional[TaskResponse]:
    """Delete the highest-priority pending task. Returns the deleted task's info or None."""
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
        # Serialize before deleting
        task_data = task_service.serialize_task(task, db, include_steps=False)
        task_service.delete_task(db, user, str(task.id))
        return task_data
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


async def complete_step_for_chat_id(chat_id: int, step_id: str) -> bool:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return False
        return task_service.complete_step(db, user, step_id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Brain dump
# ---------------------------------------------------------------------------

async def process_dump_for_chat_id(chat_id: int, text: str) -> Optional[list]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        return await task_service.process_brain_dump(db, user, text)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def add_single_task_for_chat_id(chat_id: int, text: str) -> Optional[TaskResponse]:
    """Parse a single-task instruction and create it. Returns the created task or None."""
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        tasks = await task_service.process_brain_dump(db, user, text)
        return tasks[0] if tasks else None
    finally:
        db.close()


async def add_steps_for_chat_id(chat_id: int, task_id: str, text: str) -> Optional[list]:
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return None
        return task_service.add_steps(db, user, task_id, text)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pending state helpers (not delegated to task_service — pure user-state)
# ---------------------------------------------------------------------------

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


async def clear_pending_state(chat_id: int) -> None:
    await clear_pending_steps(chat_id)
    await clear_pending_edit(chat_id)


async def apply_task_edit(chat_id: int, task_id: str, edit: dict) -> bool:
    """Apply a structured edit to a task. edit = {field: 'deadline'|'title'|'delete', value: ...}"""
    db = SessionLocal()
    try:
        user = _get_user(db, chat_id)
        if not user:
            return False
        field = edit.get("field")
        if field == "delete":
            return task_service.delete_task(db, user, task_id)
        updates = {}
        if field == "title":
            updates["title"] = edit["value"]
        elif field == "deadline":
            updates["deadline"] = datetime.fromisoformat(edit["value"]) if edit.get("value") else None
        else:
            return False
        return task_service.update_task(db, user, task_id, updates) is not None
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
