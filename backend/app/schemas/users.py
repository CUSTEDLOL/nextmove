import uuid
from pydantic import BaseModel
from typing import Optional


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: Optional[str]
    timezone: str
    study_start_hour: int
    study_end_hour: int
    uses_google_calendar: bool
    google_calendar_connected: bool


class UserUpdate(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    study_start_hour: Optional[int] = None
    study_end_hour: Optional[int] = None
    uses_google_calendar: Optional[bool] = None
