import time
import json
import asyncio
import logging
from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import (
    get_rotation_tasks, get_rotation_task, create_rotation_task,
    delete_rotation_task, toggle_rotation_task, get_rotation_logs,
    get_panel as db_get_panel,
)
from api.farmsync import get_folder_groups, get_configs, get_accounts

router = Router()

class RotationSetup(StatesGroup):
    select_folder_a     = State()
    select_folder_b     = State()
    select_farming_cfg  = State()
    select_standing_cfg = State()
    select_interval     = State()

# ── helpers ───────────────────────────────────────────────────────────────────

def _time_left(next_run: int) -> str:
    secs = next_run - int(time.time())
    if secs <= 0:
        return "скоро"
    h, rem = divmod(secs, 3600)
    m = rem // 60
    return f"{h}ч {m}м" if h else f"{m}м"

async def _load_wizard_data(api_key: str) -> tuple[list, list]:
    (ok_f, folder_groups, _), (ok_a, accounts, _), (ok_c, configs, _) = await asyncio.gather(
        get_folder_groups(api_key),
        get_accounts(api_key),
        get_configs(api_key),
    )
    counts: dict[str, int] = {}
    for a in (accounts or []):
        fid = a.get("folder_id")
        if fid:
            counts[fid] = counts.get(fid, 0) + 1

    names: dict[str, str] = {}
    if ok_f and isinstance(folder_groups, list):
        for fg in folder_groups:
            if isinstance(fg, dict):
                fid  = fg.get("id") or fg.get("folder_id")
                name = fg.get("name") or fg.get("group_name")
                if fid and name:
                    names[fid] = name

    folders = sorted(
        [{"id": fid, "name": names.get(fid, fid[:8] + "…"), "count": cnt}
         for fid, cnt in counts.items()],
        key=lambda x: -x["count"],
    )
    cfg_list = []
    if ok_c and isinstance(configs, list):
        cfg_list = [{"id": c["id"], "name": c.get("name", c["id"][:8])} for c in configs if c.get("id")]

    return folders, cfg_list

def _folder_kb(folders: list, prefix: str, exclude_id: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    for i, f in enumerate(folders[:15]):
        if f["id"] == exclude_id:
            continue
        rows.append([InlineKeyboardButton(
            text=f"📁 {f['name']}  ({f['count']} акк.)",
            callback_data=f"{prefix}:{i}",
        )])
    rows.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="autopilot")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _config_kb(configs: list, prefix: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"⚙️ {c['name']}", callback_data=f"{prefix}:{i}")]
            for i, c in enumerate(configs[:15])]
    rows.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="autopilot")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _interval_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕐 Каждые 12 часов", callback_data="ap_iv:12")],
        [InlineKeyboardButton(text="🕐 Каждые 16 часов", callback_data="ap_iv:16")],
        [InlineKeyboardButton(text="🕐 Каждые 24 часа",  callback_data="ap_iv:24")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="autopilot")],
    ])

def _progress(data: dict) -> str:
    lines = []
    if data.get("folder_a"):
        lines.append(f"✅ Фарм: {data['folder_a']['name']} ({data['folder_a']['count']} акк.)")
    if data.get("folder_b"):
        lines.append(f"✅ Стойка: {data['folder_b']['name']} ({data['folder_b']['count']} акк.)")
    if data.get("farming_cfg"):
        lines.append(f"✅ Конфиг фарма: {data['farming_cfg']['name']}")
    if data.get("standing_cfg"):
        lines.append(f"✅ Конфиг стойки: {data['standing_cfg']['name']}")
    return ("\n".join(lines) + "\n\n") if lines else ""

# ── menu ──────────────────────────────────────────────────────────────────────

