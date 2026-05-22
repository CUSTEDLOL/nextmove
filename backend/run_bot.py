"""Run the Telegram bot in polling mode (for local development)."""
import asyncio
from app.telegram.bot import get_application


async def main():
    app = get_application()
    await app.initialize()
    await app.start()
    print("Bot polling started — Ctrl+C to stop")
    await app.updater.start_polling(drop_pending_updates=True)
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
