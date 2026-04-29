from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from keyboards import panel_choice_kb, stats_kb, api_keys_kb, cancel_kb, back_kb, customize_kb, farmsync_customize_kb, accounts_customize_kb, pets_customize_kb, pets_stats_customize_kb, fs_resources_customize_kb, ao_customize_kb, ao_accounts_customize_kb, ao_resources_customize_kb, ao_pets_customize_kb, ao_pets_stats_customize_kb, PET_STAT_PERIODS, AO_PET_STAT_PERIODS, AO_STAT_ITEMS, AO_RESOURCE_ITEMS, FS_RESOURCE_ITEMS
from database import get_user, get_user_profile, get_panel, save_panel, save_user, update_user_info, get_setting, toggle_setting, save_setting, setting_exists, get_tracked_pets, save_pet_snapshot, get_pets_farmed_detail, get_tracked_ao_pets, save_ao_pet_snapshot, get_ao_pets_farmed_detail
from api.farmsync import get_stats as fs_get_stats
from api.accountsops import get_dashboard, get_trackstats, get_all_pets, pet_kind_to_name

router = Router()

class SetKey(StatesGroup):
    waiting_key  = State()
    waiting_pet  = State()
    waiting_ao_pet = State()

# ─── /start ───────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    u = message.from_user
    user = get_user(u.id)

    if not user:
        await message.answer(
            "👋 Добро пожаловать в <b>OxyLab</b>!\n\n"
            "Выбери с какими панелями будешь работать:",
            parse_mode="HTML",
            reply_markup=panel_choice_kb()
        )
        return

    update_user_info(u.id, u.username, u.full_name)
    await show_stats(message, u.id)

# ─── Выбор панели (первый раз) ────────────────────────────────────────────────

