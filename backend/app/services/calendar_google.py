from datetime import datetime
from pydantic import BaseModel
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from app.config import settings


class FreeSlotResult(BaseModel):
    start: datetime
    end: datetime


def get_credentials(access_token: str, refresh_token: str) -> Credentials:
    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


def get_google_service(access_token: str, refresh_token: str):
    creds = get_credentials(access_token, refresh_token)
    return build("calendar", "v3", credentials=creds)


def get_free_slots(
    service,
    calendar_id: str,
    date: datetime,
    study_start: int = 9,
    study_end: int = 22,
) -> list[FreeSlotResult]:
    """Return free time windows on `date` between study_start and study_end hours."""
    day_start = date.replace(hour=study_start, minute=0, second=0, microsecond=0)
    day_end = date.replace(hour=study_end, minute=0, second=0, microsecond=0)

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=day_start.isoformat() + "Z",
        timeMax=day_end.isoformat() + "Z",
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    events = events_result.get("items", [])

    busy = []
    for e in events:
        start_str = e["start"].get("dateTime", e["start"].get("date"))
        end_str = e["end"].get("dateTime", e["end"].get("date"))
        busy.append((
            datetime.fromisoformat(start_str.replace("Z", "")),
            datetime.fromisoformat(end_str.replace("Z", "")),
        ))

    free = []
    cursor = day_start
    for b_start, b_end in sorted(busy):
        if cursor < b_start:
            free.append(FreeSlotResult(start=cursor, end=b_start))
        cursor = max(cursor, b_end)
    if cursor < day_end:
        free.append(FreeSlotResult(start=cursor, end=day_end))

    return free


def create_google_event(
    service,
    title: str,
    start: datetime,
    end: datetime,
    calendar_id: str = "primary",
) -> str:
    """Create a calendar event and return its Google event ID."""
    body = {
        "summary": title,
        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "end":   {"dateTime": end.isoformat(),   "timeZone": "UTC"},
        "description": "Scheduled by NextMove",
    }
    created = service.events().insert(calendarId=calendar_id, body=body).execute()
    return created["id"]


def delete_google_event(service, event_id: str, calendar_id: str = "primary") -> None:
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
