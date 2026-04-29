import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден! Проверь файл .env")

ADMIN_ID = 6101243914

DB_PATH = os.getenv("DB_PATH", "oxylab.db")
FARMSYNC_URL = "https://api.farmsync.cloud"
ACCOUNTSOPS_URL = "https://accountops.org"
