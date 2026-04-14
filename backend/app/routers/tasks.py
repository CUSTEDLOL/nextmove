from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, Task, ScheduleBlock
from app.schemas.tasks import (
    TaskCreate, TaskUpdate, TaskResponse, BrainDumpRequest, BrainDumpResponse, TodayResponse, StepsDumpRequest
)
from app.services.ai_parser import parse_brain_dump
from app.services.matrix_scorer import (
    TaskInput,
    normalized_importance_score,
    normalized_urgency_score,
    score_task,
    score_task_from_matrix,
)
from app.services.schedule_runner import run_schedule_for_user

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
ACTIVE_TASK_STATUSES = ["pending", "scheduled", "in_progress"]


def _compute_score(task: Task) -> float:
    task_input = TaskInput(
        deadline=task.deadline,
        effort=task.effort or "medium",
        importance=task.importance or 3,
        dependency_count=0
    )
    return score_task(task_input)


def _load_user_record(db: Session, user_id) -> User:
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


def _apply_task_scores(
    task: Task,
    *,
    recompute_urgency: bool = False,
    recompute_importance: bool = False,
):
    if recompute_urgency or task.urgency_score is None:
        task.urgency_score = normalized_urgency_score(task.deadline)
    if recompute_importance or task.importance_score is None:
        task.importance_score = normalized_importance_score(task.importance or 3)
    task.priority_index = score_task_from_matrix(
        task.urgency_score or 0,
        task.importance_score or 0,
        effort=task.effort or "medium",
    )


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


def _serialize_task(
    task: Task,
    db: Session,
    *,
    scheduled_today_ids: set | None = None,
    include_steps: bool = True,
) -> TaskResponse:
    if scheduled_today_ids is None:
        scheduled_today_ids = _scheduled_today_ids(db, task.user_id)

    steps: list[TaskResponse] = []
    if include_steps:
        child_steps = (
            db.query(Task)
            .filter(Task.parent_task_id == task.id)
            .order_by(Task.created_at)
            .all()
        )
        steps = [
            _serialize_task(step, db, scheduled_today_ids=scheduled_today_ids, include_steps=False)
            for step in child_steps
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


@router.post("", response_model=TaskResponse)
def add_task(
    req: TaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    task = Task(**req.model_dump(), user_id=user.id, status="pending")
    _apply_task_scores(task, recompute_urgency=True, recompute_importance=True)
    db.add(task)
    db.commit()
    db.refresh(task)
    run_schedule_for_user(_load_user_record(db, user.id), db)
    db.refresh(task)
    return _serialize_task(task, db)


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
            notes=None,
            status="pending"
        )
        _apply_task_scores(task, recompute_urgency=True, recompute_importance=True)
        db.add(task)
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
            _apply_task_scores(step, recompute_urgency=True, recompute_importance=True)
            db.add(step)
        if p.steps:
            db.commit()
        created.append(task)
    run_schedule_for_user(_load_user_record(db, user.id), db)
    for task in created:
        db.refresh(task)
    scheduled_today_ids = _scheduled_today_ids(db, user.id)
    return BrainDumpResponse(
        tasks=[_serialize_task(task, db, scheduled_today_ids=scheduled_today_ids) for task in created]
    )


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
            Task.status.in_(ACTIVE_TASK_STATUSES)
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


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    tasks = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.parent_task_id.is_(None))
        .order_by(Task.priority_index.desc())
        .all()
    )
    scheduled_today_ids = _scheduled_today_ids(db, user.id)
    return [
        _serialize_task(task, db, scheduled_today_ids=scheduled_today_ids)
        for task in tasks
    ]


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _serialize_task(task, db)


@router.patch("/{task_id}", response_model=TaskResponse)
def patch_task(
    task_id: str,
    req: TaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    updates = req.model_dump(exclude_unset=True)
    recompute_urgency = "deadline" in updates and "urgency_score" not in updates
    recompute_importance = "importance" in updates and "importance_score" not in updates

    for field, value in updates.items():
        setattr(task, field, value)

    _apply_task_scores(
        task,
        recompute_urgency=recompute_urgency,
        recompute_importance=recompute_importance,
    )
    db.commit()
    db.refresh(task)
    run_schedule_for_user(_load_user_record(db, user.id), db)
    db.refresh(task)
    return _serialize_task(task, db)


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    step_ids = [
        step_id
        for (step_id,) in db.query(Task.id).filter(Task.parent_task_id == task.id).all()
    ]
    task_ids = [task.id, *step_ids]
    db.query(ScheduleBlock).filter(ScheduleBlock.task_id.in_(task_ids)).delete(synchronize_session=False)
    if step_ids:
        db.query(Task).filter(Task.id.in_(step_ids)).delete(synchronize_session=False)
    db.delete(task)
    db.commit()
    run_schedule_for_user(_load_user_record(db, user.id), db)
    return {"ok": True}


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
    run_schedule_for_user(_load_user_record(db, user.id), db)
    db.refresh(task)
    return _serialize_task(task, db)


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
    return [_serialize_task(step, db, include_steps=False) for step in created]


@router.get("/{task_id}/steps", response_model=list[TaskResponse])
def get_steps(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    parent = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Task not found")
    steps = db.query(Task).filter(Task.parent_task_id == parent.id).order_by(Task.created_at).all()
    return [_serialize_task(step, db, include_steps=False) for step in steps]


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
    run_schedule_for_user(_load_user_record(db, user.id), db)
    db.refresh(task)
    return _serialize_task(task, db)