@router.callback_query(lambda c: c.data.startswith("mode:"))
async def select_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[1]
    u = callback.from_user
    save_user(u.id, mode, u.username, u.full_name)

    panel_type = "farmsync" if mode in ("farmsync", "both") else "accountsops"
    await state.update_data(setup_mode=mode, setup_step=panel_type)
    await state.set_state(SetKey.waiting_key)

    names = {"farmsync": "FarmSync", "accountsops": "AccountsOps"}
    await callback.message.edit_text(
        f"🔑 Отправь API ключ для <b>{names[panel_type]}</b>:",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await callback.answer()

# ─── Ввод ключа ───────────────────────────────────────────────────────────────

@router.message(SetKey.waiting_key)
async def receive_key(message: Message, state: FSMContext):
    api_key = message.text.strip()
    await message.delete()

    data = await state.get_data()
    panel_type = data.get("setup_step") or data.get("edit_panel")
    setup_mode = data.get("setup_mode")
    user_id = message.from_user.id

    msg = await message.answer("🔄 Проверяю ключ...")
    ok, error = await validate_key(panel_type, api_key)

    if not ok:
        await msg.edit_text(
            f"❌ <b>Ошибка:</b> {error}\n\nПопробуй ещё раз:",
            parse_mode="HTML",
            reply_markup=cancel_kb()
        )
        return

    save_panel(user_id, panel_type, api_key)

    if setup_mode == "both" and panel_type == "farmsync":
        await state.update_data(setup_step="accountsops")
        await msg.edit_text(
            "✅ FarmSync подключён!\n\n🔑 Теперь отправь API ключ для <b>AccountsOps</b>:",
            parse_mode="HTML",
            reply_markup=cancel_kb()
        )
        return

    await state.clear()
    await msg.delete()
    await show_stats(message, user_id)

# ─── Статистика ───────────────────────────────────────────────────────────────

async def build_stats_text(user_id: int) -> str:
    user = get_user(user_id)
    mode = user[0]
    lines = ["📊 <b>OxyLab</b>"]

    fs_panel = get_panel(user_id, "farmsync")
    ao_panel = get_panel(user_id, "accountsops")

    show_active   = get_setting(user_id, "accounts_active")
    show_inactive = get_setting(user_id, "accounts_inactive")
    show_disabled = get_setting(user_id, "accounts_disabled")
    show_devices  = get_setting(user_id, "devices")

    # ── FarmSync ──
    if mode in ("farmsync", "both") and get_setting(user_id, "panel_farmsync"):
        lines.append("")
        if fs_panel:
            ok, stats, err = await fs_get_stats(fs_panel[0])
            if ok:
                def fmt(n): return f"{n:,}".replace(",", " ")

                lines.append("🌾 <b>FarmSync</b>")

                acc_parts = []
                if show_active:   acc_parts.append(f"✅ {stats['accounts_active']}")
                if show_inactive: acc_parts.append(f"💤 {stats['accounts_inactive']}")
                if show_disabled: acc_parts.append(f"⛔ {stats['accounts_disabled']}")
                if acc_parts:
                    lines.append("")
                    lines.append("  👥 " + "   ".join(acc_parts))

                if show_devices:
                    lines.append("")
                    for d in stats["devices"]:
                        lines.append(f"  🖥 {d['name']} — {d['active_accounts']}/{d['total_accounts']}")

                res_parts = []
                if get_setting(user_id, "fs_bucks"):   res_parts.append(f"💰 {fmt(stats.get('bucks', 0))}")
                if get_setting(user_id, "fs_potions"): res_parts.append(f"🧪 {fmt(stats.get('potions', 0))}")
                if res_parts:
                    lines.append("")
                    lines.append("  " + "   ".join(res_parts))

                all_pets = stats.get("pets", {})
                if all_pets:
                    save_pet_snapshot(user_id, all_pets)

                period_map = [
                    ("pets_stat_1h",   1,   "1ч"),
                    ("pets_stat_6h",   6,   "6ч"),
                    ("pets_stat_12h",  12,  "12ч"),
                    ("pets_stat_24h",  24,  "24ч"),
                    ("pets_stat_168h", 168, "7д"),
                ]
                active_periods = [(h, l) for k, h, l in period_map if get_setting(user_id, k)]

                # Предзагружаем дельты для всех активных периодов
                period_diffs = {}
                if active_periods and all_pets:
                    for hours, label in active_periods:
                        period_diffs[label] = get_pets_farmed_detail(user_id, all_pets, hours)

                tracked = get_tracked_pets(user_id)
                if tracked:
                    to_show = [
                        (name, all_pets[name])
                        for name, enabled in tracked
                        if enabled and name in all_pets
                    ]
                    if to_show:
                        lines.append("")
                        lines.append("  🐾 <b>Петы</b>")
                        from keyboards import _RARITY_ORDER
                        sorted_pets = sorted(to_show, key=lambda x: (_RARITY_ORDER.get(x[1]["rarity"], 5), x[0]))
                        for i, (name, pd) in enumerate(sorted_pets):
                            if i > 0:
                                lines.append("")
                            egg = " 🥚" if pd.get("is_egg") else ""
                            lines.append(f"  {name}{egg} × {pd['amount']}")
                            if active_periods:
                                stat_parts = []
                                for hours, label in active_periods:
                                    diffs = period_diffs.get(label)
                                    count = diffs.get(name, 0) if diffs is not None else None
                                    stat_parts.append(f"{label}: {'—' if count is None else f'+{count}'}")
                                lines.append("    " + "  ·  ".join(stat_parts))
            else:
                lines.append(f"🌾 <b>FarmSync</b> — ❌ {err}")
        else:
            lines.append("🌾 <b>FarmSync</b> — не подключён")

    # ── AccountsOps ──
    if mode in ("accountsops", "both") and get_setting(user_id, "panel_accountsops"):
        lines.append("")
        lines.append("<code>──────────────────</code>")
        lines.append("")
        if ao_panel:
            ok, data, err = await get_dashboard(ao_panel[0])
            if ok:
                lines.append("👤 <b>AccountsOps</b>")
                ao_parts = []
                if get_setting(user_id, "ao_active"):    ao_parts.append(f"✅ {data.get('active_count', 0)}")
                if get_setting(user_id, "ao_connected"): ao_parts.append(f"🔗 {data.get('connected_count', 0)}")
                if get_setting(user_id, "ao_queue"):     ao_parts.append(f"🕐 {data.get('queue_count', 0)}")
                if get_setting(user_id, "ao_joining"):   ao_parts.append(f"⚡ {data.get('joining_count', 0)}")
                if get_setting(user_id, "ao_unstable"):  ao_parts.append(f"⚠️ {data.get('unstable_count', 0)}")
                if ao_parts:
                    lines.append("")
                    lines.append("  👥 " + "   ".join(ao_parts))

                show_ao_bucks   = get_setting(user_id, "ao_bucks")
                show_ao_potions = get_setting(user_id, "ao_potions")
                if show_ao_bucks or show_ao_potions:
                    ok2, totals, _ = await get_trackstats(ao_panel[0])
                    if ok2:
                        def fmt(n): return f"{n:,}".replace(",", " ")
                        res = []
                        if show_ao_bucks:   res.append(f"💰 {fmt(totals.get('total_bucks', 0))}")
                        if show_ao_potions: res.append(f"🧪 {fmt(totals.get('total_potions', 0))}")
                        if res:
                            lines.append("")
                            lines.append("  " + "   ".join(res))

                ao_tracked_raw = get_tracked_ao_pets(user_id)
                ao_enabled = [(k, pet_kind_to_name(k)) for k, enabled in ao_tracked_raw if enabled]
                if ao_enabled:
                    ok3, all_ao_pets, _ = await get_all_pets(ao_panel[0])
                    if ok3 and all_ao_pets:
                        save_ao_pet_snapshot(user_id, all_ao_pets)

                        ao_period_map = [
                            ("ao_pets_stat_1h",   1,   "1ч"),
                            ("ao_pets_stat_6h",   6,   "6ч"),
                            ("ao_pets_stat_12h",  12,  "12ч"),
                            ("ao_pets_stat_24h",  24,  "24ч"),
                            ("ao_pets_stat_168h", 168, "7д"),
                        ]
                        ao_active_periods = [(h, l) for k, h, l in ao_period_map if get_setting(user_id, k)]

                        ao_period_diffs = {}
                        if ao_active_periods:
                            for hours, label in ao_active_periods:
                                ao_period_diffs[label] = get_ao_pets_farmed_detail(user_id, all_ao_pets, hours)

                        to_show = [(k, name, all_ao_pets[k]) for k, name in ao_enabled if k in all_ao_pets]
                        if to_show:
                            lines.append("")
                            lines.append("  🐾 <b>Петы</b>")
                            for i, (kind, name, pd) in enumerate(to_show):
                                if i > 0:
                                    lines.append("")
                                egg = " 🥚" if pd.get("is_egg") else ""
                                lines.append(f"  {name}{egg} × {pd['quantity']}")
                                if ao_active_periods:
                                    stat_parts = []
                                    for hours, label in ao_active_periods:
                                        diffs = ao_period_diffs.get(label)
                                        count = diffs.get(kind, 0) if diffs is not None else None
                                        stat_parts.append(f"{label}: {'—' if count is None else f'+{count}'}")
                                    lines.append("    " + "  ·  ".join(stat_parts))
            else:
                lines.append(f"👤 <b>AccountsOps</b> — ❌ {err}")
        else:
            lines.append("👤 <b>AccountsOps</b> — не подключён")

    return "\n".join(lines)

async def show_stats(message_or_obj, user_id: int, edit: bool = False):
    from config import ADMIN_ID
    text = await build_stats_text(user_id)
    kb = stats_kb(is_admin=(user_id == ADMIN_ID))
    try:
        if edit and hasattr(message_or_obj, 'edit_text'):
            await message_or_obj.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            await message_or_obj.answer(text, parse_mode="HTML", reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise

# ─── Кастомизация ─────────────────────────────────────────────────────────────

PET_STAT_KEYS    = [k for k, _ in PET_STAT_PERIODS]
AO_PET_STAT_KEYS = [k for k, _ in AO_PET_STAT_PERIODS]
AO_KEYS          = [k for k, _ in AO_STAT_ITEMS]
AO_RES_KEYS      = [k for k, _ in AO_RESOURCE_ITEMS]
FS_RES_KEYS      = [k for k, _ in FS_RESOURCE_ITEMS]
PANEL_KEYS       = ["panel_farmsync", "panel_accountsops"]
SETTING_KEYS     = ["accounts_active", "accounts_inactive", "accounts_disabled", "devices"] + PET_STAT_KEYS + AO_PET_STAT_KEYS + AO_KEYS + AO_RES_KEYS + FS_RES_KEYS + PANEL_KEYS
ACCOUNTS_KEYS    = ["accounts_active", "accounts_inactive", "accounts_disabled"]

def _get_settings(user_id: int) -> dict:
    return {key: get_setting(user_id, key) for key in SETTING_KEYS}

@router.callback_query(lambda c: c.data == "customize")
async def open_customize(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚙️ <b>Кастомизация</b>\n\n"
        "Выбери что отображать на главном экране:",
        parse_mode="HTML",
        reply_markup=customize_kb(_get_settings(callback.from_user.id))
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "customize:farmsync")
async def open_customize_farmsync(callback: CallbackQuery):
    await callback.message.edit_text(
        "🌾 <b>FarmSync</b>\n\nВыбери что отображать:",
        parse_mode="HTML",
        reply_markup=farmsync_customize_kb(_get_settings(callback.from_user.id))
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "customize:accounts")
async def open_customize_accounts(callback: CallbackQuery):
    await callback.message.edit_text(
        "👥 <b>Аккаунты</b>\n\n"
        "Выбери какую статистику показывать:",
        parse_mode="HTML",
        reply_markup=accounts_customize_kb(_get_settings(callback.from_user.id))
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "customize:fs_resources")
async def open_customize_fs_resources(callback: CallbackQuery):
    await callback.message.edit_text(
        "💰 <b>Ресурсы</b>\n\nВыбери что показывать:",
        parse_mode="HTML",
        reply_markup=fs_resources_customize_kb(_get_settings(callback.from_user.id))
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "customize:accountsops")
async def open_customize_ao(callback: CallbackQuery):
    await callback.message.edit_text(
        "👤 <b>AccountsOps</b>\n\nВыбери раздел:",
        parse_mode="HTML",
        reply_markup=ao_customize_kb()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "customize:ao_accounts")
async def open_customize_ao_accounts(callback: CallbackQuery):
    await callback.message.edit_text(
        "👥 <b>Аккаунты</b>\n\nВыбери какую статистику показывать:",
        parse_mode="HTML",
        reply_markup=ao_accounts_customize_kb(_get_settings(callback.from_user.id))
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "customize:ao_resources")
async def open_customize_ao_resources(callback: CallbackQuery):
    await callback.message.edit_text(
        "💰 <b>Ресурсы</b>\n\nВыбери что показывать:",
        parse_mode="HTML",
        reply_markup=ao_resources_customize_kb(_get_settings(callback.from_user.id))
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "customize:ao_pets")
async def open_customize_ao_pets(callback: CallbackQuery):
    raw = get_tracked_ao_pets(callback.from_user.id)
    tracked = [(k, pet_kind_to_name(k), enabled) for k, enabled in raw]
    await callback.message.edit_text(
        "🐾 <b>Петы</b>\n\n"
        "Список отслеживаемых петов.\n"
        "Нажми чтобы включить/выключить:",
        parse_mode="HTML",
        reply_markup=ao_pets_customize_kb(tracked)
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "customize:ao_pets_stats")
async def open_customize_ao_pets_stats(callback: CallbackQuery):
    await callback.message.edit_text(
        "📊 <b>Статистика фарма</b>\n\n"
        "Выбери какие периоды показывать:",
        parse_mode="HTML",
        reply_markup=ao_pets_stats_customize_kb(_get_settings(callback.from_user.id))
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "customize:pets_stats")
async def open_customize_pets_stats(callback: CallbackQuery):
    await callback.message.edit_text(
        "📊 <b>Статистика фарма</b>\n\n"
        "Выбери какие периоды показывать:",
        parse_mode="HTML",
        reply_markup=pets_stats_customize_kb(_get_settings(callback.from_user.id))
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "customize:pets")
async def open_customize_pets(callback: CallbackQuery):
    tracked = get_tracked_pets(callback.from_user.id)
    await callback.message.edit_text(
        "🐾 <b>Петы</b>\n\n"
        "Список отслеживаемых петов.\n"
        "Нажми чтобы включить/выключить:",
        parse_mode="HTML",
        reply_markup=pets_customize_kb(tracked)
    )
    await callback.answer()

# Тоглы обычных настроек (accounts_*, devices)
@router.callback_query(lambda c: c.data.startswith("toggle:") and not c.data.startswith("toggle:pet:"))
async def handle_toggle(callback: CallbackQuery):
    key = callback.data[len("toggle:"):]
    if key not in SETTING_KEYS:
        await callback.answer()
        return
    toggle_setting(callback.from_user.id, key)
    settings = _get_settings(callback.from_user.id)
    if key in ACCOUNTS_KEYS:
        kb = accounts_customize_kb(settings)
    elif key in PET_STAT_KEYS:
        kb = pets_stats_customize_kb(settings)
    elif key in AO_PET_STAT_KEYS:
        kb = ao_pets_stats_customize_kb(settings)
    elif key in AO_KEYS:
        kb = ao_accounts_customize_kb(settings)
    elif key in AO_RES_KEYS:
        kb = ao_resources_customize_kb(settings)
    elif key in FS_RES_KEYS:
        kb = fs_resources_customize_kb(settings)
    elif key in PANEL_KEYS:
        kb = customize_kb(settings)
    else:
        kb = farmsync_customize_kb(settings)  # "devices" живёт в FarmSync-подменю
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()

# Тоглы петов FarmSync — только DB, без API
@router.callback_query(lambda c: c.data.startswith("toggle:pet:"))
async def handle_pet_toggle(callback: CallbackQuery):
    key = callback.data[len("toggle:"):]   # "pet:Name"
    toggle_setting(callback.from_user.id, key)
    tracked = get_tracked_pets(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=pets_customize_kb(tracked))
    await callback.answer()

# Тоглы петов AccountsOps
@router.callback_query(lambda c: c.data.startswith("toggle:ao_pet:"))
async def handle_ao_pet_toggle(callback: CallbackQuery):
    pet_kind = callback.data[len("toggle:ao_pet:"):]
    toggle_setting(callback.from_user.id, f"ao_pet:{pet_kind}")
    raw = get_tracked_ao_pets(callback.from_user.id)
    tracked = [(k, pet_kind_to_name(k), enabled) for k, enabled in raw]
    await callback.message.edit_reply_markup(reply_markup=ao_pets_customize_kb(tracked))
    await callback.answer()

# ─── Добавление пета ──────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "pets_add")
async def pets_add_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SetKey.waiting_pet)
    await callback.message.edit_text(
        "🐾 <b>Добавить пета</b>\n\n"
        "Введи название пета или яйца <b>точно как в игре</b>.\n\n"
        "<i>⚠️ Пет должен присутствовать в инвентаре хотя бы одного аккаунта.</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@router.message(SetKey.waiting_pet)
async def pets_add_receive(message: Message, state: FSMContext):
    pet_name = message.text.strip()
    await message.delete()
    user_id = message.from_user.id

    msg = await message.answer("🔄 Ищу в инвентаре...")

    fs_panel = get_panel(user_id, "farmsync")
    if not fs_panel:
        await msg.edit_text("❌ FarmSync не подключён.", reply_markup=back_kb())
        await state.clear()
        return

    ok, stats, err = await fs_get_stats(fs_panel[0])
    if not ok:
        await msg.edit_text(f"❌ {err}", reply_markup=back_kb())
        await state.clear()
        return

    pets = stats.get("pets", {})
    matched = next((n for n in pets if n.lower() == pet_name.lower()), None)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    back_to_pets = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К петам", callback_data="customize:pets")]
    ])

    if not matched:
        await msg.edit_text(
            f"❌ <b>{pet_name}</b> не найден в инвентаре.\n\n"
            "Проверь название и попробуй ещё раз:",
            parse_mode="HTML",
            reply_markup=back_to_pets
        )
        await state.clear()
        return

    key = f"pet:{matched}"
    already = setting_exists(user_id, key)
    save_setting(user_id, key, True)
    await state.clear()

    pd   = pets[matched]
    egg  = " 🥚" if pd.get("is_egg") else ""
    info = f"×{pd['amount']}  ({pd['rarity']})"

    if already:
        text = f"ℹ️ <b>{matched}</b>{egg} уже отслеживается.\n{info}"
    else:
        text = f"✅ <b>{matched}</b>{egg} добавлен в отслеживание!\n{info}"

    await msg.edit_text(text, parse_mode="HTML", reply_markup=back_to_pets)

