from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, FSInputFile, InputMediaPhoto
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite
import os
import re
import uuid
from datetime import datetime, timezone, timedelta

from config import DB_NAME, OWNER_ID, DEFAULT_ASSET
from keyboards import (
    main_menu, cancel_kb, back_to_main_kb, submit_category_kb, subscribe_kb, support_kb,
    number_request_kb, number_confirm_kb,
    withdraw_confirm_user_kb, back_kb, cancel_numbers_kb, my_numbers_kb
)
from utils import validate_phone, cb_answer
from database import (
    get_setting, is_bot_enabled, is_admin, get_admins,
    ensure_user_record, get_price, count_queue, count_user_active_numbers, CAT_REG, CAT_NEW, CAT_LABEL, set_subscribed, slots_left, MAX_SLOTS,
    claim_next_queued_number, queue_position, get_username,
    try_deduct_balance, refund_balance, create_withdrawal, mark_withdrawal
)
from cryptopay import cp, CryptoPayError
from emojis import tg, T_HOME, T_QUEUE, T_QUEUE_ALL, T_QUEUE_OWN, T_PROFILE, T_SUBMIT, T_MY, T_WITHDRAW, T_OK, T_ERR, T_NEW, T_CODE, T_PAY, T_ACCESS, T_STOP, T_CAT, T_WARN, T_SUPPORT, T_LIST, T_HISTORY_ITEM, T_AMOUNT, T_CLEAR, T_INFO


router = Router()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WELCOME_PHOTO = os.path.join(BASE_DIR, "welcome.jpg")
CHANNEL_ID = "@sobr_channel"
CHANNEL_URL = "https://t.me/sobr_channel"

SUB_REQUIRED_MSG = (
    tg(T_ACCESS, "🔓") + " × <b>Обязательная подписка.</b>\n"
    "━━━━━━━━━━━━━━━━\n"
    "Чтобы пользоваться ботом, подпишитесь на канал ниже.\n"
    "После подписки нажмите «Проверить подписку»."
)


class WithdrawState(StatesGroup):
    waiting_amount = State()


class SubmitNumberState(StatesGroup):
    waiting_number = State()
    waiting_code = State()


def fmt_username(username) -> str:
    """Юзернейм для отображения: @name или @username."""
    if username and str(username).strip() and str(username).strip().lower() not in ("none", "null", "нет"):
        return f"@{username}" if not str(username).startswith("@") else str(username)
    return "@username"


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    """Проверка подписки на обязательный канал."""
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator", "restricted")
    except Exception:
        return False


async def check_access(user_id: int, bot: Bot | None = None) -> tuple[bool, str | None]:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT banned FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
    if row and row[0]:
        return False, tg(T_ERR, "🚫") + " × <b>Доступ ограничен.</b>\n━━━━━━━━━━━━━━━━\nОбратитесь в поддержку."
    if await is_admin(user_id):
        return True, None
    if bot is not None:
        if not await is_subscribed(bot, user_id):
            await set_subscribed(user_id, 0)
            return False, SUB_REQUIRED_MSG
        await set_subscribed(user_id, 1)
    return True, None



BOT_OFF_MSG = (
    tg(T_STOP, "🖥") + " × <b>Бот временно остановлен.</b>\n"
    "━━━━━━━━━━━━━━━━\n"
    "Приём номеров и заявки на вывод приостановлены администратором.\n"
    "Попробуйте позже, когда сервис снова будет включён."
)


async def require_service_on(user_id: int) -> tuple[bool, str | None]:
    """Для обычных пользователей блокирует действия, если бот выключен."""
    if await is_admin(user_id):
        return True, None
    if not await is_bot_enabled():
        return False, BOT_OFF_MSG
    return True, None


