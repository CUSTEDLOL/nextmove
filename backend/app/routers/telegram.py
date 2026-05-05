from fastapi import APIRouter, Header, HTTPException, Request, Response
from telegram import Update
from app.config import settings

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
