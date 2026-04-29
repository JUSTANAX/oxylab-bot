from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import alerts_kb, alert_input_kb
from database import get_user, get_alert_threshold, set_alert_threshold, toggle_alert

router = Router()

class AlertState(StatesGroup):
    waiting_threshold = State()

def _get_thresholds(user_id: int, mode: str) -> dict:
    result = {}
    if mode in ("farmsync", "both"):
        row = get_alert_threshold(user_id, "farmsync")
        result["farmsync"] = {"threshold": row[0], "enabled": bool(row[1])} if row else None
    if mode in ("accountsops", "both"):
        row = get_alert_threshold(user_id, "accountsops")
        result["accountsops"] = {"threshold": row[0], "enabled": bool(row[1])} if row else None
    return result

@router.callback_query(lambda c: c.data == "alerts")
async def show_alerts(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    mode = user[0]
    thresholds = _get_thresholds(callback.from_user.id, mode)
    await callback.message.edit_text(
        "🔔 <b>Уведомления</b>\n\n"
        "Бот пришлёт сообщение если активных аккаунтов станет <b>меньше</b> заданного порога.\n\n"
        "Нажми на панель чтобы задать порог, на иконку — включить/выключить:",
        parse_mode="HTML",
        reply_markup=alerts_kb(mode, thresholds)
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("alert_set:"))
async def alert_set_start(callback: CallbackQuery, state: FSMContext):
    panel = callback.data.split(":")[1]
    names = {"farmsync": "FarmSync", "accountsops": "AccountsOps"}
    await state.set_state(AlertState.waiting_threshold)
    await state.update_data(
        alert_panel=panel,
        alert_chat_id=callback.message.chat.id,
        alert_msg_id=callback.message.message_id,
    )
    await callback.message.edit_text(
        f"🔔 <b>{names[panel]}</b>\n\n"
        "Введи пороговое значение активных аккаунтов.\n"
        "Пример: <code>100</code>",
        parse_mode="HTML",
        reply_markup=alert_input_kb()
    )
    await callback.answer()

@router.message(AlertState.waiting_threshold)
async def alert_set_receive(message: Message, state: FSMContext):
    await message.delete()
    text = message.text.strip()
    user_id = message.from_user.id
    data = await state.get_data()
    chat_id = data.get("alert_chat_id")
    msg_id  = data.get("alert_msg_id")
    panel   = data["alert_panel"]
    names   = {"farmsync": "FarmSync", "accountsops": "AccountsOps"}

    async def edit(txt, kb):
        try:
            await message.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text=txt, parse_mode="HTML", reply_markup=kb
            )
        except Exception:
            await message.answer(txt, parse_mode="HTML", reply_markup=kb)

    if not text.isdigit() or int(text) <= 0:
        await edit("❌ Введи целое положительное число.\nПример: <code>100</code>", alert_input_kb())
        return

    threshold = int(text)
    set_alert_threshold(user_id, panel, threshold)
    await state.clear()

    user = get_user(user_id)
    mode = user[0]
    thresholds = _get_thresholds(user_id, mode)
    await edit(
        f"✅ Порог для <b>{names[panel]}</b> установлен: <b>< {threshold}</b>\n\n"
        "🔔 <b>Уведомления</b>\n\n"
        "Нажми на панель чтобы задать порог, на иконку — включить/выключить:",
        alerts_kb(mode, thresholds)
    )

@router.callback_query(lambda c: c.data.startswith("alert_toggle:"))
async def alert_toggle_handler(callback: CallbackQuery):
    panel = callback.data.split(":")[1]
    user_id = callback.from_user.id
    row = get_alert_threshold(user_id, panel)
    if not row or not row[0]:
        await callback.answer("Сначала задай порог", show_alert=True)
        return
    toggle_alert(user_id, panel)
    user = get_user(user_id)
    mode = user[0]
    thresholds = _get_thresholds(user_id, mode)
    await callback.message.edit_reply_markup(reply_markup=alerts_kb(mode, thresholds))
    await callback.answer()
