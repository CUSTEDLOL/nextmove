import uuid
from pydantic import BaseModel, model_validator
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

    @model_validator(mode="after")
    def validate_study_hours(self) -> "UserUpdate":
        start = self.study_start_hour
        end = self.study_end_hour

        if start is not None and not (0 <= start <= 23):
            raise ValueError("study_start_hour must be between 0 and 23")
        if end is not None and not (0 <= end <= 23):
            raise ValueError("study_end_hour must be between 0 and 23")
        if start is not None and end is not None and start >= end:
            raise ValueError("study_start_hour must be less than study_end_hour")
        return self
