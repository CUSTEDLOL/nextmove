from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from telegram import Update

from app.config import settings
from app.dependencies import get_current_user
from app.models.user import User
from app.telegram.link_service import store_web_link_token

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    from app.telegram.bot import get_application
    body = await request.json()
    application = get_application()
    update = Update.de_json(body, application.bot)
    await application.process_update(update)
    return Response(status_code=200)


@router.post("/link-token")
def create_link_token(current_user: User = Depends(get_current_user)):
    token = store_web_link_token(str(current_user.id))
    return {"url": f"https://t.me/{settings.telegram_bot_username}?start={token}"}


@router.get("/link-status")
def link_status(current_user: User = Depends(get_current_user)):
    return {"linked": current_user.telegram_chat_id is not None}
