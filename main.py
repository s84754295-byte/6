import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, OWNER_ID
from database import init_db, get_admins, expire_code_requests, expire_admin_pending
from middleware import AntiFloodMiddleware
from emojis import tg, T_WARN
import user
import admin

logging.basicConfig(level=logging.INFO)


async def code_expiry_watcher(bot: Bot):
    """Каждые 15 секунд отменяет заявки, где истекло время на ввод кода,
    и заявки, которые админ не открыл (не запросил код) слишком долго."""
    while True:
        try:
            expired = await expire_code_requests()
            for number_id, user_id, number in expired:
                await user.advance_queue(bot)
                try:
                    await bot.send_message(
                        user_id,
                        tg(T_WARN, "⚠️") + " × <b>Время истекло.</b>\n━━━━━━━━━━━━━━━━\n"
                        f"<b>Номер:</b> <code>{number}</code>\n"
                        "Время на ввод кода истекло, заявка отменена.\n"
                        "Вы можете сдать этот номер повторно.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

            expired_admin = await expire_admin_pending()
            for number_id, user_id, number in expired_admin:
                await user.advance_queue(bot)
                try:
                    await bot.send_message(
                        user_id,
                        tg(T_WARN, "⚠️") + " × <b>Время истекло.</b>\n━━━━━━━━━━━━━━━━\n"
                        f"<b>Номер:</b> <code>{number}</code>\n"
                        "Администратор не отреагировал на заявку вовремя, она отменена.\n"
                        "Вы можете сдать этот номер повторно.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
        except Exception:
            logging.exception("code_expiry_watcher error")
        await asyncio.sleep(15)


async def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Укажите BOT_TOKEN в файле .env")
        return

    if not OWNER_ID or OWNER_ID == 0:
        print("Укажите OWNER_ID в файле .env")
        return

    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(AntiFloodMiddleware(limit=10, delay=1.0))
    dp.callback_query.middleware(AntiFloodMiddleware(limit=15, delay=0.5))

    dp.include_router(admin.router)
    dp.include_router(user.router)

    admins = await get_admins()
    print("Bot started!")
    print(f"Владелец: {OWNER_ID}")
    print(f"Админы: {admins}")

    asyncio.create_task(code_expiry_watcher(bot))

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
