from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def panel_choice_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌾 FarmSync",     callback_data="mode:farmsync")],
        [InlineKeyboardButton(text="👤 AccountsOps",  callback_data="mode:accountsops")],
        [InlineKeyboardButton(text="⚡ Оба варианта", callback_data="mode:both")],
    ])

def stats_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔄 Обновить",      callback_data="refresh_stats")],
        [InlineKeyboardButton(text="👤 Профиль",        callback_data="profile"),
         InlineKeyboardButton(text="🔑 API-Ключи",      callback_data="api_keys")],
        [InlineKeyboardButton(text="⚙️ Кастомизация",  callback_data="customize"),
         InlineKeyboardButton(text="📋 Обновления",    callback_data="changelog")],
        [InlineKeyboardButton(text="🔔 Уведомления",   callback_data="alerts")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠 Админ", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

FS_RESOURCE_ITEMS = [
    ("fs_bucks",   "💰 Баксы"),
    ("fs_potions", "🧪 Зелья"),
]

AO_STAT_ITEMS = [
    ("ao_active",    "✅ Активных"),
    ("ao_connected", "🔗 Подключено"),
    ("ao_queue",     "🕐 В очереди"),
    ("ao_joining",   "⚡ Присоединяется"),
    ("ao_unstable",  "⚠️ Нестабильных"),
]

AO_RESOURCE_ITEMS = [
    ("ao_bucks",   "💰 Баксы"),
    ("ao_potions", "🧪 Зелья"),
]

def customize_kb(settings: dict) -> InlineKeyboardMarkup:
    fs_on = "✅" if settings.get("panel_farmsync",    True) else "❌"
    ao_on = "✅" if settings.get("panel_accountsops", True) else "❌"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌾 FarmSync  ›",    callback_data="customize:farmsync"),
            InlineKeyboardButton(text=fs_on,               callback_data="toggle:panel_farmsync"),
        ],
        [
            InlineKeyboardButton(text="👤 AccountsOps  ›", callback_data="customize:accountsops"),
            InlineKeyboardButton(text=ao_on,               callback_data="toggle:panel_accountsops"),
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_stats")],
    ])

def farmsync_customize_kb(settings: dict) -> InlineKeyboardMarkup:
    def btn(key: str, label: str) -> InlineKeyboardButton:
        icon = "✅" if settings.get(key, True) else "❌"
        return InlineKeyboardButton(text=f"{icon}  {label}", callback_data=f"toggle:{key}")

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Аккаунты  ›",  callback_data="customize:accounts")],
        [btn("devices", "🖥 Девайсы")],
        [InlineKeyboardButton(text="🐾 Петы  ›",      callback_data="customize:pets")],
        [InlineKeyboardButton(text="💰 Ресурсы  ›",   callback_data="customize:fs_resources")],
        [InlineKeyboardButton(text="🔙 Назад",         callback_data="customize")],
    ])

def fs_resources_customize_kb(settings: dict) -> InlineKeyboardMarkup:
    rows = []
    for key, label in FS_RESOURCE_ITEMS:
        icon = "✅" if settings.get(key, True) else "❌"
        rows.append([InlineKeyboardButton(text=f"{icon}  {label}", callback_data=f"toggle:{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="customize:farmsync")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def ao_customize_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Аккаунты  ›", callback_data="customize:ao_accounts")],
        [InlineKeyboardButton(text="🐾 Петы  ›",     callback_data="customize:ao_pets")],
        [InlineKeyboardButton(text="💰 Ресурсы  ›",  callback_data="customize:ao_resources")],
        [InlineKeyboardButton(text="🔙 Назад",        callback_data="customize")],
    ])

