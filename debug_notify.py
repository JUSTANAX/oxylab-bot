_bot = None
_admin_id = None

def setup(bot, admin_id):
    global _bot, _admin_id
    _bot = bot
    _admin_id = admin_id

async def notify(text: str):
    if _bot and _admin_id:
        try:
            await _bot.send_message(_admin_id, text, parse_mode="HTML")
        except Exception:
            pass
