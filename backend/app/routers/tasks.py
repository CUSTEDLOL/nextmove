from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, Task
from app.schemas.tasks import (
    TaskCreate, TaskResponse, BrainDumpRequest, BrainDumpResponse, TodayResponse, StepsDumpRequest
)
from app.services.ai_parser import parse_brain_dump
from app.services.matrix_scorer import score_task, TaskInput
from app.services.schedule_runner import run_schedule_for_user

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
        # Create steps if GPT detected sub-actions
        for step_title in p.steps:
            step = Task(
                user_id=user.id,
                title=step_title,
                parent_task_id=task.id,
                deadline=deadline,
                effort=p.effort,
                importance=p.importance,
                context=p.context,
                status="pending"
            )
            db.add(step)
        if p.steps:
            db.commit()
        created.append(task)
    run_schedule_for_user(user, db)
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


@router.post("/{task_id}/steps", response_model=list[TaskResponse])
def add_steps(
    task_id: str,
    req: StepsDumpRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    parent = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Task not found")

    # Parse steps: split by newlines or commas, clean up
    raw = req.text.replace("\n", ",")
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
            status="pending"
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        created.append(step)
    return created


@router.get("/{task_id}/steps", response_model=list[TaskResponse])
def get_steps(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    parent = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Task not found")
    return db.query(Task).filter(Task.parent_task_id == parent.id).order_by(Task.created_at).all()


@router.get("/{task_id}/why")
def why_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"explanation": _generate_why(task)}


def _generate_why(task: Task) -> str:
    reasons = []

    # Urgency — deadline proximity
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

    # Importance
    importance = task.importance or 3
    if importance >= 5:
        reasons.append("you marked it as critically important")
    elif importance >= 4:
        reasons.append("you rated it high importance")
    elif importance <= 2:
        reasons.append("it's lower importance but still needs doing")

    # Effort — explain energy match
    effort = task.effort or "medium"
    if effort == "high":
        reasons.append("it's a heavy task that needs focus — best tackled now while your energy is fresh")
    elif effort == "low":
        reasons.append("it's a quick win that'll clear your head")

    # Compose
    title = task.title
    reasons_str = ", and ".join(reasons) if len(reasons) <= 2 else ", ".join(reasons[:-1]) + ", and " + reasons[-1]
    return f"'{title}' is your top priority because {reasons_str}."


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
