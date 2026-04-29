import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from aiogram.exceptions import TelegramBadRequest
from config import BOT_TOKEN
from database import init_db, get_users_with_alerts, update_alert_notified, get_panel as db_get_panel
from handlers import start, admin
from handlers import alerts as alerts_handler
from api.farmsync import get_stats as fs_get_stats
from api.accountsops import get_dashboard

async def check_all_alerts(bot: Bot):
    for user_id, panel, threshold, last_notified in get_users_with_alerts():
        if last_notified:
            try:
                last = datetime.fromisoformat(last_notified)
                if datetime.utcnow() - last < timedelta(minutes=30):
                    continue
            except Exception:
                pass

        panel_row = db_get_panel(user_id, panel)
        if not panel_row:
            continue

        try:
            if panel == "farmsync":
                ok, stats, _ = await fs_get_stats(panel_row[0])
                count = stats.get("accounts_active", 0) if ok else None
            else:
                ok, data, _ = await get_dashboard(panel_row[0])
                count = data.get("active_count", 0) if ok else None
        except Exception as e:
            logging.error("Alert API error user=%s panel=%s: %s", user_id, panel, e)
            continue

        if count is not None and count < threshold:
            panel_name = "🌾 FarmSync" if panel == "farmsync" else "👤 AccountsOps"
            try:
                await bot.send_message(
                    user_id,
                    f"⚠️ <b>Уведомление OxyLab</b>\n\n"
                    f"{panel_name}: активных аккаунтов — <b>{count}</b>\n"
                    f"Порог: {threshold}\n\n"
                    "Проверь ферму!",
                    parse_mode="HTML"
                )
                update_alert_notified(user_id, panel)
            except Exception as e:
                logging.error("Alert send error user=%s: %s", user_id, e)

async def alert_checker_loop(bot: Bot):
    while True:
        await asyncio.sleep(300)
        try:
            await check_all_alerts(bot)
        except Exception as e:
            logging.error("Alert checker error: %s", e, exc_info=e)

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
            return
        logging.error("Unhandled error: %s", exc, exc_info=exc)

    dp.include_router(admin.router)
    dp.include_router(alerts_handler.router)
    dp.include_router(start.router)
    asyncio.create_task(alert_checker_loop(bot))
    print("OxyLab Bot запущен ✅")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
