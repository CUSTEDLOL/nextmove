from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.models.task import Task
from app.schemas.tasks import (
    TaskCreate, TaskUpdate, TaskResponse, BrainDumpRequest, BrainDumpResponse,
    TodayResponse, StepsDumpRequest,
)
from app.services import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse)
def add_task(
    req: TaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return task_service.create_task(
        db, user,
        title=req.title,
        deadline=req.deadline,
        effort=req.effort,
        importance=req.importance,
        context=req.context,
    )


@router.post("/dump", response_model=BrainDumpResponse)
async def brain_dump(
    req: BrainDumpRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tasks = await task_service.process_brain_dump(db, user, req.text)
    return BrainDumpResponse(tasks=tasks)


@router.get("/today", response_model=TodayResponse)
def get_today(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return task_service.get_today(db, user)


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return task_service.list_tasks(db, user)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_service.serialize_task(task, db)


@router.patch("/{task_id}", response_model=TaskResponse)
def patch_task(
    task_id: str,
    req: TaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = task_service.update_task(db, user, task_id, req.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ok = task_service.delete_task(db, user, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}


@router.post("/{task_id}/complete", response_model=TaskResponse)
def complete_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = task_service.complete_task(db, user, task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.post("/{task_id}/steps", response_model=list[str])
def add_steps(
    task_id: str,
    req: StepsDumpRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    titles = task_service.add_steps(db, user, task_id, req.text)
    if titles is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return titles


@router.get("/{task_id}/steps", response_model=list[TaskResponse])
def get_steps(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = task_service.get_steps(db, user, task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    _, steps_data = result
    return steps_data


@router.get("/{task_id}/why")
def why_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"explanation": task_service.generate_why(task)}


@router.post("/{task_id}/reschedule", response_model=TaskResponse)
def reschedule_task(
    task_id: str,
    new_deadline: datetime,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = task_service.reschedule_task(db, user, task_id, new_deadline)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result