# ─── Добавление пета AccountsOps ─────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "ao_pets_add")
async def ao_pets_add_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SetKey.waiting_ao_pet)
    await callback.message.edit_text(
        "🐾 <b>Добавить пета (AccountsOps)</b>\n\n"
        "Введи название пета <b>точно как в игре</b>.\n\n"
        "<i>⚠️ Пет должен присутствовать в инвентаре хотя бы одного аккаунта.</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@router.message(SetKey.waiting_ao_pet)
async def ao_pets_add_receive(message: Message, state: FSMContext):
    pet_name = message.text.strip()
    await message.delete()
    user_id = message.from_user.id

    msg = await message.answer("🔄 Ищу в инвентаре...")

    ao_panel = get_panel(user_id, "accountsops")
    if not ao_panel:
        await msg.edit_text("❌ AccountsOps не подключён.", reply_markup=back_kb())
        await state.clear()
        return

    ok, all_pets, err = await get_all_pets(ao_panel[0])
    if not ok:
        await msg.edit_text(f"❌ {err}", reply_markup=back_kb())
        await state.clear()
        return

    matched_kind = None
    for kind in all_pets:
        if pet_kind_to_name(kind).lower() == pet_name.lower() or kind.lower() == pet_name.lower():
            matched_kind = kind
            break

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    back_to_pets = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К петам", callback_data="customize:ao_pets")]
    ])

    if not matched_kind:
        await msg.edit_text(
            f"❌ <b>{pet_name}</b> не найден в инвентаре.\n\n"
            "Проверь название и попробуй ещё раз:",
            parse_mode="HTML",
            reply_markup=back_to_pets
        )
        await state.clear()
        return

    key = f"ao_pet:{matched_kind}"
    already = setting_exists(user_id, key)
    save_setting(user_id, key, True)
    await state.clear()

    pd  = all_pets[matched_kind]
    egg = " 🥚" if pd.get("is_egg") else ""
    display_name = pet_kind_to_name(matched_kind)

    if already:
        text = f"ℹ️ <b>{display_name}</b>{egg} уже отслеживается.\n×{pd['quantity']}"
    else:
        text = f"✅ <b>{display_name}</b>{egg} добавлен в отслеживание!\n×{pd['quantity']}"

    await msg.edit_text(text, parse_mode="HTML", reply_markup=back_to_pets)

