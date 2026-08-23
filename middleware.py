import time
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery


class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 8, delay: float = 1.0):
        self.limit = limit
        self.delay = delay
        self.users: dict[int, tuple[float, int]] = {}

    async def __call__(self, handler, event, data):
        user = None
        if isinstance(event, Message) and event.from_user:
            user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            user = event.from_user

        if user:
            user_id = user.id
            now = time.monotonic()

            if user_id in self.users:
                last_time, count = self.users[user_id]
                if now - last_time < self.delay:
                    if count >= self.limit:
                        if isinstance(event, Message):
                            await event.answer("<b>Подождите секунду…</b>", parse_mode="HTML")
                        elif isinstance(event, CallbackQuery):
                            await event.answer("Слишком быстро", show_alert=False)
                        return
                    self.users[user_id] = (last_time, count + 1)
                else:
                    self.users[user_id] = (now, 1)
            else:
                self.users[user_id] = (now, 1)

        return await handler(event, data)