def ao_pets_customize_kb(tracked: list) -> InlineKeyboardMarkup:
    rows = []
    for pet_kind, display_name, enabled in tracked:
        icon = "✅" if enabled else "❌"
        rows.append([InlineKeyboardButton(
            text=f"{icon}  {display_name}",
            callback_data=f"toggle:ao_pet:{pet_kind}"
        )])
    rows.append([InlineKeyboardButton(text="📊 Статистика фарма  ›", callback_data="customize:ao_pets_stats")])
    rows.append([InlineKeyboardButton(text="➕ Добавить пета",        callback_data="ao_pets_add")])
    rows.append([InlineKeyboardButton(text="🔙 Назад",                callback_data="customize:accountsops")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def ao_pets_stats_customize_kb(settings: dict) -> InlineKeyboardMarkup:
    rows = []
    for key, label in AO_PET_STAT_PERIODS:
        icon = "✅" if settings.get(key, True) else "❌"
        rows.append([InlineKeyboardButton(text=f"{icon}  {label}", callback_data=f"toggle:{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="customize:ao_pets")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def ao_resources_customize_kb(settings: dict) -> InlineKeyboardMarkup:
    rows = []
    for key, label in AO_RESOURCE_ITEMS:
        icon = "✅" if settings.get(key, True) else "❌"
        rows.append([InlineKeyboardButton(text=f"{icon}  {label}", callback_data=f"toggle:{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="customize:accountsops")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def ao_accounts_customize_kb(settings: dict) -> InlineKeyboardMarkup:
    rows = []
    for key, label in AO_STAT_ITEMS:
        icon = "✅" if settings.get(key, True) else "❌"
        rows.append([InlineKeyboardButton(text=f"{icon}  {label}", callback_data=f"toggle:{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="customize:accountsops")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def accounts_customize_kb(settings: dict) -> InlineKeyboardMarkup:
    def btn(key: str, label: str) -> InlineKeyboardButton:
        icon = "✅" if settings.get(key, True) else "❌"
        return InlineKeyboardButton(text=f"{icon}  {label}", callback_data=f"toggle:{key}")

    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("accounts_active",   "✅ Активные")],
        [btn("accounts_inactive", "💤 Неактивные")],
        [btn("accounts_disabled", "⛔ Выключенные")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="customize:farmsync")],
    ])

_RARITY_ORDER = {"Legendary": 0, "Epic": 1, "Rare": 2, "Uncommon": 3, "Common": 4}

PET_STAT_PERIODS = [
    ("pets_stat_1h",   "За час"),
    ("pets_stat_6h",   "За 6 часов"),
    ("pets_stat_12h",  "За 12 часов"),
    ("pets_stat_24h",  "За 24 часа"),
    ("pets_stat_168h", "За 7 дней"),
]

AO_PET_STAT_PERIODS = [
    ("ao_pets_stat_1h",   "За час"),
    ("ao_pets_stat_6h",   "За 6 часов"),
    ("ao_pets_stat_12h",  "За 12 часов"),
    ("ao_pets_stat_24h",  "За 24 часа"),
    ("ao_pets_stat_168h", "За 7 дней"),
]

def pets_customize_kb(tracked: list) -> InlineKeyboardMarkup:
    rows = []
    for name, enabled in tracked:
        icon = "✅" if enabled else "❌"
        rows.append([InlineKeyboardButton(
            text=f"{icon}  {name}",
            callback_data=f"toggle:pet:{name}"
        )])
    rows.append([InlineKeyboardButton(text="📊 Статистика фарма  ›", callback_data="customize:pets_stats")])
    rows.append([InlineKeyboardButton(text="➕ Добавить пета",        callback_data="pets_add")])
    rows.append([InlineKeyboardButton(text="🔙 Назад",                callback_data="customize:farmsync")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def pets_stats_customize_kb(settings: dict) -> InlineKeyboardMarkup:
    rows = []
    for key, label in PET_STAT_PERIODS:
        icon = "✅" if settings.get(key, True) else "❌"
        rows.append([InlineKeyboardButton(text=f"{icon}  {label}", callback_data=f"toggle:{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="customize:pets")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи",  callback_data="admin_users")],
        [InlineKeyboardButton(text="🔄 Перезагрузить", callback_data="admin_restart")],
        [InlineKeyboardButton(text="🔙 Назад",          callback_data="back_stats")],
    ])

def api_keys_kb(mode: str, has_fs: bool, has_ao: bool) -> InlineKeyboardMarkup:
    buttons = []

    if mode in ("farmsync", "both"):
        label = "🌾 FarmSync: ✅ Сменить ключ" if has_fs else "🌾 FarmSync: ❌ Подключить"
        buttons.append([InlineKeyboardButton(text=label, callback_data="set_key:farmsync")])

    if mode in ("accountsops", "both"):
        label = "👤 AccountsOps: ✅ Сменить ключ" if has_ao else "👤 AccountsOps: ❌ Подключить"
        buttons.append([InlineKeyboardButton(text=label, callback_data="set_key:accountsops")])

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_stats")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_stats")]
    ])

def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_stats")]
    ])

def alerts_kb(mode: str, thresholds: dict) -> InlineKeyboardMarkup:
    rows = []
    if mode in ("farmsync", "both"):
        t = thresholds.get("farmsync")
        if t and t["threshold"]:
            label = f"🌾 FarmSync: < {t['threshold']}"
            icon = "✅" if t["enabled"] else "❌"
        else:
            label = "🌾 FarmSync: — задать порог"
            icon = "❌"
        rows.append([
            InlineKeyboardButton(text=label,  callback_data="alert_set:farmsync"),
            InlineKeyboardButton(text=icon,   callback_data="alert_toggle:farmsync"),
        ])
    if mode in ("accountsops", "both"):
        t = thresholds.get("accountsops")
        if t and t["threshold"]:
            label = f"👤 AccountsOps: < {t['threshold']}"
            icon = "✅" if t["enabled"] else "❌"
        else:
            label = "👤 AccountsOps: — задать порог"
            icon = "❌"
        rows.append([
            InlineKeyboardButton(text=label,  callback_data="alert_set:accountsops"),
            InlineKeyboardButton(text=icon,   callback_data="alert_toggle:accountsops"),
        ])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_stats")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def alert_input_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="alerts")]
    ])