# ─── Профиль ──────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "profile")
async def show_profile(callback: CallbackQuery):
    from datetime import datetime
    profile = get_user_profile(callback.from_user.id)
    if not profile:
        await callback.answer("Профиль не найден", show_alert=True)
        return

    mode, username, full_name, created_at, subscription = profile

    try:
        date_str = datetime.fromisoformat(created_at).strftime("%d.%m.%Y")
    except Exception:
        date_str = created_at or "—"

    mode_labels = {
        "farmsync":    "🌾 FarmSync",
        "accountsops": "👤 AccountsOps",
        "both":        "🌾 FarmSync + 👤 AccountsOps",
    }

    lines = [
        "👤 <b>Профиль</b>\n",
        f"ID: <code>{callback.from_user.id}</code>",
        f"Имя: {full_name or '—'}",
        f"Username: {'@' + username if username else '—'}",
        f"\nПодписка: <b>{subscription or 'Test'}</b>",
        f"Регистрация: {date_str}",
        f"Панели: {mode_labels.get(mode, mode)}",
    ]

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_kb()
    )
    await callback.answer()

# ─── Кнопки ───────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "refresh_stats")
async def refresh_stats(callback: CallbackQuery):
    await callback.answer("🔄 Обновляю...")
    await show_stats(callback.message, callback.from_user.id, edit=True)

