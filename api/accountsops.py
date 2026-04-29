import re
import asyncio
import aiohttp
from config import ACCOUNTSOPS_URL

def pet_kind_to_name(pet_kind: str) -> str:
    name = re.sub(r'^.*_\d{4}_', '', pet_kind)
    return name.replace('_', ' ').title()

async def _get(api_key: str, endpoint: str) -> tuple[bool, any, str]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{ACCOUNTSOPS_URL}{endpoint}",
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
        return False, None, "Не удалось подключиться к AccountsOps."
    except Exception as e:
        return False, None, f"Ошибка: {e}"

async def get_dashboard(api_key: str) -> tuple[bool, dict, str]:
    ok, data, err = await _get(api_key, "/api/dashboard")
    return ok, data or {}, err

async def get_trackstats(api_key: str) -> tuple[bool, dict, str]:
    ok, data, err = await _get(api_key, "/api/trackstats/accounts")
    if not ok:
        return False, {}, err
    totals = data.get("totals", {}) if isinstance(data, dict) else {}
    return True, totals, ""

async def get_account_pets(api_key: str, account_id) -> tuple[bool, list, str]:
    ok, data, err = await _get(api_key, f"/api/trackstats/accounts/{account_id}/pets")
    return ok, data or [], err

async def get_all_pets(api_key: str) -> tuple[bool, dict, str]:
    """Aggregate pets across all accounts. Returns {pet_kind: {"quantity": N, "is_egg": bool}}"""
    ok, data, err = await _get(api_key, "/api/trackstats/accounts")
    if not ok:
        return False, {}, err

    if isinstance(data, dict):
        accounts = data.get("accounts") or []
    elif isinstance(data, list):
        accounts = data
    else:
        accounts = []

    if not accounts:
        return True, {}, ""

    sem = asyncio.Semaphore(10)

    async def fetch(acc_id):
        async with sem:
            return await get_account_pets(api_key, acc_id)

    results = await asyncio.gather(
        *[fetch(acc["id"]) for acc in accounts if acc.get("id")],
        return_exceptions=True,
    )

    pets: dict = {}
    for result in results:
        if isinstance(result, Exception) or not result[0]:
            continue
        for pet in result[1]:
            kind = pet.get("pet_kind")
            if not kind:
                continue
            if kind not in pets:
                pets[kind] = {"quantity": 0, "is_egg": pet.get("is_egg", False)}
            pets[kind]["quantity"] += pet.get("quantity", 0)
    return True, pets, ""
