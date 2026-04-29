import aiohttp
from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_conn
from keyboards import main_menu_kb, farmsync_panel_kb

FARMSYNC_URL = "https://api.farmsync.cloud"

router = Router()

class FSConnect(StatesGroup):
    waiting_api_key = State()

# ─── Подключение ──────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "connect_farmsync")
async def ask_api_key(callback: CallbackQuery, state: FSMContext):
    # Проверяем — вдруг уже подключена
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT api_key FROM panels WHERE user_id = ? AND type = 'farmsync'",
            (callback.from_user.id,)
        ).fetchone()

    if existing:
        await callback.answer("FarmSync уже подключён. Сначала отключи текущую панель.", show_alert=True)
        return

    await state.set_state(FSConnect.waiting_api_key)
    await callback.message.edit_text(
        "🔑 <b>Подключение FarmSync</b>\n\n"
        "Отправь свой API ключ.\n"
        "Выглядит так: <code>fs_live_xxxxxxxxxxxxxxxxxxxx</code>\n\n"
        "⚠️ Ключ хранится только на сервере бота.",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(FSConnect.waiting_api_key)
async def receive_api_key(message: Message, state: FSMContext):
    api_key = message.text.strip()
    await message.delete()

    msg = await message.answer("🔄 Проверяю ключ...")
    valid, device_count, error = await validate_farmsync_key(api_key)

    if not valid:
        await msg.edit_text(
            f"❌ <b>Ошибка подключения</b>\n\n{error}\n\nПопробуй ввести ключ ещё раз:",
            parse_mode="HTML"
        )
        return

    user_id = message.from_user.id
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO panels (user_id, type, api_key) VALUES (?, 'farmsync', ?)",
            (user_id, api_key)
        )
        user = conn.execute("SELECT mode FROM users WHERE user_id = ?", (user_id,)).fetchone()

    await state.clear()
    await msg.edit_text(
        f"🎉 <b>FarmSync подключён!</b>\n\n"
        f"Устройств найдено: <b>{device_count}</b>",
        parse_mode="HTML",
        reply_markup=main_menu_kb(user[0])
    )

# ─── Меню панели ──────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "open_farmsync")
async def panel_menu(callback: CallbackQuery):
    with get_conn() as conn:
        panel = conn.execute(
            "SELECT api_key FROM panels WHERE user_id = ? AND type = 'farmsync'",
            (callback.from_user.id,)
        ).fetchone()

    if not panel:
        await callback.answer("FarmSync не подключён", show_alert=True)
        return

    _, device_count, _ = await validate_farmsync_key(panel[0])

    await callback.message.edit_text(
        f"🌾 <b>FarmSync</b>\n\n"
        f"Устройств онлайн: <b>{device_count}</b>",
        parse_mode="HTML",
        reply_markup=farmsync_panel_kb()
    )
    await callback.answer()

# ─── Отключение панели ────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "fs_disconnect")
async def disconnect(callback: CallbackQuery):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM panels WHERE user_id = ? AND type = 'farmsync'",
            (callback.from_user.id,)
        )
        conn.execute(
            "DELETE FROM user_settings WHERE user_id = ? AND panel_type = 'farmsync'",
            (callback.from_user.id,)
        )
        user = conn.execute(
            "SELECT mode FROM users WHERE user_id = ?", (callback.from_user.id,)
        ).fetchone()

    await callback.message.edit_text(
        "🔌 <b>FarmSync отключён.</b>\n\nМожешь подключить заново в любой момент.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(user[0])
    )
    await callback.answer()

# ─── Валидация ────────────────────────────────────────────────────────────────

async def validate_farmsync_key(api_key: str) -> tuple[bool, int, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{FARMSYNC_URL}/api/devices/",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 401:
                    return False, 0, "Неверный API ключ."
                if resp.status == 403:
                    return False, 0, "Доступ запрещён. Проверь права ключа."
                if resp.status != 200:
                    return False, 0, f"Ошибка сервера FarmSync (код {resp.status})."
                devices = await resp.json()
                return True, len(devices), ""
    except aiohttp.ClientConnectorError:
        return False, 0, "Не удалось подключиться к FarmSync."
    except Exception as e:
        return False, 0, f"Неизвестная ошибка: {e}"
