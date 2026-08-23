import aiosqlite
from config import DB_NAME, OWNER_ID, ADMIN_IDS

# category: 'max_registered' | 'max_unregistered' | 'bk'
CAT_MAX_REG = "max_registered"
CAT_MAX_NEW = "max_unregistered"
CAT_BK = "bk"

# Обратная совместимость: раньше существовало только приложение MAX
CAT_REG = CAT_MAX_REG
CAT_NEW = CAT_MAX_NEW

CAT_LABEL = {
    CAT_MAX_REG: "MAX • Рег",
    CAT_MAX_NEW: "MAX • Нерег",
    CAT_BK: "BK",
}

# Приложения (категории верхнего уровня), доступные для сдачи номеров.
# У MAX есть подкатегории Рег/Нерег с разными ценами.
# У BK своя отдельная логика без подкатегорий — одна цена, номер сразу уходит в очередь.
APPS = {
    "max": {"label": "MAX", "reg": CAT_MAX_REG, "new": CAT_MAX_NEW},
    "bk":  {"label": "BK",  "single": CAT_BK},
}


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0,
                total INTEGER DEFAULT 0,
                success INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                banned INTEGER DEFAULT 0,
                approved INTEGER DEFAULT 0,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN approved INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN subscribed INTEGER DEFAULT 0")
        except Exception:
            pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                number TEXT,
                status TEXT DEFAULT 'pending',
                code TEXT DEFAULT '',
                category TEXT DEFAULT 'registered',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for col, default in [("code", "''"), ("category", "'registered'")]:
            try:
                await db.execute(f"ALTER TABLE numbers ADD COLUMN {col} TEXT DEFAULT {default}")
            except Exception:
                pass
        for col, typ in [("code_msg_id", "INTEGER"), ("code_requested_at", "TEXT")]:
            try:
                await db.execute(f"ALTER TABLE numbers ADD COLUMN {col} {typ}")
            except Exception:
                pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                status TEXT DEFAULT 'pending',
                crypto_address TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        """)

        await db.execute("INSERT OR IGNORE INTO settings VALUES ('price', '5.8')")
        await db.execute("INSERT OR IGNORE INTO settings VALUES ('price_registered', '5.8')")
        await db.execute("INSERT OR IGNORE INTO settings VALUES ('price_unregistered', '4.0')")
        await db.execute("INSERT OR IGNORE INTO settings VALUES ('bot_enabled', '1')")
        await db.execute("INSERT OR IGNORE INTO settings VALUES ('min_withdraw', '1.0')")

        # migrate old price -> registered if needed
        cur = await db.execute("SELECT value FROM settings WHERE key='price'")
        row = await cur.fetchone()
        if row:
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES ('price_registered', ?)",
                (row[0],)
            )

        # migrate legacy price_registered/price_unregistered -> price_max_* (до вставки дефолтов!)
        cur = await db.execute("SELECT value FROM settings WHERE key='price_registered'")
        row = await cur.fetchone()
        if row:
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES ('price_max_registered', ?)",
                (row[0],)
            )
        cur = await db.execute("SELECT value FROM settings WHERE key='price_unregistered'")
        row = await cur.fetchone()
        if row:
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES ('price_max_unregistered', ?)",
                (row[0],)
            )

        # дефолты для новых ключей (сработает только если миграция выше не создала значение)
        await db.execute("INSERT OR IGNORE INTO settings VALUES ('price_max_registered', '5.8')")
        await db.execute("INSERT OR IGNORE INTO settings VALUES ('price_max_unregistered', '4.0')")

        # миграция с предыдущей версии BK (там были подкатегории Рег/Нерег) -> единая цена BK
        cur = await db.execute("SELECT value FROM settings WHERE key='price_bk_registered'")
        row = await cur.fetchone()
        if row:
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES ('price_bk', ?)",
                (row[0],)
            )
        await db.execute("INSERT OR IGNORE INTO settings VALUES ('price_bk', '5.0')")

        # migrate legacy категории заявок (когда существовал только MAX)
        await db.execute("UPDATE numbers SET category='max_registered' WHERE category='registered'")
        await db.execute("UPDATE numbers SET category='max_unregistered' WHERE category='unregistered' OR category IS NULL OR category=''")
        # миграция с предыдущей версии BK (Рег/Нерег) -> единая категория 'bk'
        await db.execute("UPDATE numbers SET category='bk' WHERE category IN ('bk_registered', 'bk_unregistered')")

        for admin_id in ADMIN_IDS:
            await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))
        await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (OWNER_ID,))
        await db.execute("UPDATE users SET approved=1 WHERE user_id=?", (OWNER_ID,))
        for admin_id in ADMIN_IDS:
            await db.execute("UPDATE users SET approved=1 WHERE user_id=?", (admin_id,))
        await db.commit()


async def get_setting(key: str, default: str = "0") -> str:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )
        await db.commit()


async def get_price(category: str) -> float:
    key = f"price_{category}"
    if category == CAT_BK:
        default = "5.0"
    elif category.endswith("_registered") or category == CAT_REG:
        default = "5.8"
    else:
        default = "4.0"
    return float(await get_setting(key, default))


async def is_bot_enabled() -> bool:
    return (await get_setting("bot_enabled", "1")) == "1"


async def get_admins() -> list[int]:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT user_id FROM admins")
        rows = await cur.fetchall()
        ids = [r[0] for r in rows]
        # owner always first
        if OWNER_ID in ids:
            ids = [OWNER_ID] + [i for i in ids if i != OWNER_ID]
        elif OWNER_ID:
            ids = [OWNER_ID] + ids
        return ids


async def get_username(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT username FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row and row[0] else None


async def add_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute("INSERT INTO admins (user_id) VALUES (?)", (user_id,))
            await db.execute("UPDATE users SET approved=1 WHERE user_id=?", (user_id,))
            await db.commit()
            return True
        except Exception:
            return False


async def remove_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return False
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
        await db.commit()
        return cur.rowcount > 0


async def is_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
        return await cur.fetchone() is not None


async def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


async def is_approved(user_id: int) -> bool:
    if await is_admin(user_id):
        return True
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT approved FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return bool(row and row[0])


async def set_subscribed(user_id: int, value: int = 1) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET subscribed=? WHERE user_id=?", (1 if value else 0, user_id))
        await db.commit()


async def set_approved(user_id: int, value: int = 1) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "UPDATE users SET approved=? WHERE user_id=?",
            (value, user_id)
        )
        await db.commit()
        return cur.rowcount > 0


async def ensure_user_record(user_id: int, username: str | None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, approved, subscribed)
            VALUES (?, ?, 1, 0)
            ON CONFLICT(user_id) DO UPDATE SET username=COALESCE(excluded.username, users.username)
            """,
            (user_id, username if username else None)
        )
        if await is_admin(user_id):
            await db.execute(
                "UPDATE users SET approved=1, subscribed=1 WHERE user_id=?",
                (user_id,),
            )
        await db.commit()


