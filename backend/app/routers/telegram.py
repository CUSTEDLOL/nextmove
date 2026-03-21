from fastapi import APIRouter, Request, Response
from telegram import Update

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(request: Request):
    from app.telegram.bot import get_application
    body = await request.json()
    application = get_application()
    update = Update.de_json(body, application.bot)
    await application.process_update(update)
    return Response(status_code=200)