async def show_menu(target, text: str, reply_markup, parse_mode="HTML", with_photo: bool = True):
    photo_ok = os.path.exists(WELCOME_PHOTO)
    photo = FSInputFile(WELCOME_PHOTO) if photo_ok else None

    async def _send_text(t):
        if isinstance(t, CallbackQuery):
            try:
                if t.message.photo:
                    await t.message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
                else:
                    await t.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            except Exception:
                try:
                    await t.message.delete()
                except Exception:
                    pass
                await t.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await t.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)

    if isinstance(target, CallbackQuery):
        if photo:
            try:
                await target.message.edit_media(
                    media=InputMediaPhoto(media=photo, caption=text, parse_mode=parse_mode),
                    reply_markup=reply_markup,
                )
            except Exception:
                try:
                    await target.message.delete()
                except Exception:
                    pass
                try:
                    await target.message.answer_photo(photo=photo, caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
                except Exception:
                    await _send_text(target)
        else:
            await _send_text(target)
        try:
            await target.answer()
        except Exception:
            pass
    else:
        if photo:
            try:
                await target.answer_photo(photo=photo, caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
            except Exception:
                await target.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await target.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


async def build_main_menu_text(user_id: int) -> str:
    bot_on = await is_bot_enabled()
    status = "Включён" if bot_on else "Выключен"
    price_new = await get_price(CAT_NEW)
    price_reg = await get_price(CAT_REG)
    queue = await count_queue()
    used, mx = await slots_left(user_id)
    free = max(0, mx - used)
    return (
        tg(T_HOME, "🏠") + " × <b>Главное меню.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"┌ {tg(T_STOP, '🖥')} <b>Статус работы:</b> {status}\n"
        f"├ {tg(T_PAY, '🛒')} <b>Прайс:</b> Нерег - (<code>${price_new:.2f}</code>) | Рег - (<code>${price_reg:.2f}</code>)\n"
        f"├ {tg(T_QUEUE, '🕓')} <b>Очередь номеров:</b> <code>{queue}</code>\n"
        f"└ {tg(T_CAT, '⭐️')} <b>Слотов:</b> <code>{free}/10</code>"
    )


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(call: CallbackQuery, state: FSMContext, bot: Bot):
    await ensure_user_record(call.from_user.id, call.from_user.username)
    if await is_admin(call.from_user.id) or await is_subscribed(bot, call.from_user.id):
        await set_subscribed(call.from_user.id, 1)
        await call.message.answer(
            tg(T_OK, "✅") + " Подписка подтверждена.",
            parse_mode="HTML",
        )
        await cb_answer(call)
        admin = await is_admin(call.from_user.id)
        text = await build_main_menu_text(call.from_user.id)
        await show_menu(call, text, main_menu(call.from_user.id, admin))
    else:
        await set_subscribed(call.from_user.id, 0)
        await call.message.answer(
            tg(T_ERR, "🚫") + " Подписка не найдена.",
            parse_mode="HTML",
        )
        await cb_answer(call)
        try:
            await call.message.edit_text(SUB_REQUIRED_MSG, reply_markup=subscribe_kb(), parse_mode="HTML")
        except Exception:
            await call.message.answer(SUB_REQUIRED_MSG, reply_markup=subscribe_kb(), parse_mode="HTML")


@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext, bot: Bot):
    await state.clear()
    await ensure_user_record(msg.from_user.id, msg.from_user.username)
    ok, err = await check_access(msg.from_user.id, bot)
    if not ok:
        if err == SUB_REQUIRED_MSG:
            await msg.answer(err, reply_markup=subscribe_kb(), parse_mode="HTML")
        else:
            await msg.answer(err, parse_mode="HTML")
        return
    admin = await is_admin(msg.from_user.id)
    display = msg.from_user.first_name or msg.from_user.username or "пользователь"
    text = await build_main_menu_text(msg.from_user.id)
    await show_menu(msg, text, main_menu(msg.from_user.id, admin), with_photo=True)


@router.callback_query(F.data == "main_menu")
async def main_menu_callback(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    ok, err = await check_access(call.from_user.id, bot)
    if not ok:
        kb = subscribe_kb() if err == SUB_REQUIRED_MSG else None
        try:
            if call.message.photo:
                await call.message.edit_caption(caption=err, reply_markup=kb, parse_mode="HTML")
            else:
                await call.message.edit_text(err, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await call.message.answer(err, reply_markup=kb, parse_mode="HTML")
        await call.answer()
        return
    admin = await is_admin(call.from_user.id)
    display = call.from_user.first_name or call.from_user.username or "пользователь"
    text = await build_main_menu_text(call.from_user.id)
    await show_menu(call, text, main_menu(call.from_user.id, admin))


@router.callback_query(F.data == "cancel")
async def cancel_handler(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    ok, err = await check_access(call.from_user.id, bot)
    if not ok:
        await call.answer()
        return
    admin = await is_admin(call.from_user.id)
    display = call.from_user.first_name or call.from_user.username or "пользователь"
    text = await build_main_menu_text(call.from_user.id)
    await show_menu(call, text, main_menu(call.from_user.id, admin))
    await cb_answer(call)




@router.callback_query(F.data == "support")
async def support_callback(call: CallbackQuery, bot: Bot):
    ok, err = await check_access(call.from_user.id, bot)
    if not ok:
        await cb_answer(call)
        return
    text = (
        tg(T_SUPPORT, "🔗") + " × <b>Поддержка.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "Нужна помощь по боту, выплатам или сдаче номеров?\n"
        "Нажмите кнопку ниже — откроется чат с администратором."
    )
    await show_menu(call, text, support_kb())

@router.callback_query(F.data == "public_queue")
async def public_queue_handler(call: CallbackQuery, bot: Bot):
    ok, err = await check_access(call.from_user.id, bot)
    if not ok:
        await cb_answer(call)
        return
    total = await count_queue()
    own = await count_user_active_numbers(call.from_user.id)
    text = (
        tg(T_QUEUE, "🕓") + " × <b>Очередь номеров.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"• {tg(T_QUEUE_ALL, '🧭')} <b>Всего номеров в очереди:</b> <code>{total}</code>\n"
        f"• {tg(T_QUEUE_OWN, '⭐️')} <b>Ваших номеров в очереди:</b> <code>{own}</code>"
    )
    await show_menu(call, text, back_to_main_kb())


@router.callback_query(F.data == "profile")
async def profile_callback(call: CallbackQuery, bot: Bot):
    ok, err = await check_access(call.from_user.id, bot)
    if not ok:
        await cb_answer(call)
        return
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT balance, total, success, failed, subscribed, registered_at FROM users WHERE user_id=?",
            (call.from_user.id,)
        )
        data = await cur.fetchone()
        if not data:
            await show_menu(call, tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\nПользователь не найден.", back_to_main_kb())
            return
        balance, total, success, failed, subscribed, registered_at = data
        cur = await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE user_id=? AND status IN ('pending','code_requested','code_submitted')",
            (call.from_user.id,)
        )
        in_progress = (await cur.fetchone())[0]
    uname = fmt_username(call.from_user.username)
    price_new = await get_price(CAT_NEW)
    price_reg = await get_price(CAT_REG)
    min_w = float(await get_setting("min_withdraw", "1.0"))
    used, mx = await slots_left(call.from_user.id)
    free = max(0, mx - used)
    conversion = (success / total * 100) if total else 0.0
    reg_date = str(registered_at).split(" ")[0] if registered_at else "—"
    sub_status = "Подписан" if subscribed else "Не подписан"
    text = (
        tg(T_PROFILE, "ℹ️") + " × <b>Личный кабинет.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"{tg(T_LIST, '🧑‍💻')} <b>Профиль.</b>\n"
        f"┌ <b>Username:</b> {uname}\n"
        f"├ <b>ID:</b> <code>{call.from_user.id}</code>\n"
        f"├ <b>Регистрация:</b> <code>{reg_date}</code>\n"
        f"└ <b>Подписка на канал:</b> {sub_status}\n"
        "\n"
        f"{tg(T_PAY, '🛒')} <b>Баланс.</b>\n"
        f"┌ <b>Текущий баланс:</b> <code>${balance:.2f}</code>\n"
        f"└ <b>Минимум для вывода:</b> <code>${min_w:.2f}</code>\n"
        "\n"
        f"{tg(T_SUBMIT, '📥')} <b>Ваши заявки.</b>\n"
        f"┌ <b>Всего сдано:</b> <code>{total}</code>\n"
        f"├ <b>Принято:</b> <code>{success}</code>\n"
        f"├ <b>Отклонено:</b> <code>{failed}</code>\n"
        f"├ <b>В обработке сейчас:</b> <code>{in_progress}</code>\n"
        f"└ <b>Конверсия в успешные:</b> <code>{conversion:.1f}%</code>\n"
        "\n"
        f"{tg(T_QUEUE, '🕓')} <b>Слоты и цены.</b>\n"
        f"┌ <b>Свободно слотов:</b> <code>{free}/{mx}</code>\n"
        f"├ <b>Цена • Рег:</b> <code>${price_reg:.2f}</code>\n"
        f"└ <b>Цена • Нерег:</b> <code>${price_new:.2f}</code>"
    )
    await show_menu(call, text, back_to_main_kb())


@router.callback_query(F.data == "submit_menu")
async def submit_menu(call: CallbackQuery, state: FSMContext, bot: Bot):
    ok, err = await check_access(call.from_user.id, bot)
    if not ok:
        await cb_answer(call)
        return
    ok_on, off_msg = await require_service_on(call.from_user.id)
    if not ok_on:
        await cb_answer(call)
        await call.message.answer(off_msg, parse_mode="HTML")
        return
    used, mx = await slots_left(call.from_user.id)
    if used >= mx:
        await cb_answer(call)
        await call.message.answer(
            tg(T_WARN, "⚠️") + " × <b>Лимит слотов.</b>\n━━━━━━━━━━━━━━━━\n"
            f"<b>Все слоты заняты:</b> <code>{used}</code>/<code>{mx}</code>.\n"
            "Дождитесь обработки предыдущих номеров администратором.",
            parse_mode="HTML",
        )
        return
    await state.clear()
    text = (
        tg(T_SUBMIT, "📥") + " × <b>Сдача номера.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "<b>Выберите категорию:</b>"
    )
    await show_menu(call, text, submit_category_kb())


@router.callback_query(F.data.in_({"submit_cat_registered", "submit_cat_unregistered"}))
async def submit_category_chosen(call: CallbackQuery, state: FSMContext, bot: Bot):
    ok, err = await check_access(call.from_user.id, bot)
    if not ok:
        await cb_answer(call)
        return
    ok_on, off_msg = await require_service_on(call.from_user.id)
    if not ok_on:
        await cb_answer(call)
        await call.message.answer(off_msg, parse_mode="HTML")
        return
    if call.data == "submit_cat_registered":
        category = CAT_REG
    else:
        category = CAT_NEW
    price = await get_price(category)
    label = CAT_LABEL[category]
    await state.update_data(category=category)
    text = (
        tg(T_CAT, "⭐️") + f" × <b>Сдача: {label}.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "<b>Формат:</b> <code>+7XXXXXXXXXX</code>\n"
        "<b>Пример:</b> <code>+79991234567</code>"
    )
    await show_menu(call, text, cancel_kb("submit_menu", with_back=False))
    await state.set_state(SubmitNumberState.waiting_number)


async def notify_admins_of_number(bot: Bot, number_id: int, user_id: int, number: str, category: str):
    """Отправляет заявку на номер администраторам (следующая в очереди на обработку)."""
    label = CAT_LABEL.get(category, category)
    admins = await get_admins()
    uname = fmt_username(await get_username(user_id))
    for admin_id in admins:
        try:
            await bot.send_message(
                admin_id,
                tg(T_NEW, "🧪") + f" × <b>Новая заявка №{number_id}.</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                f"<b>От пользователя:</b> {uname}\n"
                f"<b>Категория:</b> {label}\n"
                f"<b>Номер:</b> <code>{number}</code>",
                reply_markup=number_request_kb(number_id, user_id),
                parse_mode="HTML"
            )
        except Exception:
            pass


async def advance_queue(bot: Bot):
    """
    Очередь FIFO: если сейчас никто не обрабатывается — берёт следующий
    номер из очереди и отправляет его администраторам. Вызывается после
    того, как предыдущая заявка закрыта (принята/отклонена/отменена/истекла).
    """
    row = await claim_next_queued_number()
    if not row:
        return
    number_id, user_id, number, category = row
    await notify_admins_of_number(bot, number_id, user_id, number, category)


@router.message(SubmitNumberState.waiting_number, F.text)
async def submit_number_process(msg: Message, state: FSMContext, bot: Bot):
    ok, err = await check_access(msg.from_user.id, bot)
    if not ok:
        await msg.answer(err, parse_mode="HTML")
        await state.clear()
        return
    ok_on, off_msg = await require_service_on(msg.from_user.id)
    if not ok_on:
        await msg.answer(off_msg, parse_mode="HTML")
        await state.clear()
        return
    number = msg.text.strip()
    if not validate_phone(number):
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Неверный формат.</b>\n━━━━━━━━━━━━━━━━\n<b>Формат:</b> <code>+7XXXXXXXXXX</code>",
            reply_markup=cancel_kb("submit_menu", with_back=False),
            parse_mode="HTML"
        )
        return
    used, mx = await slots_left(msg.from_user.id)
    if used >= mx:
        await msg.answer(
            tg(T_WARN, "⚠️") + " × <b>Лимит слотов.</b>\n━━━━━━━━━━━━━━━━\n"
            f"<b>Все слоты заняты:</b> <code>{used}</code>/<code>{mx}</code>.\n"
            "Дождитесь обработки предыдущих номеров администратором.",
            reply_markup=back_to_main_kb(),
            parse_mode="HTML",
        )
        await state.clear()
        return
    data = await state.get_data()
    category = data.get("category", CAT_REG)
    label = CAT_LABEL.get(category, category)
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT status FROM numbers WHERE number=? AND status IN ('pending','code_requested','code_submitted','accepted') "
            "ORDER BY id DESC LIMIT 1",
            (number,)
        )
        dup = await cur.fetchone()
        if dup:
            await msg.answer(
                tg(T_ERR, "🚫") + " × <b>Номер уже был сдан.</b>\n━━━━━━━━━━━━━━━━\n"
                f"<b>Номер:</b> <code>{number}</code>",
                reply_markup=back_to_main_kb(), parse_mode="HTML"
            )
            await state.clear()
            return
        price_at_submit = await get_price(category)
        await db.execute(
            "INSERT INTO numbers (user_id, number, status, category, notified_admin, price) VALUES (?, ?, 'pending', ?, 0, ?)",
            (msg.from_user.id, number, category, price_at_submit)
        )
        await db.execute("UPDATE users SET total = total + 1 WHERE user_id=?", (msg.from_user.id,))
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid()")
        number_id = (await cur.fetchone())[0]

    await advance_queue(bot)
    position = await queue_position(number_id)

    used2, mx2 = await slots_left(msg.from_user.id)
    free2 = max(0, mx2 - used2)
    text = (
        tg(T_OK, "✅") + " × <b>Номер отправлен.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"<b>Позиция в очереди:</b> <code>{position}</code>"
    )
    await msg.answer(text, reply_markup=back_to_main_kb(), parse_mode="HTML")
    await state.clear()


async def _accept_code(msg: Message, bot: Bot, number_id: int, number: str, code: str, state: FSMContext | None = None):
    """Общая логика принятия валидного кода."""
    cat_label = ""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT status, category FROM numbers WHERE id=? AND user_id=?", (number_id, msg.from_user.id))
        row = await cur.fetchone()
        if not row or row[0] != "code_requested":
            await msg.answer(tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\nЗаявка уже обработана.", reply_markup=back_to_main_kb(), parse_mode="HTML")
            if state:
                await state.clear()
            return False
        cat_label = CAT_LABEL.get(row[1] or CAT_REG, row[1] or "")
        await db.execute("UPDATE numbers SET status='code_submitted', code=? WHERE id=?", (code, number_id))
        await db.commit()
    admins = await get_admins()
    uname = fmt_username(msg.from_user.username)
    for admin_id in admins:
        try:
            await bot.send_message(
                admin_id,
                tg(T_CODE, "📨") + f" × <b>Новая заявка №{number_id}.</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                f"<b>От пользователя:</b> {uname}\n"
                f"<b>Категория:</b> {cat_label}\n"
                f"<b>Номер:</b> <code>{number}</code>\n"
                f"<b>Код:</b> <code>{code}</code>",
                reply_markup=number_confirm_kb(number_id, msg.from_user.id),
                parse_mode="HTML"
            )
        except Exception:
            pass
    await msg.answer(tg(T_OK, "✅") + " × <b>Код отправлен.</b>\n━━━━━━━━━━━━━━━━\nОжидайте подтверждение администратором.", reply_markup=back_to_main_kb(), parse_mode="HTML")
    if state:
        await state.clear()
    return True


def _is_valid_six_digit_code(text: str) -> bool:
    return bool(text) and len(text) == 6 and text.isdigit()


@router.message(SubmitNumberState.waiting_code, F.text)
async def submit_code_process(msg: Message, state: FSMContext, bot: Bot):
    ok, err = await check_access(msg.from_user.id, bot)
    if not ok:
        await msg.answer(err, parse_mode="HTML")
        await state.clear()
        return
    data = await state.get_data()
    number_id = data.get("number_id")
    number = data.get("number", "")
    code = (msg.text or "").strip()
    if not number_id:
        await msg.answer(tg(T_ERR, "🚫") + " × <b>Сессия истекла.</b>\n━━━━━━━━━━━━━━━━\nСессия истекла.", reply_markup=back_to_main_kb(), parse_mode="HTML")
        await state.clear()
        return
    # Обязателен ответ на сообщение с запросом кода
    if not msg.reply_to_message:
        await msg.answer(
            tg(T_WARN, "⚠️") + " × <b>Код не принят.</b>\n━━━━━━━━━━━━━━━━\n"
            "Отправьте код ответом на сообщение с запросом кода.",
            parse_mode="HTML",
        )
        return
    if not _is_valid_six_digit_code(code):
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Неверный код.</b>\n━━━━━━━━━━━━━━━━\n"
            "Код должен состоять ровно из 6 цифр.",
            parse_mode="HTML",
        )
        return
    await _accept_code(msg, bot, number_id, number, code, state)


@router.message(F.text, StateFilter(None))
async def maybe_code_message(msg: Message, state: FSMContext, bot: Bot):
    """Принимает код только как ответ на сообщение с запросом кода, ровно 6 цифр, в течение 2 минут."""
    ok, err = await check_access(msg.from_user.id, bot)
    if not ok:
        return

    text = (msg.text or "").strip()

    # Есть активный запрос кода у пользователя?
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT id, number, code_msg_id, code_requested_at FROM numbers "
            "WHERE user_id=? AND status='code_requested' ORDER BY id DESC LIMIT 1",
            (msg.from_user.id,),
        )
        row = await cur.fetchone()

    if not row:
        return

    number_id, number, code_msg_id, code_requested_at = row

    # Код принимается ТОЛЬКО ответом на сообщение запроса
    if not msg.reply_to_message:
        # Если похоже на код — подсказать
        if text.isdigit() or (len(text) <= 10 and any(c.isdigit() for c in text)):
            await msg.answer(
                tg(T_WARN, "⚠️") + " × <b>Код не принят.</b>\n━━━━━━━━━━━━━━━━\n"
                "Отправьте код ответом на сообщение с запросом кода.",
                parse_mode="HTML",
            )
        return

    # Проверяем, что ответ именно на наше сообщение с запросом
    if code_msg_id and msg.reply_to_message.message_id != code_msg_id:
        await msg.answer(
            tg(T_WARN, "⚠️") + " × <b>Код не принят.</b>\n━━━━━━━━━━━━━━━━\n"
            "Ответьте именно на сообщение с запросом кода "
            f"(номер <code>{number}</code>).",
            parse_mode="HTML",
        )
        return

    # Таймаут 2 минуты
    if code_requested_at:
        try:
            requested = datetime.fromisoformat(code_requested_at)
            if requested.tzinfo is None:
                requested = requested.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - requested > timedelta(minutes=2):
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute(
                        "UPDATE numbers SET status='rejected' WHERE id=? AND status='code_requested'",
                        (number_id,),
                    )
                    await db.execute("UPDATE users SET failed = failed + 1 WHERE user_id=?", (msg.from_user.id,))
                    await db.commit()
                await advance_queue(bot)
                await msg.answer(
                    tg(T_WARN, "⚠️") + " × <b>Время истекло.</b>\n━━━━━━━━━━━━━━━━\n"
                    f"<b>Номер:</b> <code>{number}</code>\n"
                    "Время на ввод кода истекло, заявка отменена.\n"
                    "Вы можете сдать этот номер повторно.",
                    reply_markup=back_to_main_kb(),
                    parse_mode="HTML",
                )
                return
        except Exception:
            pass

    if not _is_valid_six_digit_code(text):
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Неверный код.</b>\n━━━━━━━━━━━━━━━━\n"
            "Код должен состоять ровно из 6 цифр.",
            parse_mode="HTML",
        )
        return

    await _accept_code(msg, bot, number_id, number, text, state)