async def clear_queue(category: str | None = None) -> int:
    """Удаляет заявки в статусах ожидания. category=None — все."""
    async with aiosqlite.connect(DB_NAME) as db:
        if category:
            cur = await db.execute(
                "DELETE FROM numbers WHERE status IN ('pending','code_requested','code_submitted') AND category=?",
                (category,)
            )
        else:
            cur = await db.execute(
                "DELETE FROM numbers WHERE status IN ('pending','code_requested','code_submitted')"
            )
        await db.commit()
        return cur.rowcount


async def count_queue(category: str | None = None) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        if category:
            cur = await db.execute(
                "SELECT COUNT(*) FROM numbers WHERE status IN ('pending','code_requested','code_submitted') AND category=?",
                (category,)
            )
        else:
            cur = await db.execute(
                "SELECT COUNT(*) FROM numbers WHERE status IN ('pending','code_requested','code_submitted')"
            )
        return (await cur.fetchone())[0]


MAX_SLOTS = 10


async def count_user_active_numbers(user_id: int) -> int:
    """Номера в обработке: pending / code_requested / code_submitted."""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE user_id=? AND status IN ('pending','code_requested','code_submitted')",
            (user_id,),
        )
        row = await cur.fetchone()
        return int(row[0] if row else 0)


async def slots_left(user_id: int) -> tuple[int, int]:
    """(занято, максимум)."""
    used = await count_user_active_numbers(user_id)
    return used, MAX_SLOTS
