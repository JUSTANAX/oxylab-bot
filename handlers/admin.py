import os
import sys
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_ID
from database import get_admin_stats, get_all_users, get_panel
from keyboards import admin_kb

router = Router()

# ─── /admin ───────────────────────────────────────────────────────────────────

@router.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def cmd_admin(message: Message):
    await _show_admin(message)

@router.callback_query(lambda c: c.data == "admin_panel", F.from_user.id == ADMIN_ID)
async def open_admin_panel(callback: CallbackQuery):
    await _show_admin(callback.message, edit=True)
    await callback.answer()

async def _show_admin(target, edit: bool = False):
    s = get_admin_stats()
    text = (
        "🛠 <b>Админ-панель</b>\n\n"
        f"👥 Пользователей:  <b>{s['total_users']}</b>\n"
        f"🌾 FarmSync:       <b>{s['farmsync_panels']}</b>\n"
        f"👤 AccountsOps:    <b>{s['accountsops_panels']}</b>"
    )
    if edit:
        await target.edit_text(text, parse_mode="HTML", reply_markup=admin_kb())
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=admin_kb())

# ─── Список пользователей ─────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin_users", F.from_user.id == ADMIN_ID)
async def admin_users(callback: CallbackQuery):
    rows = get_all_users(limit=20)
    if not rows:
        await callback.answer("Нет пользователей", show_alert=True)
        return

    lines = ["🛠 Админ  ›  👥 <b>Пользователи</b>\n"]
    for user_id, full_name, username, mode, created_at in rows:
        uname = f"@{username}" if username else "—"
        name  = full_name or "—"
        lines.append(f"<code>{user_id}</code>  {name}  {uname}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
    ])
    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)
    await callback.answer()

# ─── /setaokey ────────────────────────────────────────────────────────────────

@router.message(Command("setaokey"), F.from_user.id == ADMIN_ID)
async def cmd_setaokey(message: Message):
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: <code>/setaokey &lt;api_key&gt;</code>", parse_mode="HTML")
        return
    api_key = parts[1].strip()
    from database import save_panel
    save_panel(message.from_user.id, "accountsops", api_key)
    await message.answer(f"✅ Ключ AccountsOps сохранён\n<code>{api_key[:6]}...{api_key[-4:]}</code> ({len(api_key)} симв.)", parse_mode="HTML")

# ─── /debugao ─────────────────────────────────────────────────────────────────

@router.message(Command("debugao"), F.from_user.id == ADMIN_ID)
async def cmd_debugao(message: Message):
    import os
    from api.accountsops import _get
    from config import DB_PATH
    db_abs = os.path.abspath(DB_PATH)
    await message.answer(f"🔖 Версия кода: <b>v2.3</b>\n📁 БД: <code>{db_abs}</code>", parse_mode="HTML")
    panel = get_panel(message.from_user.id, "accountsops")
    if not panel:
        await message.answer("❌ AccountsOps не подключён в базе")
        return
    api_key = panel[0]
    await message.answer(f"🔑 Ключ в БД: <code>{api_key[:6]}...{api_key[-4:]}</code> ({len(api_key)} симв.)", parse_mode="HTML")
    ok, data, err = await _get(api_key, "/api/dashboard")
    if ok:
        await message.answer(f"✅ /api/dashboard OK\n<code>{str(data)[:500]}</code>", parse_mode="HTML")
    else:
        await message.answer(f"❌ /api/dashboard FAIL\n{err}", parse_mode="HTML")

# ─── /restart ─────────────────────────────────────────────────────────────────

@router.message(Command("restart"), F.from_user.id == ADMIN_ID)
async def cmd_restart(message: Message):
    await message.answer("🔄 Перезагружаю бота...")
    os.execv(sys.executable, [sys.executable] + sys.argv)

@router.callback_query(lambda c: c.data == "admin_restart", F.from_user.id == ADMIN_ID)
async def admin_restart(callback: CallbackQuery):
    await callback.message.edit_text("🔄 Перезагружаю бота...")
    await callback.answer()
    os.execv(sys.executable, [sys.executable] + sys.argv)
