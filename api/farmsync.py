import json
import asyncio
import aiohttp
from config import FARMSYNC_URL

async def _get(api_key: str, endpoint: str) -> tuple[bool, any, str]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{FARMSYNC_URL}{endpoint}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 401:
                    return False, None, "Неверный API ключ."
                if resp.status == 403:
                    return False, None, "Доступ запрещён."
                if resp.status != 200:
                    return False, None, f"Ошибка сервера (код {resp.status})."
                return True, await resp.json(), ""
    except aiohttp.ClientConnectorError:
        return False, None, "Не удалось подключиться к FarmSync."
    except Exception as e:
        return False, None, f"Ошибка: {e}"

async def get_devices(api_key: str) -> tuple[bool, list, str]:
    ok, data, err = await _get(api_key, "/api/devices/")
    return ok, data or [], err

async def get_accounts(api_key: str) -> tuple[bool, list, str]:
    ok, data, err = await _get(api_key, "/api/self/accounts")
    return ok, data or [], err

async def get_stats(api_key: str) -> tuple[bool, dict, str]:
    """Получаем всё за один раз для главного экрана."""
    (ok_d, devices, err_d), (ok_a, accounts, err_a) = await asyncio.gather(
        get_devices(api_key),
        get_accounts(api_key),
    )
    if not ok_d:
        return False, {}, err_d
    if not ok_a:
        return False, {}, err_a

    active   = sum(1 for a in accounts if a.get("running") and a.get("enabled"))
    inactive = sum(1 for a in accounts if not a.get("running") and a.get("enabled"))
    disabled = sum(1 for a in accounts if not a.get("enabled"))

    devices_list = [
        {
            "name":            d.get("device_note") or d.get("device_name") or d.get("id", "Unknown"),
            "active_accounts": d.get("active_accounts", 0),
            "total_accounts":  d.get("total_accounts", 0),
        }
        for d in devices
    ]

    # Агрегируем петов и ресурсы из поля data каждого аккаунта
    pets: dict[str, dict] = {}
    bucks = ride_potions = fly_potions = potions = 0

    for account in accounts:
        try:
            data = json.loads(account.get("data") or "{}")
            bucks        += data.get("bucks", 0)
            potions      += data.get("potions", 0)
            ride_potions += data.get("ride_potions", 0)
            fly_potions  += data.get("fly_potions", 0)
            for pet in data.get("pets", []):
                name = pet.get("name")
                if not name:
                    continue
                if name not in pets:
                    pets[name] = {
                        "amount": 0,
                        "rarity": pet.get("rarity", "Common"),
                        "is_egg": pet.get("is_egg", False),
                    }
                pets[name]["amount"] += pet.get("amount", 1)
        except Exception:
            continue

    return True, {
        "accounts_active":   active,
        "accounts_inactive": inactive,
        "accounts_disabled": disabled,
        "devices":           devices_list,
        "pets":              pets,
        "bucks":             bucks,
        "potions":           potions,
        "ride_potions":      ride_potions,
        "fly_potions":       fly_potions,
    }, ""
