import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, OWNER_ID
from database import init_db, get_admins
from middleware import AntiFloodMiddleware
import user
import admin

logging.basicConfig(level=logging.INFO)


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

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