async def _show_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    tasks = get_rotation_tasks(callback.from_user.id)
    rows = []
    for t in tasks:
        icon = "✅" if t["enabled"] else "❌"
        rows.append([InlineKeyboardButton(
            text=f"{icon} Задача #{t['id']} — каждые {t['interval_hours']}ч",
            callback_data=f"autopilot:task:{t['id']}",
        )])
    rows.append([InlineKeyboardButton(text="➕ Создать задачу", callback_data="autopilot:create")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_stats")])

    if tasks:
        active = sum(1 for t in tasks if t["enabled"])
        body = f"Активных: {active} из {len(tasks)}"
    else:
        body = "Задач пока нет. Создай первую ротацию!"

    await callback.message.edit_text(
        f"🤖 <b>Автопилот</b>\n\n{body}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )

@router.callback_query(lambda c: c.data == "autopilot")
async def open_autopilot(callback: CallbackQuery, state: FSMContext):
    await _show_menu(callback, state)
    await callback.answer()

# ── task detail ───────────────────────────────────────────────────────────────

async def _show_task(callback: CallbackQuery, task_id: int):
    task = get_rotation_task(task_id)
    if not task or task["user_id"] != callback.from_user.id:
        await callback.answer("Задача не найдена", show_alert=True)
        return

    next_str = _time_left(task["next_run"]) if task.get("next_run") else "—"

    logs = get_rotation_logs(task_id, limit=1)
    log_text = ""
    if logs:
        run_at, switched, skipped_raw = logs[0]
        skipped = json.loads(skipped_raw or "[]")
        log_text = (
            f"\n\n📊 <b>Последняя ротация:</b> {run_at[:16]}\n"
            f"  Переключено: {switched}, пропущено: {len(skipped)}"
        )

    toggle_text = "✅ Включена" if task["enabled"] else "❌ Выключена"
    text = (
        f"🤖 Автопилот  ›  🔁 <b>Задача #{task_id}</b>\n\n"
        f"📁 Фарм: {task['folder_a_name']}\n"
        f"📁 Стойка: {task['folder_b_name']}\n"
        f"⚙️ Конфиг фарма: {task['farming_config_name']}\n"
        f"⚙️ Конфиг стойки: {task['standing_config_name']}\n"
        f"🕐 Каждые {task['interval_hours']} часов\n\n"
        f"⏱ Следующая ротация: через {next_str}"
        f"{log_text}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=toggle_text,   callback_data=f"autopilot:toggle:{task_id}"),
            InlineKeyboardButton(text="🗑 Удалить",  callback_data=f"autopilot:del:{task_id}"),
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="autopilot")],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(lambda c: c.data.startswith("autopilot:task:"))
async def open_task(callback: CallbackQuery):
    await _show_task(callback, int(callback.data.split(":")[2]))
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("autopilot:toggle:"))
async def toggle_task(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[2])
    task = get_rotation_task(task_id)
    if not task or task["user_id"] != callback.from_user.id:
        await callback.answer()
        return
    enabled = toggle_rotation_task(task_id)
    await callback.answer("✅ Включена" if enabled else "❌ Выключена")
    await _show_task(callback, task_id)

@router.callback_query(lambda c: c.data.startswith("autopilot:del:"))
async def delete_confirm(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[2])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"autopilot:del_ok:{task_id}")],
        [InlineKeyboardButton(text="🔙 Отмена",      callback_data=f"autopilot:task:{task_id}")],
    ])
    await callback.message.edit_text(
        f"🤖 Автопилот  ›  🔁 Задача #{task_id}  ›  🗑 <b>Удалить</b>\n\n"
        "Удалить задачу ротации? Действие необратимо.",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("autopilot:del_ok:"))
async def delete_task(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[2])
    task = get_rotation_task(task_id)
    if task and task["user_id"] == callback.from_user.id:
        delete_rotation_task(task_id)
    await callback.answer("Удалено")
    await _show_menu(callback, state)

