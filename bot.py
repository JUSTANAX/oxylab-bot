import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from aiogram.exceptions import TelegramBadRequest
from config import BOT_TOKEN
from database import init_db
from handlers import start, admin

async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    @dp.error()
    async def error_handler(event: ErrorEvent):
        exc = event.exception
        if isinstance(exc, TelegramBadRequest) and (
            "query is too old" in str(exc) or
            "message is not modified" in str(exc)
        ):
            return  # Игнорируем просроченные / неизменённые сообщения
        logging.error("Unhandled error: %s", exc, exc_info=exc)

    dp.include_router(admin.router)
    dp.include_router(start.router)
    print("OxyLab Bot запущен ✅")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
