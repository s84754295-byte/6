import asyncio
import re

from aiogram.types import CallbackQuery, Message


def validate_phone(number: str) -> bool:
    """Проверяет формат +7XXXXXXXXXX"""
    return bool(re.fullmatch(r"\+7\d{10}", number.strip()))


async def cb_answer(event: CallbackQuery | Message, text: str | None = None, *, alert: bool = False, ttl: float = 60 * 60 * 24 * 365 * 999):
    """
    Ответ на callback с жирным текстом.
    Telegram call.answer() не поддерживает HTML — поэтому:
    1) снимаем «часики» с кнопки через пустой answer()
    2) шлём короткое <b>сообщение</b> и удаляем его через ttl секунд
    Для Message — просто отправляем жирный текст (и удаляем).
    """
    if isinstance(event, CallbackQuery):
        try:
            await event.answer()
        except Exception:
            pass
        if not text:
            return
        try:
            msg = await event.message.answer(f"<b>{text}</b>", parse_mode="HTML")
        except Exception:
            # запасной вариант — нативный тост без HTML
            try:
                await event.answer(text, show_alert=alert)
            except Exception:
                pass
            return

        async def _delete():
            await asyncio.sleep(ttl)
            try:
                await msg.delete()
            except Exception:
                pass

        try:
            asyncio.create_task(_delete())
        except Exception:
            pass
        return

    # Message
    if not text:
        return
    try:
        msg = await event.answer(f"<b>{text}</b>", parse_mode="HTML")

        async def _delete():
            await asyncio.sleep(ttl)
            try:
                await msg.delete()
            except Exception:
                pass

        asyncio.create_task(_delete())
    except Exception:
        pass
