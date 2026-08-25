import aiosqlite
from datetime import datetime, timezone, timedelta
from config import DB_NAME, OWNER_ID, ADMIN_IDS

# category: 'registered' | 'unregistered'
CAT_REG = "registered"
CAT_NEW = "unregistered"
CAT_LABEL = {
    CAT_REG: "MAX • Рег",
    CAT_NEW: "MAX • Нерег",
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
        try:
            await db.execute("ALTER TABLE numbers ADD COLUMN notified_admin INTEGER DEFAULT 0")
            # существующие "живые" заявки уже были показаны админу по старой логике —
            # помечаем их как активные, чтобы не сломать уже идущую обработку
            await db.execute(
                "UPDATE numbers SET notified_admin=1 WHERE status IN ('pending','code_requested','code_submitted')"
            )
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE numbers ADD COLUMN price REAL")
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
        for col, coldef in [
            ("spend_id", "TEXT"),
            ("asset", "TEXT DEFAULT 'USDT'"),
            ("error", "TEXT"),
        ]:
            try:
                await db.execute(f"ALTER TABLE withdrawals ADD COLUMN {col} {coldef}")
            except Exception:
                pass
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
    key = "price_registered" if category == CAT_REG else "price_unregistered"
    return float(await get_setting(key, "5.8" if category == CAT_REG else "4.0"))


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


async def claim_next_queued_number():
    """
    Очередь FIFO: только один номер одновременно "активен" (показан админам).
    Если сейчас никто не обрабатывается — забирает следующий по очереди номер
    (самый старый неотправленный админам) и помечает его активным.
    Возвращает (id, user_id, number, category) или None.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE notified_admin=1 AND status IN ('pending','code_requested','code_submitted')"
        )
        active = (await cur.fetchone())[0]
        if active > 0:
            return None
        cur = await db.execute(
            "SELECT id, user_id, number, category FROM numbers "
            "WHERE status='pending' AND notified_admin=0 ORDER BY id ASC LIMIT 1"
        )
        row = await cur.fetchone()
        if not row:
            return None
        number_id = row[0]
        await db.execute("UPDATE numbers SET notified_admin=1 WHERE id=?", (number_id,))
        await db.commit()
        return row


async def queue_position(number_id: int) -> int:
    """Позиция заявки в общей очереди обработки (1 = сейчас обрабатывается/следующая)."""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status IN ('pending','code_requested','code_submitted') AND id<=?",
            (number_id,),
        )
        row = await cur.fetchone()
        return int(row[0] if row else 1)


CODE_TIMEOUT_MINUTES = 2


async def expire_code_requests() -> list[tuple[int, int, str]]:
    """
    Находит заявки в статусе 'code_requested', у которых истекло время на ввод кода,
    автоматически отклоняет их (status='rejected') — освобождая слот и номер для
    повторной сдачи, и возвращает список (number_id, user_id, number) для уведомления.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT id, user_id, number, code_requested_at FROM numbers WHERE status='code_requested'"
        )
        rows = await cur.fetchall()
        expired = []
        now = datetime.now(timezone.utc)
        for number_id, user_id, number, requested_at in rows:
            if not requested_at:
                continue
            try:
                requested = datetime.fromisoformat(requested_at)
                if requested.tzinfo is None:
                    requested = requested.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if now - requested > timedelta(minutes=CODE_TIMEOUT_MINUTES):
                expired.append((number_id, user_id, number))
        if expired:
            ids = [e[0] for e in expired]
            placeholders = ",".join("?" * len(ids))
            await db.execute(
                f"UPDATE numbers SET status='rejected' WHERE id IN ({placeholders}) AND status='code_requested'",
                ids,
            )
            for _, user_id, _ in expired:
                await db.execute("UPDATE users SET failed = failed + 1 WHERE user_id=?", (user_id,))
            await db.commit()
        return expired


# ---------- Казна: атомарные операции с виртуальным балансом и историей выводов ----------

async def try_deduct_balance(user_id: int, amount: float) -> bool:
    """
    Атомарно списывает виртуальный баланс, только если денег хватает.
    Вызывается ДО отправки реального перевода через CryptoPay, чтобы пользователь
    не смог вывести больше, чем у него есть, даже при параллельных запросах.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?",
            (amount, user_id, amount),
        )
        await db.commit()
        return cur.rowcount > 0


async def refund_balance(user_id: int, amount: float) -> None:
    """Возвращает деньги на виртуальный баланс, если реальный перевод не удался."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        await db.commit()


async def create_withdrawal(user_id: int, amount: float, asset: str, spend_id: str) -> int:
    """Создаёт запись о выводе со статусом 'processing' ДО вызова transfer() — идемпотентность."""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "INSERT INTO withdrawals (user_id, amount, status, asset, spend_id) VALUES (?, ?, 'processing', ?, ?)",
            (user_id, amount, asset, spend_id),
        )
        await db.commit()
        return cur.lastrowid


async def mark_withdrawal(withdrawal_id: int, status: str, error: str | None = None) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE withdrawals SET status=?, error=? WHERE id=?",
            (status, error, withdrawal_id),
        )
        await db.commit()


async def get_treasury_stats() -> dict:
    """Статистика по выводам для админского экрана 'Казна' (сверка с реальным балансом приложения)."""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM withdrawals WHERE status='success'")
        n_success, sum_success = await cur.fetchone()
        cur = await db.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM withdrawals WHERE status='failed'")
        n_failed, sum_failed = await cur.fetchone()
        cur = await db.execute("SELECT COUNT(*) FROM withdrawals WHERE status='processing'")
        n_processing = (await cur.fetchone())[0]
        cur = await db.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount),0) FROM withdrawals "
            "WHERE status='success' AND created_at >= datetime('now','-1 day')"
        )
        n_24h, sum_24h = await cur.fetchone()
        cur = await db.execute("SELECT COALESCE(SUM(balance),0) FROM users")
        total_balance = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(DISTINCT user_id) FROM withdrawals WHERE status='success'")
        n_users = (await cur.fetchone())[0]
    avg = (sum_success / n_success) if n_success else 0.0
    return {
        "n_success": n_success, "sum_success": sum_success,
        "n_failed": n_failed, "sum_failed": sum_failed,
        "n_processing": n_processing,
        "n_24h": n_24h, "sum_24h": sum_24h,
        "total_balance": total_balance,
        "n_users": n_users,
        "avg": avg,
    }
