from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
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
        await tg_app.bot.set_my_commands([
            BotCommand("menu",  "Show main menu"),
            BotCommand("today", "Today's priority task"),
            BotCommand("list",  "All pending tasks"),
            BotCommand("dump",  "Add new tasks (brain dump)"),
            BotCommand("done",  "Mark top task complete"),
            BotCommand("skip",  "Skip top task"),
            BotCommand("edit",  "Edit or delete a task"),
            BotCommand("web",   "Open NextMove in browser"),
        ])
    except Exception as exc:  # pragma: no cover - specific cases are covered in tests
        logger.warning("Telegram startup skipped: %s", exc)
        return None

    return tg_app


async def shutdown_telegram_bot(tg_app):
    if tg_app is None:
        return
    await tg_app.shutdown()


@asynccontextmanager
async def lifespan(app: FastAPI):
    tg_app = await initialize_telegram_bot()

    from app.services.pinger import ping_procrastinating_users
    scheduler.add_job(ping_procrastinating_users, "interval", hours=1, id="pinger")
    scheduler.start()

    yield

    scheduler.shutdown()
    await shutdown_telegram_bot(tg_app)


app = FastAPI(title="NextMove API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