@router.callback_query(lambda c: c.data == "back_stats")
async def back_stats(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_stats(callback.message, callback.from_user.id, edit=True)

@router.callback_query(lambda c: c.data == "api_keys")
async def api_keys_menu(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    mode = user[0]
    has_fs = get_panel(callback.from_user.id, "farmsync") is not None
    has_ao = get_panel(callback.from_user.id, "accountsops") is not None

    await callback.message.edit_text(
        "🔑 <b>Управление API ключами</b>\n\n"
        "Нажми на панель чтобы подключить или сменить ключ:",
        parse_mode="HTML",
        reply_markup=api_keys_kb(mode, has_fs, has_ao)
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("set_key:"))
async def set_key(callback: CallbackQuery, state: FSMContext):
    panel_type = callback.data.split(":")[1]
    await state.set_state(SetKey.waiting_key)
    await state.update_data(edit_panel=panel_type)

    names = {"farmsync": "FarmSync", "accountsops": "AccountsOps"}
    await callback.message.edit_text(
        f"🔑 Отправь новый API ключ для <b>{names[panel_type]}</b>:",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await callback.answer()

# ─── Валидация ────────────────────────────────────────────────────────────────

async def validate_key(panel_type: str, api_key: str) -> tuple[bool, str]:
    if panel_type == "farmsync":
        from api.farmsync import get_devices
        ok, _, err = await get_devices(api_key)
        return ok, err
    else:
        ok, _, err = await get_dashboard(api_key)
        return ok, err
