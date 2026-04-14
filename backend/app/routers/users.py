from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.users import UserResponse, UserUpdate
from app.services.schedule_runner import run_schedule_for_user

router = APIRouter(prefix="/api/users", tags=["users"])


def _serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        timezone=user.timezone or "UTC",
        study_start_hour=user.study_start_hour or 9,
        study_end_hour=user.study_end_hour or 22,
        uses_google_calendar=bool(user.uses_google_calendar),
        google_calendar_connected=bool(user.google_access_token),
    )


def _load_db_user(db: Session, user_id) -> User:
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.get("/me", response_model=UserResponse)
def get_me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _serialize_user(_load_db_user(db, user.id))


@router.patch("/me", response_model=UserResponse)
def patch_me(
    req: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db_user = _load_db_user(db, user.id)
    updates = req.model_dump(exclude_unset=True)
    should_rebuild_schedule = any(
        key in updates for key in ("study_start_hour", "study_end_hour", "uses_google_calendar")
    )

    for field, value in updates.items():
        setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)

    if should_rebuild_schedule:
        run_schedule_for_user(db_user, db)
        db.refresh(db_user)

    return _serialize_user(db_user)
