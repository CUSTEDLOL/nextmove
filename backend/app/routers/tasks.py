from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, Task
from app.schemas.tasks import (
    TaskCreate, TaskResponse, BrainDumpRequest, BrainDumpResponse, TodayResponse
)
from app.services.ai_parser import parse_brain_dump
from app.services.matrix_scorer import score_task, TaskInput

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _compute_score(task: Task) -> float:
    task_input = TaskInput(
        deadline=task.deadline,
        effort=task.effort or "medium",
        importance=task.importance or 3,
        dependency_count=0
    )
    return score_task(task_input)


@router.post("", response_model=TaskResponse)
def add_task(
    req: TaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    task = Task(**req.model_dump(), user_id=user.id, status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)
    task.priority_index = _compute_score(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/dump", response_model=BrainDumpResponse)
async def brain_dump(
    req: BrainDumpRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    parsed = await parse_brain_dump(req.text, user_timezone=user.timezone)
    created = []
    for p in parsed:
        deadline = datetime.fromisoformat(p.deadline) if p.deadline else None
        task = Task(
            user_id=user.id,
            title=p.title,
            raw_input=req.text,
            deadline=deadline,
            effort=p.effort,
            importance=p.importance,
            context=p.context,
            status="pending"
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task.priority_index = _compute_score(task)
        db.commit()
        db.refresh(task)
        created.append(task)
    return BrainDumpResponse(tasks=created)


@router.get("/today", response_model=TodayResponse)
def get_today(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    tasks = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.status.in_(["pending", "scheduled", "in_progress"]))
        .order_by(Task.priority_index.desc())
        .limit(4)
        .all()
    )
    primary = tasks[0] if tasks else None
    secondary = tasks[1:4] if len(tasks) > 1 else []
    return TodayResponse(primary=primary, secondary=secondary)


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return (
        db.query(Task)
        .filter(Task.user_id == user.id)
        .order_by(Task.priority_index.desc())
        .all()
    )


@router.post("/{task_id}/complete", response_model=TaskResponse)
def complete_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "completed"
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/reschedule", response_model=TaskResponse)
def reschedule_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "rescheduled"
    db.commit()
    db.refresh(task)
    return task
