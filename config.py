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

# ---------- Казна: приём/выплаты через @CryptoBot (Crypto Pay API) ----------
# Токен приложения Crypto Pay: @CryptoBot -> /pay -> Create App -> API Token
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN", "")
# True — тестовая сеть (@CryptoTestnetBot), False — боевая (@CryptoBot)
USE_TESTNET = os.getenv("USE_TESTNET", "false").lower() == "true"
CRYPTO_PAY_BASE_URL = (
    "https://testnet-pay.crypt.bot/api/" if USE_TESTNET else "https://pay.crypt.bot/api/"
)
# Актив, в котором хранится баланс и выполняются выводы (USDT, TON, BTC, ETH, ...)
DEFAULT_ASSET = os.getenv("DEFAULT_ASSET", "USDT")
