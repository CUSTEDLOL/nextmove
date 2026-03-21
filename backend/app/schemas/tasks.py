from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class TaskCreate(BaseModel):
    title: str
    deadline: Optional[datetime] = None
    effort: str = "medium"
    importance: int = 3
    context: Optional[str] = "Study"


class TaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    deadline: Optional[datetime]
    effort: Optional[str]
    importance: Optional[int]
    context: Optional[str]
    priority_index: Optional[float]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class StepsDumpRequest(BaseModel):
    text: str


class BrainDumpRequest(BaseModel):
    text: str


class BrainDumpResponse(BaseModel):
    tasks: list[TaskResponse]


class TodayResponse(BaseModel):
    primary: Optional[TaskResponse]
    secondary: list[TaskResponse]