# ── wizard: создание задачи ───────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "autopilot:create")
async def wizard_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    panel = db_get_panel(user_id, "farmsync")
    if not panel:
        await callback.answer("FarmSync не подключён", show_alert=True)
        return

    await callback.message.edit_text("🔄 Загружаю данные...", parse_mode="HTML")
    folders, configs = await _load_wizard_data(panel[0])

    if not folders:
        await callback.message.edit_text(
            "🤖 Автопилот  ›  ➕ <b>Новая задача</b>\n\n"
            "❌ Нет аккаунтов в папках. Сначала распредели аккаунты по папкам в FarmSync.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="autopilot")]
            ]),
        )
        await callback.answer()
        return

    if not configs:
        await callback.message.edit_text(
            "🤖 Автопилот  ›  ➕ <b>Новая задача</b>\n\n"
            "❌ Нет конфигов. Создай хотя бы два конфига в FarmSync.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="autopilot")]
            ]),
        )
        await callback.answer()
        return

    await state.set_state(RotationSetup.select_folder_a)
    await state.update_data(folders=folders, configs=configs)

    await callback.message.edit_text(
        "🤖 Автопилот  ›  ➕ <b>Новая задача</b>\n\n"
        "📁 Шаг 1 из 5: выбери папку с <b>фарм-аккаунтами</b>",
        parse_mode="HTML",
        reply_markup=_folder_kb(folders, "ap_fa"),
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("ap_fa:"), RotationSetup.select_folder_a)
async def wizard_folder_a(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    folders = data["folders"]
    if idx >= len(folders):
        await callback.answer()
        return
    folder_a = folders[idx]
    await state.update_data(folder_a=folder_a)
    await state.set_state(RotationSetup.select_folder_b)

    await callback.message.edit_text(
        "🤖 Автопилот  ›  ➕ <b>Новая задача</b>\n\n"
        f"{_progress(await state.get_data())}"
        "📁 Шаг 2 из 5: выбери папку со <b>стоячими аккаунтами</b>",
        parse_mode="HTML",
        reply_markup=_folder_kb(folders, "ap_fb", exclude_id=folder_a["id"]),
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("ap_fb:"), RotationSetup.select_folder_b)
async def wizard_folder_b(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    folders, folder_a = data["folders"], data["folder_a"]
    # find by original index (may shift due to exclude)
    available = [f for f in folders if f["id"] != folder_a["id"]]
    if idx >= len(available):
        await callback.answer()
        return
    folder_b = available[idx]
    await state.update_data(folder_b=folder_b)
    await state.set_state(RotationSetup.select_farming_cfg)

    await callback.message.edit_text(
        "🤖 Автопилот  ›  ➕ <b>Новая задача</b>\n\n"
        f"{_progress(await state.get_data())}"
        "⚙️ Шаг 3 из 5: выбери <b>конфиг фарма</b>\n"
        "<i>Будет применён к фарм-папке после ротации</i>",
        parse_mode="HTML",
        reply_markup=_config_kb(data["configs"], "ap_cf"),
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("ap_cf:"), RotationSetup.select_farming_cfg)
async def wizard_farming_cfg(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    configs = data["configs"]
    if idx >= len(configs):
        await callback.answer()
        return
    await state.update_data(farming_cfg=configs[idx])
    await state.set_state(RotationSetup.select_standing_cfg)

    await callback.message.edit_text(
        "🤖 Автопилот  ›  ➕ <b>Новая задача</b>\n\n"
        f"{_progress(await state.get_data())}"
        "⚙️ Шаг 4 из 5: выбери <b>конфиг стойки</b>\n"
        "<i>Будет применён к стоячей папке после ротации</i>",
        parse_mode="HTML",
        reply_markup=_config_kb(configs, "ap_cs"),
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("ap_cs:"), RotationSetup.select_standing_cfg)
async def wizard_standing_cfg(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    configs = data["configs"]
    if idx >= len(configs):
        await callback.answer()
        return
    await state.update_data(standing_cfg=configs[idx])
    await state.set_state(RotationSetup.select_interval)

    await callback.message.edit_text(
        "🤖 Автопилот  ›  ➕ <b>Новая задача</b>\n\n"
        f"{_progress(await state.get_data())}"
        "🕐 Шаг 5 из 5: выбери <b>интервал ротации</b>",
        parse_mode="HTML",
        reply_markup=_interval_kb(),
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("ap_iv:"), RotationSetup.select_interval)
async def wizard_interval(callback: CallbackQuery, state: FSMContext):
    hours = int(callback.data.split(":")[1])
    data  = await state.get_data()

    folder_a    = data["folder_a"]
    folder_b    = data["folder_b"]
    farming_cfg = data["farming_cfg"]
    standing_cfg = data["standing_cfg"]

    task_id = create_rotation_task(
        user_id             = callback.from_user.id,
        folder_a_id         = folder_a["id"],
        folder_a_name       = folder_a["name"],
        folder_b_id         = folder_b["id"],
        folder_b_name       = folder_b["name"],
        farming_config      = farming_cfg["id"],
        farming_config_name = farming_cfg["name"],
        standing_config     = standing_cfg["id"],
        standing_config_name= standing_cfg["name"],
        interval_hours      = hours,
    )
    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 К автопилоту", callback_data="autopilot")]
    ])
    await callback.message.edit_text(
        f"✅ <b>Задача #{task_id} создана!</b>\n\n"
        f"📁 Фарм: {folder_a['name']} ({folder_a['count']} акк.)\n"
        f"📁 Стойка: {folder_b['name']} ({folder_b['count']} акк.)\n"
        f"⚙️ Конфиг фарма: {farming_cfg['name']}\n"
        f"⚙️ Конфиг стойки: {standing_cfg['name']}\n"
        f"🕐 Каждые {hours} часов\n\n"
        f"⏱ Первая ротация через {hours}ч",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()
