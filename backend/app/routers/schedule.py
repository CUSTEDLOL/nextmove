from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, ScheduleBlock, Task

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


class ScheduleEntry(BaseModel):
    id: str
    task_id: str
    task_title: str
    effort: str | None
    start_time: datetime
    end_time: datetime
    entry_type: str   # "block" | "deadline"


@router.get("", response_model=list[ScheduleEntry])
def get_schedule(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=31)
    result: list[ScheduleEntry] = []

    # 1. Scheduled work blocks
    blocks = (
        db.query(ScheduleBlock)
        .filter(
            ScheduleBlock.user_id == user.id,
            ScheduleBlock.start_time >= start,
            ScheduleBlock.start_time < end,
        )
        .order_by(ScheduleBlock.start_time)
        .all()
    )
    for b in blocks:
        task = db.get(Task, b.task_id)
        result.append(ScheduleEntry(
            id=str(b.id),
            task_id=str(b.task_id),
            task_title=task.title if task else "Unknown",
            effort=task.effort if task else None,
            start_time=b.start_time,
            end_time=b.end_time,
            entry_type="block",
        ))

    # 2. Deadline events — tasks with a deadline, shown as a 30-min marker at deadline time
    deadline_tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user.id,
            Task.deadline.isnot(None),
            Task.deadline >= start,
            Task.deadline < end,
            Task.parent_task_id.is_(None),   # top-level only
        )
        .all()
    )
    for t in deadline_tasks:
        result.append(ScheduleEntry(
            id=f"deadline-{t.id}",
            task_id=str(t.id),
            task_title=f"⏰ Due: {t.title}",
            effort=t.effort,
            start_time=t.deadline,
            end_time=t.deadline + timedelta(minutes=30),
            entry_type="deadline",
        ))

    return sorted(result, key=lambda x: x.start_time)
