"""
Bridges Telegram chat_id → database user_id.
All bot handlers call these instead of touching the DB directly.
"""
from typing import Optional
from app.database import SessionLocal
from app.models import User, Task
from app.schemas.tasks import TaskResponse, TodayResponse
from app.services.ai_parser import parse_brain_dump
from app.services.matrix_scorer import score_task, TaskInput
from datetime import datetime


def _get_user_by_chat_id(chat_id: int):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.telegram_chat_id == chat_id).first()
    finally:
        db.close()


async def get_today_for_chat_id(chat_id: int) -> Optional[tuple]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        if not user:
            return None
        tasks = (
            db.query(Task)
            .filter(Task.user_id == user.id, Task.status.in_(["pending", "scheduled", "in_progress"]))
            .order_by(Task.priority_index.desc())
            .limit(4)
            .all()
        )
        primary = TaskResponse.model_validate(tasks[0]) if tasks else None
        secondary = [TaskResponse.model_validate(t) for t in tasks[1:4]]
        return primary, secondary
    finally:
        db.close()


async def process_dump_for_chat_id(chat_id: int, text: str) -> Optional[list]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
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
                status="pending"
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            task.priority_index = score_task(TaskInput(
                deadline=task.deadline,
                effort=task.effort or "medium",
                importance=task.importance or 3,
                dependency_count=0
            ))
            db.commit()
            db.refresh(task)
            created.append(TaskResponse.model_validate(task))
        return created
    finally:
        db.close()


async def complete_task_for_chat_id(chat_id: int, task_id: str) -> bool:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
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


async def reschedule_task_for_chat_id(chat_id: int, task_id: str) -> bool:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
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
