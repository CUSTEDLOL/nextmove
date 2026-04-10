from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, CalendarEvent
from app.schemas.calendar import CalendarEventCreate, CalendarEventResponse, CalendarConnectionResponse
from app.services.schedule_runner import run_schedule_for_user

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _connection_state(user: User) -> CalendarConnectionResponse:
    return CalendarConnectionResponse(
        uses_google_calendar=bool(user.uses_google_calendar),
        google_calendar_connected=bool(user.google_access_token),
    )


@router.get("/status", response_model=CalendarConnectionResponse)
def calendar_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db_user = db.query(User).filter(User.id == user.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return _connection_state(db_user)


@router.post("/connect", response_model=CalendarConnectionResponse)
def connect_calendar(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db_user = db.query(User).filter(User.id == user.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    if not db_user.google_access_token:
        raise HTTPException(status_code=400, detail="Google account is not linked")
    db_user.uses_google_calendar = True
    db.commit()
    run_schedule_for_user(db_user, db)
    db.refresh(db_user)
    return _connection_state(db_user)


@router.post("/disconnect", response_model=CalendarConnectionResponse)
def disconnect_calendar(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db_user = db.query(User).filter(User.id == user.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db_user.uses_google_calendar = False
    db_user.google_access_token = None
    db_user.google_refresh_token = None
    db.commit()
    run_schedule_for_user(db_user, db)
    db.refresh(db_user)
    return _connection_state(db_user)


@router.get("/events", response_model=list[CalendarEventResponse])
def list_events(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    window_start = datetime.utcnow() - timedelta(days=30)
    window_end = datetime.utcnow() + timedelta(days=60)
    return (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.user_id == user.id,
            CalendarEvent.start_time >= window_start,
            CalendarEvent.start_time < window_end,
        )
        .order_by(CalendarEvent.start_time)
        .all()
    )


@router.post("/events", response_model=CalendarEventResponse)
def create_event(
    req: CalendarEventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    event = CalendarEvent(**req.model_dump(), user_id=user.id, source="manual")
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.patch("/events/{event_id}", response_model=CalendarEventResponse)
def update_event(
    event_id: str,
    req: CalendarEventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    event = db.query(CalendarEvent).filter(
        CalendarEvent.id == event_id, CalendarEvent.user_id == user.id
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    for k, v in req.model_dump().items():
        setattr(event, k, v)
    db.commit()
    db.refresh(event)
    return event


@router.delete("/events/{event_id}")
def delete_event(
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    event = db.query(CalendarEvent).filter(
        CalendarEvent.id == event_id, CalendarEvent.user_id == user.id
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(event)
    db.commit()
    return {"ok": True}
