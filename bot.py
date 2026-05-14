import asyncio
import logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s")
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from aiogram.exceptions import TelegramBadRequest
from config import BOT_TOKEN, ADMIN_ID
import debug_notify
from database import (
    init_db, get_users_with_alerts, update_alert_notified,
    get_panel as db_get_panel,
    get_due_rotation_tasks, advance_rotation_next_run, complete_rotation,
)
from handlers import start, admin
from handlers import alerts as alerts_handler
from handlers import autopilot as autopilot_handler
from api.farmsync import get_stats as fs_get_stats, get_accounts, bulk_update_accounts
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

async def execute_rotation(bot: Bot, task: dict):
    user_id = task["user_id"]
    panel   = db_get_panel(user_id, "farmsync")
    if not panel:
        return

    api_key = panel[0]
    ok, accounts, err = await get_accounts(api_key)
    if not ok:
        await bot.send_message(user_id, f"❌ <b>Ротация #{task['id']} не удалась</b>\n\nОшибка API: {err}", parse_mode="HTML")
        return

    folder_a_id = task["folder_a_id"]
    folder_b_id = task["folder_b_id"]
    folder_a    = [a for a in accounts if a.get("folder_id") == folder_a_id]
    folder_b    = [a for a in accounts if a.get("folder_id") == folder_b_id]

    a_alive = [a for a in folder_a if not a.get("dead_cookie")]
    b_alive = [a for a in folder_b if not a.get("dead_cookie")]
    skipped = [a["username"] for a in folder_a + folder_b if a.get("dead_cookie")]

    all_alive = a_alive + b_alive
    if not all_alive:
        await bot.send_message(user_id, f"⚠️ <b>Ротация #{task['id']} пропущена</b>\n\nНет живых аккаунтов.", parse_mode="HTML")
        return

    if task["state"] == "a_farming":
        cfg_for_a, cfg_for_b, new_state = task["standing_config"], task["farming_config"], "b_farming"
    else:
        cfg_for_a, cfg_for_b, new_state = task["farming_config"], task["standing_config"], "a_farming"

    config_updates = (
        [{"username": a["username"], "config_id": cfg_for_a} for a in a_alive] +
        [{"username": a["username"], "config_id": cfg_for_b} for a in b_alive]
    )
    ok, _, err = await bulk_update_accounts(api_key, config_updates)
    if not ok:
        await bot.send_message(user_id, f"❌ <b>Ротация #{task['id']} не удалась</b>\n\nОшибка смены конфигов: {err}", parse_mode="HTML")
        return

    await bulk_update_accounts(api_key, [{"username": a["username"], "enabled": False} for a in all_alive])
    await asyncio.sleep(150)
    await bulk_update_accounts(api_key, [{"username": a["username"], "enabled": True} for a in all_alive])

    complete_rotation(task["id"], new_state, len(all_alive), skipped)

    skip_text = ""
    if skipped:
        skip_text = f"\n\n⚠️ <b>Пропущено:</b> {len(skipped)}\n" + "\n".join(f"  • {n} — мёртвый куки" for n in skipped[:10])

    next_run = task["interval_hours"]
    await bot.send_message(
        user_id,
        f"🔁 <b>Ротация #{task['id']} завершена</b>\n\n"
        f"✅ Переключено: {len(all_alive)} аккаунтов"
        f"{skip_text}\n\n"
        f"⏱ Следующая: через {next_run}ч",
        parse_mode="HTML",
    )

async def check_all_rotations(bot: Bot):
    for task in get_due_rotation_tasks():
        advance_rotation_next_run(task["id"], task["interval_hours"])
        asyncio.create_task(execute_rotation(bot, task))

async def rotation_checker_loop(bot: Bot):
    while True:
        await asyncio.sleep(60)
        try:
            await check_all_rotations(bot)
        except Exception as e:
            logging.error("Rotation checker error: %s", e, exc_info=e)

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
    debug_notify.setup(bot, ADMIN_ID)
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
    dp.include_router(autopilot_handler.router)
    dp.include_router(start.router)
    asyncio.create_task(alert_checker_loop(bot))
    asyncio.create_task(rotation_checker_loop(bot))
    print("OxyLab Bot запущен ✅")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
