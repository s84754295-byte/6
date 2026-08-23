import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
# Начальный список админов из .env (владелец всегда админ)
_raw_admins = os.getenv("ADMIN_IDS", str(OWNER_ID))
ADMIN_IDS = list(set(map(int, _raw_admins.split(","))))  # уникальные
if OWNER_ID not in ADMIN_IDS:
    ADMIN_IDS.append(OWNER_ID)

DB_NAME = os.getenv("DB_NAME", "bot.db")
