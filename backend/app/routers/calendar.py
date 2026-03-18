from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, CalendarEvent
from app.schemas.calendar import CalendarEventCreate, CalendarEventResponse

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/events", response_model=list[CalendarEventResponse])
def list_events(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return (
        db.query(CalendarEvent)
        .filter(CalendarEvent.user_id == user.id)
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
