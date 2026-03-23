from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.routers import auth, tasks, telegram, calendar
from app.routers.schedule import router as schedule_router

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Telegram bot once at startup — not per request
    from app.telegram.bot import get_application
    tg_app = get_application()
    await tg_app.initialize()

    # Register commands in Telegram's autocomplete menu
    from telegram import BotCommand
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

    from app.services.pinger import ping_procrastinating_users
    scheduler.add_job(ping_procrastinating_users, "interval", hours=1, id="pinger")
    scheduler.start()

    yield

    scheduler.shutdown()
    await tg_app.shutdown()


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
app.include_router(schedule_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