HISTORY_PAGE_SIZE = 28


@router.callback_query(F.data == "my_numbers")
async def my_numbers(call: CallbackQuery, bot: Bot):
    await my_numbers_page(call, bot, page=1)


@router.callback_query(F.data.regexp(r"^my_numbers_page_\d+$"))
async def my_numbers_page_callback(call: CallbackQuery, bot: Bot):
    page = int(call.data.rsplit("_", 1)[1])
    await my_numbers_page(call, bot, page=page)


async def my_numbers_page(call: CallbackQuery, bot: Bot, page: int):
    ok, err = await check_access(call.from_user.id, bot)
    if not ok:
        await cb_answer(call)
        return
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT COUNT(*) FROM numbers WHERE user_id=?", (call.from_user.id,))
        total = (await cur.fetchone())[0]
        if total == 0:
            await show_menu(
                call,
                tg(T_MY, "📚") + " × <b>История номеров.</b>\n━━━━━━━━━━━━━━━━\nПока нет сданных номеров.",
                back_to_main_kb(),
            )
            return
        total_pages = max(1, (total + HISTORY_PAGE_SIZE - 1) // HISTORY_PAGE_SIZE)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * HISTORY_PAGE_SIZE
        cur = await db.execute(
            "SELECT number, code, price, category, status FROM numbers WHERE user_id=? ORDER BY id ASC LIMIT ? OFFSET ?",
            (call.from_user.id, HISTORY_PAGE_SIZE, offset)
        )
        rows = await cur.fetchall()
    text = tg(T_MY, "📚") + " × <b>История номеров.</b>\n━━━━━━━━━━━━━━━━\n"
    for num, code, price, cat, status in rows:
        code_s = code if code else "123456"
        if status in ("rejected", "cancelled"):
            price = 0.0
        elif price is None:
            price = await get_price(cat or CAT_REG)
        text += f"<code>{num}</code> — <code>{code_s}</code> — <code>${price:.2f}</code>\n"
    await show_menu(call, text, my_numbers_kb(page, total_pages))


@router.callback_query(F.data == "cancel_menu")
async def cancel_menu(call: CallbackQuery, bot: Bot):
    ok, err = await check_access(call.from_user.id, bot)
    if not ok:
        await cb_answer(call)
        return
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            SELECT id, number, seq FROM (
                SELECT id, number, status,
                       ROW_NUMBER() OVER (ORDER BY id ASC) AS seq
                FROM numbers
                WHERE user_id=?
            )
            WHERE status='pending'
            ORDER BY id ASC
            """,
            (call.from_user.id,)
        )
        rows = await cur.fetchall()
    if not rows:
        await show_menu(
            call,
            tg(T_CLEAR, "🗑") + " × <b>Отмена заявки.</b>\n━━━━━━━━━━━━━━━━\n"
            "Сейчас у вас нету доступных заявок на отмену.",
            back_to_main_kb(),
        )
        return
    text = (
        tg(T_CLEAR, "🗑") + " × <b>Отмена заявки.</b>\n━━━━━━━━━━━━━━━━\n"
        "<b>Выберите заявку, которую хотите отменить:</b>"
    )
    await show_menu(call, text, cancel_numbers_kb(rows))


@router.callback_query(F.data.regexp(r"^user_cancel_\d+$"))
async def user_cancel_number(call: CallbackQuery, bot: Bot):
    ok, err = await check_access(call.from_user.id, bot)
    if not ok:
        await cb_answer(call)
        return
    number_id = int(call.data.split("_")[2])
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT number, status, notified_admin FROM numbers WHERE id=? AND user_id=?",
            (number_id, call.from_user.id),
        )
        row = await cur.fetchone()
        if not row or row[1] != "pending":
            await cb_answer(call)
            await call.message.answer(
                tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\n"
                "Эту заявку уже нельзя отменить — она в обработке или уже закрыта.",
                parse_mode="HTML",
            )
            return
        number, _, notified_admin = row
        cur = await db.execute(
            "UPDATE numbers SET status='cancelled' WHERE id=? AND status='pending'",
            (number_id,),
        )
        if cur.rowcount == 0:
            await cb_answer(call)
            return
        await db.execute("UPDATE users SET failed = failed + 1 WHERE user_id=?", (call.from_user.id,))
        await db.commit()
    if notified_admin:
        await advance_queue(bot)
        admins = await get_admins()
        for admin_id in admins:
            try:
                await bot.send_message(
                    admin_id,
                    tg(T_INFO, "🔔") + " × <b>Заявка отменена пользователем.</b>\n"
                    "━━━━━━━━━━━━━━━━\n"
                    f"<b>Номер:</b> <code>{number}</code>",
                    parse_mode="HTML",
                )
            except Exception:
                pass
    await cb_answer(call)
    text = (
        tg(T_OK, "✅") + " × <b>Заявка отменена.</b>\n━━━━━━━━━━━━━━━━\n"
        f"<b>Номер:</b> <code>{number}</code>"
    )
    await show_menu(call, text, back_to_main_kb())


@router.callback_query(F.data == "withdraw")
async def withdraw_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    ok, err = await check_access(call.from_user.id, bot)
    if not ok:
        await cb_answer(call)
        return
    ok_on, off_msg = await require_service_on(call.from_user.id)
    if not ok_on:
        await cb_answer(call)
        await call.message.answer(off_msg, parse_mode="HTML")
        return
    min_w = float(await get_setting("min_withdraw", "1.0"))
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT balance FROM users WHERE user_id=?", (call.from_user.id,))
        data = await cur.fetchone()
        if not data or data[0] < min_w:
            bal = data[0] if data else 0
            text = (
                tg(T_ERR, "🚫") + " × <b>Недостаточно средств.</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                f"• {tg(T_WARN, '⚠️')} <b>Минимум:</b> <code>${min_w:.2f}</code>\n"
                f"• {tg(T_PAY, '🛒')} <b>Баланс:</b> <code>${bal:.2f}</code>"
            )
            await show_menu(call, text, back_to_main_kb())
            return
        text = (
            tg(T_WITHDRAW, "💼") + " × <b>Вывод средств.</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "Деньги придут мгновенно на ваш кошелёк в @CryptoBot.\n"
            f"{tg(T_AMOUNT, '👝')} <b>Введите сумму вывода:</b>"
        )
        await show_menu(call, text, cancel_kb())
        await state.set_state(WithdrawState.waiting_amount)


@router.message(WithdrawState.waiting_amount, F.text)
async def withdraw_amount(msg: Message, state: FSMContext, bot: Bot):
    ok, err = await check_access(msg.from_user.id, bot)
    if not ok:
        await msg.answer(err, parse_mode="HTML")
        await state.clear()
        return
    min_w = float(await get_setting("min_withdraw", "1.0"))
    try:
        amount = float(msg.text.replace(",", ".").strip())
        if amount < min_w:
            raise ValueError
    except ValueError:
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\n"
            f"<b>Минимум:</b> <code>${min_w:.2f}</code>",
            reply_markup=cancel_kb(), parse_mode="HTML"
        )
        return
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT balance FROM users WHERE user_id=?", (msg.from_user.id,))
        balance = (await cur.fetchone())[0]
        if amount > balance:
            await msg.answer(
                tg(T_ERR, "🚫") + " × <b>Недостаточно средств.</b>\n━━━━━━━━━━━━━━━━\n"
                f"{tg(T_PAY, '🛒')} <b>Баланс:</b> <code>${balance:.2f}</code>",
                reply_markup=back_to_main_kb(), parse_mode="HTML"
            )
            await state.clear()
            return
    await state.update_data(amount=amount, balance=balance)
    await msg.answer(
        tg(T_PAY, "🛒") + " × <b>Проверьте заявку.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"<b>Сумма:</b> <code>${amount:.2f}</code>\n"
        f"<b>Баланс:</b> <code>${balance:.2f}</code>",
        reply_markup=withdraw_confirm_user_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "withdraw_user_yes")
async def withdraw_user_confirm(call: CallbackQuery, state: FSMContext, bot: Bot):
    ok, err = await check_access(call.from_user.id, bot)
    if not ok:
        await cb_answer(call)
        return
    ok_on, off_msg = await require_service_on(call.from_user.id)
    if not ok_on:
        await cb_answer(call)
        await call.message.answer(off_msg, parse_mode="HTML")
        await state.clear()
        return
    data = await state.get_data()
    amount = data.get("amount")
    if amount is None:
        await cb_answer(call)
        await state.clear()
        return
    amount = float(amount)
    user_id = call.from_user.id

    # 1. Атомарно списываем виртуальный баланс ДО реального перевода —
    #    чтобы пользователь не смог вывести больше, чем у него есть.
    ok_ded = await try_deduct_balance(user_id, amount)
    if not ok_ded:
        async with aiosqlite.connect(DB_NAME) as db:
            cur = await db.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
        balance = row[0] if row else 0
        await call.message.edit_text(
            tg(T_ERR, "🚫") + " × <b>Недостаточно средств.</b>\n━━━━━━━━━━━━━━━━\n"
            f"{tg(T_PAY, '🛒')} <b>Баланс:</b> <code>${balance:.2f}</code>",
            reply_markup=back_to_main_kb(), parse_mode="HTML"
        )
        await state.clear()
        await call.answer()
        return

    # 2. Идемпотентный ключ генерируется и сохраняется ДО вызова transfer,
    #    чтобы при обрыве соединения повторный вызов не отправил деньги дважды.
    spend_id = uuid.uuid4().hex
    withdrawal_id = await create_withdrawal(user_id, amount, DEFAULT_ASSET, spend_id)

    processing_text = (
        tg(T_WITHDRAW, "💼") + " × <b>Обрабатываем вывод.</b>\n━━━━━━━━━━━━━━━━\n"
        f"<b>Сумма:</b> <code>${amount:.2f}</code>\n"
        "Отправляем на ваш кошелёк в @CryptoBot..."
    )
    try:
        await call.message.edit_text(processing_text, parse_mode="HTML")
    except Exception:
        pass

    # 3. Реальная мгновенная отправка денег из казны на кошелёк пользователя в @CryptoBot.
    try:
        await cp.transfer(
            user_id=user_id,
            asset=DEFAULT_ASSET,
            amount=amount,
            spend_id=spend_id,
            comment="Вывод средств",
        )
    except CryptoPayError as e:
        await refund_balance(user_id, amount)
        await mark_withdrawal(withdrawal_id, "failed", str(e.message))
        if e.code == 400 and isinstance(e.message, str) and "USER_NOT_FOUND" in e.message.upper():
            fail_text = (
                tg(T_ERR, "🚫") + " × <b>Не удалось выполнить вывод.</b>\n━━━━━━━━━━━━━━━━\n"
                "Похоже, вы ни разу не открывали @CryptoBot.\n"
                "Откройте его, нажмите /start, затем повторите вывод.\n"
                f"<code>${amount:.2f}</code> возвращено на баланс."
            )
        else:
            fail_text = (
                tg(T_ERR, "🚫") + " × <b>Не удалось выполнить вывод.</b>\n━━━━━━━━━━━━━━━━\n"
                f"<code>${amount:.2f}</code> возвращено на баланс."
            )
        try:
            await call.message.edit_text(fail_text, reply_markup=back_to_main_kb(), parse_mode="HTML")
        except Exception:
            await call.message.answer(fail_text, reply_markup=back_to_main_kb(), parse_mode="HTML")
        for admin_id in await get_admins():
            try:
                await bot.send_message(
                    admin_id,
                    tg(T_ERR, "🚫") + " × <b>Вывод не выполнен.</b>\n━━━━━━━━━━━━━━━━\n"
                    f"<b>От пользователя:</b> {fmt_username(call.from_user.username)}\n"
                    f"<b>Сумма:</b> <code>${amount:.2f}</code>\n"
                    f"<b>Ошибка:</b> <code>{e.message}</code>",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        await state.clear()
        await cb_answer(call)
        return

    await mark_withdrawal(withdrawal_id, "success")
    ok_text = (
        tg(T_OK, "✅") + " × <b>Готово.</b>\n━━━━━━━━━━━━━━━━\n"
        f"<b>Сумма:</b> <code>${amount:.2f}</code>\n"
        "Отправлено на ваш кошелёк в @CryptoBot."
    )
    try:
        await call.message.edit_text(ok_text, reply_markup=back_to_main_kb(), parse_mode="HTML")
    except Exception:
        await call.message.answer(ok_text, reply_markup=back_to_main_kb(), parse_mode="HTML")
    for admin_id in await get_admins():
        try:
            await bot.send_message(
                admin_id,
                tg(T_WITHDRAW, "💼") + " × <b>Автовыплата выполнена.</b>\n━━━━━━━━━━━━━━━━\n"
                f"<b>От пользователя:</b> {fmt_username(call.from_user.username)}\n"
                f"<b>Сумма:</b> <code>${amount:.2f}</code>",
                parse_mode="HTML",
            )
        except Exception:
            pass
    await state.clear()
    await cb_answer(call)


@router.callback_query(F.data == "withdraw_user_no")
async def withdraw_user_cancel(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    admin = await is_admin(call.from_user.id)
    display = call.from_user.first_name or call.from_user.username or "пользователь"
    text = await build_main_menu_text(call.from_user.id)
    await show_menu(call, text, main_menu(call.from_user.id, admin))
    await cb_answer(call)
