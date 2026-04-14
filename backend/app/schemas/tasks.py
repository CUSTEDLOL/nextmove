from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class TaskCreate(BaseModel):
    title: str
    deadline: Optional[datetime] = None
    effort: str = "medium"
    importance: int = 3
    context: Optional[str] = "Study"
    notes: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    deadline: Optional[datetime] = None
    effort: Optional[str] = None
    importance: Optional[int] = None
    context: Optional[str] = None
    notes: Optional[str] = None
    urgency_score: Optional[float] = None
    importance_score: Optional[float] = None
    status: Optional[str] = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    deadline: Optional[datetime]
    effort: Optional[str]
    importance: Optional[int]
    context: Optional[str]
    notes: Optional[str] = None
    urgency_score: Optional[float] = None
    importance_score: Optional[float] = None
    priority_index: Optional[float]
    status: str
    created_at: datetime
    scheduled_today: bool = False
    steps: list["TaskResponse"] = Field(default_factory=list)

    class Config:
        from_attributes = True

TaskResponse.model_rebuild()


class StepsDumpRequest(BaseModel):
    text: str


class BrainDumpRequest(BaseModel):
    text: str


class BrainDumpResponse(BaseModel):
    tasks: list[TaskResponse]


class TodayResponse(BaseModel):
    primary: Optional[TaskResponse]
    secondary: list[TaskResponse]
