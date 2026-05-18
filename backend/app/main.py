from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import BotCommand
from app.routers import auth, tasks, telegram, calendar, users
from app.routers.schedule import router as schedule_router

scheduler = AsyncIOScheduler()
logger = logging.getLogger(__name__)


async def initialize_telegram_bot():
    from app.telegram.bot import get_application

    tg_app = get_application()
    try:
        await tg_app.initialize()
        await tg_app.start()
        await tg_app.bot.set_my_commands([
            BotCommand("menu",  "Show main menu"),
            BotCommand("today", "Today's priority task"),
            BotCommand("list",  "All pending tasks"),
            BotCommand("dump",  "Add new tasks (brain dump)"),
            BotCommand("done",  "Mark top task complete"),
            BotCommand("skip",  "Skip top task"),
            BotCommand("edit",  "Edit or delete a task"),
        ])
    except Exception as exc:  # pragma: no cover - specific cases are covered in tests
        logger.warning("Telegram startup skipped: %s", exc)
        return None

    return tg_app


async def shutdown_telegram_bot(tg_app):
    if tg_app is None:
        return
    await tg_app.stop()
    await tg_app.shutdown()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import settings
    import os
    _is_prod = os.getenv("ENV", "dev") != "dev"

    if settings.jwt_secret_key == "dev-secret-change-in-production":
        if _is_prod:
            raise RuntimeError("JWT_SECRET_KEY must be set to a secure value in production")
        else:
            logger.warning("Using default JWT secret — DO NOT use in production")

    if not settings.fernet_key.strip():
        if _is_prod:
            raise RuntimeError("FERNET_KEY must be set in production to encrypt OAuth tokens")
        else:
            logger.warning("FERNET_KEY not set — using dev key for token encryption. DO NOT use in production")

    from app.workers import notification_jobs

    tg_app = await initialize_telegram_bot()
    if tg_app is not None:
        notification_jobs.set_bot(tg_app.bot)

    from app.services.pinger import ping_procrastinating_users
    scheduler.add_job(ping_procrastinating_users, "interval", hours=1, id="pinger")
    scheduler.add_job(
        notification_jobs.morning_brief_job,
        CronTrigger(hour=8, minute=0),
        id="morning_brief",
    )
    scheduler.add_job(
        notification_jobs.evening_wrapup_job,
        CronTrigger(hour=21, minute=0),
        id="evening_wrapup",
    )
    scheduler.add_job(
        notification_jobs.weekly_summary_job,
        CronTrigger(day_of_week="sun", hour=19, minute=0),
        id="weekly_summary",
    )
    scheduler.start()

    yield

    scheduler.shutdown()
    await shutdown_telegram_bot(tg_app)


app = FastAPI(title="NextMove API", version="0.1.0", lifespan=lifespan)

import os as _os
_cors_origins = [o.strip() for o in _os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(telegram.router)
app.include_router(calendar.router)
app.include_router(users.router)
app.include_router(schedule_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
