from aiogram.filters import Command, CommandObject
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, FSInputFile, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite
from datetime import datetime, timezone
import os

from config import DB_NAME, OWNER_ID
from utils import cb_answer
from keyboards import (
    admin_panel_kb, back_to_admin_kb, cancel_kb, back_kb, price_menu_kb,
    access_panel_kb, number_request_kb, number_confirm_kb,
    categories_menu_kb,
    clear_queue_confirm_kb, grant_all_confirm_kb, revoke_all_confirm_kb
)
from emojis import tg, T_HOME, T_ADMIN, T_QUEUE, T_OK, T_ERR, T_NEW, T_CODE, T_PAY, T_ACCESS, T_STATS, T_LIST, T_BROADCAST, T_PRICE, T_STOP, T_CLEAR, T_WARN, T_USERS, T_PROFILE, T_INFO, T_CHECK, T_SUBMIT, T_WITHDRAW, T_CAT
from database import (
    get_setting, set_setting, is_admin, is_owner,
    get_admins, add_admin, remove_admin, is_bot_enabled,
    is_category_enabled, set_category_enabled,
    set_approved, ensure_user_record, get_price, clear_queue, count_queue,
    get_username, get_treasury_stats, set_banned, is_banned,
    CAT_REG, CAT_NEW, CAT_LABEL
)
from cryptopay import cp, CryptoPayError
from config import DEFAULT_ASSET
from user import advance_queue

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WELCOME_PHOTO = os.path.join(BASE_DIR, "welcome.jpg")
router = Router()


class AdminStates(StatesGroup):
    waiting_price_registered = State()
    waiting_price_unregistered = State()
    waiting_min_withdraw = State()
    waiting_broadcast = State()
    waiting_grant_access = State()
    waiting_revoke_access = State()
    waiting_ban_user = State()
    waiting_unban_user = State()


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


async def safe_edit(call: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    try:
        if call.message.photo:
            await call.message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await call.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        try:
            await call.message.delete()
        except Exception:
            pass
        try:
            await call.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            pass
    try:
        await call.answer()
    except Exception:
        pass


async def require_admin(call_or_msg) -> bool:
    user_id = call_or_msg.from_user.id
    if not await is_admin(user_id):
        await cb_answer(call_or_msg)
        return False
    return True




async def build_admin_panel_text() -> str:
    bot_on = await is_bot_enabled()
    status = "Включён" if bot_on else "Выключен"
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT COUNT(*) FROM numbers WHERE status='accepted'")
        accepted = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM numbers WHERE status IN ('rejected','cancelled')")
        rejected = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM numbers")
        total_numbers = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COALESCE(SUM(amount),0) FROM withdrawals WHERE status='success'")
        paid_sum = (await cur.fetchone())[0]
        cur = await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status='accepted' AND category='registered'"
        )
        acc_reg = (await cur.fetchone())[0]
        cur = await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status='accepted' AND (category='unregistered' OR category IS NULL OR category='')"
        )
        acc_new = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE banned=1")
        banned_count = (await cur.fetchone())[0]
    price_reg = await get_price(CAT_REG)
    price_new = await get_price(CAT_NEW)
    earned_est = acc_reg * price_reg + acc_new * price_new
    return (
        tg(T_ADMIN, "🛡") + " × <b>Админ-панель.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"┌ {tg(T_STOP, '🖥')} <b>Статус:</b> {status}\n"
        f"├ {tg(T_OK, '✅')} <b>Успешных номеров:</b> <code>{accepted}</code>\n"
        f"├ {tg(T_ERR, '🚫')} <b>Отклонённых:</b> <code>{rejected}</code>\n"
        f"├ {tg(T_SUBMIT, '📥')} <b>Всего сдано:</b> <code>{total_numbers}</code>\n"
        f"├ {tg(T_PAY, '🛒')} <b>Оборот (оценка):</b> <code>${earned_est:.2f}</code>\n"
        f"├ {tg(T_WITHDRAW, '💼')} <b>Выплачено:</b> <code>${paid_sum:.2f}</code>\n"
        f"└ {tg(T_WARN, '⚠️')} <b>Заблокировано:</b> <code>{banned_count}</code>"
    )


@router.message(Command("cc"))
async def control_cmd(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id):
        return
    await state.clear()
    bot_on = await is_bot_enabled()
    owner = await is_owner(msg.from_user.id)
    text = await build_admin_panel_text()
    await show_menu(msg, text, admin_panel_kb(is_owner=owner, bot_enabled=bot_on))


@router.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        await cb_answer(call)
        return
    await state.clear()
    bot_on = await is_bot_enabled()
    owner = await is_owner(call.from_user.id)
    text = await build_admin_panel_text()
    await show_menu(call, text, admin_panel_kb(is_owner=owner, bot_enabled=bot_on))


@router.callback_query(F.data == "bot_stop")
async def bot_stop(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        await cb_answer(call)
        return
    await set_setting("bot_enabled", "0")
    await show_categories_menu(call)
    await cb_answer(call)


@router.callback_query(F.data == "bot_start")
async def bot_start(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        await cb_answer(call)
        return
    await set_setting("bot_enabled", "1")
    await show_categories_menu(call)
    await cb_answer(call)


# ---------- Категории: запуск/остановка приёма номеров ----------
async def show_categories_menu(call: CallbackQuery):
    bot_on = await is_bot_enabled()
    reg_on = await is_category_enabled(CAT_REG)
    new_on = await is_category_enabled(CAT_NEW)
    text = (
        tg(T_STOP, "🖥") + " × <b>Категории.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"┌ <b>Весь бот:</b> {'Включён' if bot_on else 'Выключен'}\n"
        f"├ <b>MAX • Рег:</b> {'Включена' if reg_on else 'Выключена'}\n"
        f"└ <b>MAX • Нерег:</b> {'Включена' if new_on else 'Выключена'}\n\n"
        "Остановка всего бота отключает приём номеров и вывод средств полностью. "
        "Остановка отдельной категории отключает приём номеров только по ней."
    )
    await show_menu(call, text, categories_menu_kb(bot_on, reg_on, new_on))


@router.callback_query(F.data == "categories_menu")
async def categories_menu(call: CallbackQuery):
    if not await require_admin(call):
        return
    await show_categories_menu(call)


@router.callback_query(F.data == "cat_stop_registered")
async def cat_stop_registered(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        await cb_answer(call)
        return
    await set_category_enabled(CAT_REG, False)
    await show_categories_menu(call)
    await cb_answer(call)


@router.callback_query(F.data == "cat_start_registered")
async def cat_start_registered(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        await cb_answer(call)
        return
    await set_category_enabled(CAT_REG, True)
    await show_categories_menu(call)
    await cb_answer(call)


@router.callback_query(F.data == "cat_stop_unregistered")
async def cat_stop_unregistered(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        await cb_answer(call)
        return
    await set_category_enabled(CAT_NEW, False)
    await show_categories_menu(call)
    await cb_answer(call)


@router.callback_query(F.data == "cat_start_unregistered")
async def cat_start_unregistered(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        await cb_answer(call)
        return
    await set_category_enabled(CAT_NEW, True)
    await show_categories_menu(call)
    await cb_answer(call)


# ---------- Очистка очереди ----------
@router.callback_query(F.data == "clear_queue_menu")
async def clear_queue_menu(call: CallbackQuery):
    if not await require_admin(call):
        return
    total = await count_queue()
    text = (
        tg(T_CLEAR, "🗑") + " × <b>Очистка очереди.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "Подтверждая удаление все ожидающие заявки будут удалены."
    )
    await show_menu(call, text, clear_queue_confirm_kb())


@router.callback_query(F.data == "clear_q_yes_all")
async def clear_queue_do(call: CallbackQuery):
    if not await require_admin(call):
        return
    deleted = await clear_queue(None)
    text = (
        tg(T_OK, "✅") + " × <b>Очередь очищена.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"<b>Удалено заявок:</b> <code>{deleted}</code>"
    )
    await show_menu(call, text, back_to_admin_kb())
    await cb_answer(call)


# ---------- Номера: код / принять / отклонить ----------
@router.callback_query(F.data.regexp(r"^reqcode_\d+_\d+$"))
async def request_code(call: CallbackQuery, bot: Bot):
    if not await is_admin(call.from_user.id):
        await cb_answer(call)
        return
    parts = call.data.split("_")
    number_id, user_id = int(parts[1]), int(parts[2])
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT number, status FROM numbers WHERE id=?", (number_id,))
        row = await cur.fetchone()
        if not row or row[1] != "pending":
            await cb_answer(call)
            return
        number = row[0]

    from aiogram.types import ForceReply
    now_iso = datetime.now(timezone.utc).isoformat()
    text = (
        tg(T_CODE, "📨") + " × <b>Запрошен код.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"<b>Номер:</b> <code>{number}</code>\n\n"
        "Пришлите код из 6 цифр ответом на это сообщение в течение 2 минут.\n"
        "Код без ответа на это сообщение не принимается."
    )
    try:
        sent = await bot.send_message(
            user_id,
            text,
            parse_mode="HTML",
            reply_markup=ForceReply(selective=True, input_field_placeholder="Код из 6 цифр"),
        )
    except Exception:
        await cb_answer(call)
        return

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE numbers SET status='code_requested', code_msg_id=?, code_requested_at=? WHERE id=?",
            (sent.message_id, now_iso, number_id),
        )
        await db.commit()

    await safe_edit(
        call,
        tg(T_CODE, "📨") + " × <b>Код запрошен.</b>\n━━━━━━━━━━━━━━━━\n"
        f"<b>Номер:</b> <code>{number}</code>",
        back_to_admin_kb(),
    )
    await cb_answer(call)


@router.callback_query(F.data.regexp(r"^cancelnum_\d+_\d+$"))
async def cancel_number(call: CallbackQuery, bot: Bot):
    if not await is_admin(call.from_user.id):
        await cb_answer(call)
        return
    parts = call.data.split("_")
    number_id, user_id = int(parts[1]), int(parts[2])
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT number, status FROM numbers WHERE id=?", (number_id,))
        row = await cur.fetchone()
        if not row or row[1] not in ("pending", "code_requested", "code_submitted"):
            await cb_answer(call)
            return
        number = row[0]
        cur = await db.execute(
            "UPDATE numbers SET status='rejected' WHERE id=? AND status IN ('pending','code_requested','code_submitted')",
            (number_id,),
        )
        if cur.rowcount == 0:
            await cb_answer(call)
            return
        await db.execute("UPDATE users SET failed = failed + 1 WHERE user_id=?", (user_id,))
        await db.commit()
    await advance_queue(bot)
    try:
        await bot.send_message(
            user_id,
            tg(T_ERR, "🚫") + " × <b>Заявка отклонена.</b>\n━━━━━━━━━━━━━━━━\n"
            f"<b>Номер:</b> <code>{number}</code>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await safe_edit(
        call,
        tg(T_ERR, "🚫") + " × <b>Номер отклонён.</b>\n━━━━━━━━━━━━━━━━\n"
        f"<b>Номер:</b> <code>{number}</code>",
        back_to_admin_kb(),
    )
    await cb_answer(call)


@router.callback_query(F.data.regexp(r"^confirmnum_\d+_\d+$"))
async def confirm_number(call: CallbackQuery, bot: Bot):
    if not await is_admin(call.from_user.id):
        await cb_answer(call)
        return
    parts = call.data.split("_")
    number_id, user_id = int(parts[1]), int(parts[2])
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT number, status, category FROM numbers WHERE id=?", (number_id,))
        row = await cur.fetchone()
        if not row or row[1] not in ("code_submitted", "code_requested", "pending"):
            await cb_answer(call)
            return
        number, _, category = row[0], row[1], row[2] or CAT_REG
        price = await get_price(category)
        cur = await db.execute(
            "UPDATE numbers SET status='accepted' WHERE id=? AND status IN ('code_submitted','code_requested','pending')",
            (number_id,),
        )
        if cur.rowcount == 0:
            await cb_answer(call)
            return
        await db.execute(
            "UPDATE users SET balance = balance + ?, success = success + 1 WHERE user_id=?",
            (price, user_id)
        )
        await db.commit()
    await advance_queue(bot)
    try:
        await bot.send_message(
            user_id,
            tg(T_OK, "✅") + " × <b>Номер принят.</b>\n━━━━━━━━━━━━━━━━\n"
            f"<b>На ваш баланс зачислено:</b> <code>${price:.2f}</code>",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await safe_edit(
        call,
        tg(T_OK, "✅") + " × <b>Номер принят.</b>\n━━━━━━━━━━━━━━━━\n"
        f"<b>На баланс зачислено:</b> <code>${price:.2f}</code>",
        back_to_admin_kb(),
    )
    await cb_answer(call)


@router.callback_query(F.data.regexp(r"^rejectnum_\d+_\d+$"))
async def reject_number(call: CallbackQuery, bot: Bot):
    if not await is_admin(call.from_user.id):
        await cb_answer(call)
        return
    parts = call.data.split("_")
    number_id, user_id = int(parts[1]), int(parts[2])
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT number, status FROM numbers WHERE id=?", (number_id,))
        row = await cur.fetchone()
        if not row or row[1] not in ("code_submitted", "code_requested", "pending"):
            await cb_answer(call)
            return
        number = row[0]
        cur = await db.execute(
            "UPDATE numbers SET status='rejected' WHERE id=? AND status IN ('pending','code_requested','code_submitted')",
            (number_id,),
        )
        if cur.rowcount == 0:
            await cb_answer(call)
            return
        await db.execute("UPDATE users SET failed = failed + 1 WHERE user_id=?", (user_id,))
        await db.commit()
    await advance_queue(bot)
    try:
        await bot.send_message(
            user_id,
            tg(T_ERR, "🚫") + " × <b>Заявка отклонена.</b>\n━━━━━━━━━━━━━━━━\n"
            f"<b>Номер:</b> <code>{number}</code>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await safe_edit(
        call,
        tg(T_ERR, "🚫") + " × <b>Номер отклонён.</b>\n━━━━━━━━━━━━━━━━\n"
        f"<b>Номер:</b> <code>{number}</code>",
        back_to_admin_kb(),
    )
    await cb_answer(call)


# ---------- Цены ----------

@router.callback_query(F.data == "price_menu")
async def price_menu(call: CallbackQuery):
    if not await require_admin(call):
        return
    text = (
        tg(T_PRICE, "🎨") + " × <b>Управление ценами.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "<b>Выберите категорию:</b>"
    )
    await show_menu(call, text, price_menu_kb())


@router.callback_query(F.data == "set_price_registered")
async def set_price_reg_start(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    current = await get_setting("price_registered", "5.8")
    await safe_edit(
        call,
        tg(T_PRICE, "🎨") + " × <b>Цена: MAX • Рег.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "<b>Введите новую цену:</b>",
        reply_markup=cancel_kb("admin_panel")
    )
    await state.set_state(AdminStates.waiting_price_registered)


@router.callback_query(F.data == "set_price_unregistered")
async def set_price_new_start(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    current = await get_setting("price_unregistered", "4.0")
    await safe_edit(
        call,
        tg(T_PRICE, "🎨") + " × <b>Цена: MAX • Нерег.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "<b>Введите новую цену:</b>",
        reply_markup=cancel_kb("admin_panel")
    )
    await state.set_state(AdminStates.waiting_price_unregistered)


@router.message(AdminStates.waiting_price_registered, F.text)
async def set_price_reg_process(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id):
        return
    try:
        price = float(msg.text.replace(",", ".").strip())
        if price < 0:
            raise ValueError
    except ValueError:
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\n"
            "Введите число не меньше <code>$0.00</code>.",
            reply_markup=cancel_kb("admin_panel"), parse_mode="HTML"
        )
        return
    await set_setting("price_registered", str(price))
    await set_setting("price", str(price))
    await msg.answer(
        tg(T_OK, "✅") + " × <b>Цена обновлена.</b>\n━━━━━━━━━━━━━━━━\n"
        f"<b>MAX • Рег:</b> <code>${price:.2f}</code>",
        reply_markup=back_to_admin_kb(), parse_mode="HTML"
    )
    await state.clear()


@router.message(AdminStates.waiting_price_unregistered, F.text)
async def set_price_new_process(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id):
        return
    try:
        price = float(msg.text.replace(",", ".").strip())
        if price < 0:
            raise ValueError
    except ValueError:
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\n"
            "Введите число не меньше <code>$0.00</code>.",
            reply_markup=cancel_kb("admin_panel"), parse_mode="HTML"
        )
        return
    await set_setting("price_unregistered", str(price))
    await msg.answer(
        tg(T_OK, "✅") + " × <b>Цена обновлена.</b>\n━━━━━━━━━━━━━━━━\n"
        f"<b>MAX • Нерег:</b> <code>${price:.2f}</code>",
        reply_markup=back_to_admin_kb(), parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data == "set_min_withdraw")
async def set_min_withdraw_start(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    current = await get_setting("min_withdraw", "1.0")
    await safe_edit(
        call,
        tg(T_PRICE, "🎨") + " × <b>Минимум вывода.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "<b>Введите новую сумму:</b>",
        reply_markup=cancel_kb("price_menu")
    )
    await state.set_state(AdminStates.waiting_min_withdraw)


@router.message(AdminStates.waiting_min_withdraw, F.text)
async def set_min_withdraw_process(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id):
        return
    try:
        value = float(msg.text.replace(",", ".").strip())
        if value < 0:
            raise ValueError
    except ValueError:
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\n"
            "Введите число не меньше <code>$0.00</code>.",
            reply_markup=cancel_kb("price_menu"), parse_mode="HTML"
        )
        return
    await set_setting("min_withdraw", str(value))
    await msg.answer(
        tg(T_OK, "✅") + " × <b>Минимум вывода.</b>\n━━━━━━━━━━━━━━━━\n"
        f"<b>Сумма:</b> <code>${value:.2f}</code>",
        reply_markup=back_to_admin_kb(), parse_mode="HTML"
    )
    await state.clear()


# ---------- Статистика ----------
@router.callback_query(F.data == "stats")
async def show_stats(call: CallbackQuery):
    if not await require_admin(call):
        return
    async with aiosqlite.connect(DB_NAME) as db:
        users_count = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        active_users = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE banned=0 AND subscribed=1"
        )).fetchone())[0]
        subscribed_users = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE subscribed=1"
        )).fetchone())[0]
        approved_users = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE approved=1"
        )).fetchone())[0]
        banned_users = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE banned=1"
        )).fetchone())[0]
        new_24h = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE registered_at >= datetime('now', '-1 day')"
        )).fetchone())[0]
        new_7d = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE registered_at >= datetime('now', '-7 day')"
        )).fetchone())[0]
        new_30d = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE registered_at >= datetime('now', '-30 day')"
        )).fetchone())[0]

        total_numbers = (await (await db.execute("SELECT COUNT(*) FROM numbers")).fetchone())[0]
        accepted = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status='accepted'"
        )).fetchone())[0]
        rejected_admin = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status='rejected'"
        )).fetchone())[0]
        cancelled_by_user = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status='cancelled'"
        )).fetchone())[0]
        rejected = rejected_admin + cancelled_by_user
        in_queue = await count_queue()
        active_now = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status='pending' AND notified_admin=1"
        )).fetchone())[0]
        waiting_turn = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status='pending' AND notified_admin=0"
        )).fetchone())[0]
        waiting_code = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status='code_requested'"
        )).fetchone())[0]
        code_sent = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status='code_submitted'"
        )).fetchone())[0]
        acc_reg = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status='accepted' AND category='registered'"
        )).fetchone())[0]
        acc_new = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status='accepted' AND (category='unregistered' OR category IS NULL OR category='')"
        )).fetchone())[0]
        in_queue_reg = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status IN ('pending','code_requested','code_submitted') AND category=?",
            (CAT_REG,)
        )).fetchone())[0]
        in_queue_new = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status IN ('pending','code_requested','code_submitted') AND category=?",
            (CAT_NEW,)
        )).fetchone())[0]

        paid_sum = (await (await db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM withdrawals WHERE status='success'"
        )).fetchone())[0]
        processing_wd_sum = (await (await db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM withdrawals WHERE status='processing'"
        )).fetchone())[0]
        failed_wd_sum = (await (await db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM withdrawals WHERE status='failed'"
        )).fetchone())[0]
        total_balance = (await (await db.execute(
            "SELECT COALESCE(SUM(balance),0) FROM users"
        )).fetchone())[0]
        processing_wd = (await (await db.execute(
            "SELECT COUNT(*) FROM withdrawals WHERE status='processing'"
        )).fetchone())[0]
        paid_wd = (await (await db.execute(
            "SELECT COUNT(*) FROM withdrawals WHERE status='success'"
        )).fetchone())[0]
        failed_wd = (await (await db.execute(
            "SELECT COUNT(*) FROM withdrawals WHERE status='failed'"
        )).fetchone())[0]
        admins_count = (await (await db.execute("SELECT COUNT(*) FROM admins")).fetchone())[0]

    price_reg = await get_price(CAT_REG)
    price_new = await get_price(CAT_NEW)
    min_withdraw = await get_setting("min_withdraw", "1.0")
    earned_est = acc_reg * price_reg + acc_new * price_new
    bot_on = await is_bot_enabled()
    reg_on = await is_category_enabled(CAT_REG)
    new_on = await is_category_enabled(CAT_NEW)
    avg_balance = (total_balance / users_count) if users_count else 0.0
    conversion = (accepted / total_numbers * 100) if total_numbers else 0.0

    text = (
        tg(T_STATS, "📊") + " × <b>Информация.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"{tg(T_USERS, '👥')} <b>Пользователи.</b>\n"
        f"┌ <b>Всего:</b> <code>{users_count}</code>\n"
        f"├ <b>Активных:</b> <code>{active_users}</code>\n"
        f"├ <b>Подписанных на канал:</b> <code>{subscribed_users}</code>\n"
        f"├ <b>Одобренных:</b> <code>{approved_users}</code>\n"
        f"├ <b>Заблокированных:</b> <code>{banned_users}</code>\n"
        f"├ <b>Новых за 24ч:</b> <code>{new_24h}</code>\n"
        f"├ <b>Новых за 7 дней:</b> <code>{new_7d}</code>\n"
        f"└ <b>Новых за 30 дней:</b> <code>{new_30d}</code>\n"
        "\n"
        f"{tg(T_SUBMIT, '📥')} <b>Заявки на номера.</b>\n"
        f"┌ <b>Всего сдано:</b> <code>{total_numbers}</code>\n"
        f"├ <b>Успешных:</b> <code>{accepted}</code>\n"
        f"├ <b>Отклонено админом:</b> <code>{rejected_admin}</code>\n"
        f"├ <b>Отменено пользователями:</b> <code>{cancelled_by_user}</code>\n"
        f"├ <b>Принято • Рег:</b> <code>{acc_reg}</code>\n"
        f"├ <b>Принято • Нерег:</b> <code>{acc_new}</code>\n"
        f"└ <b>Конверсия в успешные:</b> <code>{conversion:.1f}%</code>\n"
        "\n"
        f"{tg(T_QUEUE, '🕓')} <b>Очередь сейчас.</b>\n"
        f"┌ <b>Всего в очереди:</b> <code>{in_queue}</code>\n"
        f"├ <b>Сейчас на рассмотрении:</b> <code>{active_now}</code>\n"
        f"├ <b>Ждут своей очереди:</b> <code>{waiting_turn}</code>\n"
        f"├ <b>Запрошен код:</b> <code>{waiting_code}</code>\n"
        f"├ <b>Код отправлен, на проверке:</b> <code>{code_sent}</code>\n"
        f"├ <b>MAX • Рег в очереди:</b> <code>{in_queue_reg}</code>\n"
        f"└ <b>MAX • Нерег в очереди:</b> <code>{in_queue_new}</code>\n"
        "\n"
        f"{tg(T_WITHDRAW, '💼')} <b>Финансы.</b>\n"
        f"┌ <b>Оборот (оценка):</b> <code>${earned_est:.2f}</code>\n"
        f"├ <b>Выплачено:</b> <code>${paid_sum:.2f}</code> (<code>{paid_wd}</code> шт.)\n"
        f"├ <b>В обработке сейчас:</b> <code>${processing_wd_sum:.2f}</code> (<code>{processing_wd}</code> шт.)\n"
        f"├ <b>Неудачных выплат:</b> <code>${failed_wd_sum:.2f}</code> (<code>{failed_wd}</code> шт.)\n"
        f"├ <b>Балансы пользователей:</b> <code>${total_balance:.2f}</code>\n"
        f"└ <b>Средний баланс:</b> <code>${avg_balance:.2f}</code>\n"
        "\n"
        f"{tg(T_STOP, '🖥')} <b>Настройки сервиса.</b>\n"
        f"┌ <b>Весь бот:</b> {'Включён' if bot_on else 'Выключен'}\n"
        f"├ <b>MAX • Рег:</b> {'Включена' if reg_on else 'Выключена'}\n"
        f"├ <b>MAX • Нерег:</b> {'Включена' if new_on else 'Выключена'}\n"
        f"├ <b>Цена • Рег:</b> <code>${price_reg:.2f}</code>\n"
        f"├ <b>Цена • Нерег:</b> <code>${price_new:.2f}</code>\n"
        f"├ <b>Мин. сумма вывода:</b> <code>${float(min_withdraw):.2f}</code>\n"
        f"└ <b>Администраторов:</b> <code>{admins_count}</code>"
    )
    await show_menu(call, text, back_to_admin_kb())


# ---------- Рассылка ----------
@router.callback_query(F.data == "broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    await safe_edit(
        call,
        tg(T_BROADCAST, "📢") + " × <b>Рассылка.</b>\n━━━━━━━━━━━━━━━━\n"
        "Введите текст сообщения для рассылки всем пользователям.",
        reply_markup=cancel_kb("admin_panel"),
    )
    await state.set_state(AdminStates.waiting_broadcast)


@router.message(AdminStates.waiting_broadcast, F.text)
async def broadcast_process(msg: Message, state: FSMContext, bot: Bot):
    if not await is_admin(msg.from_user.id):
        return
    text = msg.text
    # Удаляем исходное сообщение админа, чтобы текст рассылки не оставался в чате
    try:
        await msg.delete()
    except Exception:
        pass
    status_msg = await bot.send_message(
        msg.from_user.id,
        tg(T_BROADCAST, "📢") + " × <b>Рассылка...</b>\n━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
    )
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE banned=0 AND subscribed=1")
        users = await cur.fetchall()
    success = fail = 0
    for (user_id,) in users:
        try:
            await bot.send_message(user_id, text, parse_mode="HTML")
            success += 1
        except Exception:
            fail += 1
    await status_msg.edit_text(
        tg(T_OK, "✅") + " × <b>Рассылка завершена.</b>\n━━━━━━━━━━━━━━━━\n"
        + f"<b>Доставлено:</b> <code>{success}</code>\n<b>Ошибок:</b> <code>{fail}</code>",
        reply_markup=back_to_admin_kb(),
        parse_mode="HTML",
    )
    await state.clear()


# ---------- Доступ ----------
@router.callback_query(F.data == "access_panel")
async def access_panel(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    await state.clear()
    await show_menu(call, tg(T_ACCESS, "🔓") + " × <b>Управление доступом.</b>\n━━━━━━━━━━━━━━━━\n<b>Выберите действие:</b>", access_panel_kb())




@router.callback_query(F.data == "grant_all_access")
async def grant_all_ask(call: CallbackQuery):
    if not await require_admin(call):
        return
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE approved=0 AND banned=0")
        cnt = (await cur.fetchone())[0]
    text = (
        tg(T_ACCESS, "🔓") + " × <b>Открыть доступ всем.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "Выдать доступ всем пользователям?"
    )
    await safe_edit(call, text, grant_all_confirm_kb())


@router.callback_query(F.data == "grant_all_yes")
async def grant_all_do(call: CallbackQuery, bot: Bot):
    if not await require_admin(call):
        return
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE banned=0 AND approved=0")
        ids = [r[0] for r in await cur.fetchall()]
        if ids:
            await db.execute("UPDATE users SET approved=1 WHERE banned=0 AND approved=0")
            await db.commit()
    notified = 0
    for uid in ids:
        try:
            await bot.send_message(
                uid,
                tg(T_OK, "✅") + " × <b>Доступ выдан.</b>\n━━━━━━━━━━━━━━━━\nНажмите /start — чтобы начать пользоваться ботом.",
                parse_mode="HTML"
            )
            notified += 1
        except Exception:
            pass
    text = (
        tg(T_OK, "✅") + " × <b>Доступ открыт.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"<b>Выдано:</b> <code>{len(ids)}</code> — Пользователям\n"
        f"<b>Уведомлено:</b> <code>{notified}</code> — Пользователей"
    )
    await safe_edit(call, text, access_panel_kb())
    await cb_answer(call)


@router.callback_query(F.data == "revoke_all_access")
async def revoke_all_ask(call: CallbackQuery):
    if not await require_admin(call):
        return
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM users WHERE approved=1 AND banned=0"
        )
        cnt = (await cur.fetchone())[0]
    text = (
        tg(T_WARN, "⚠️") + " × <b>Закрыть доступ всем.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "Забрать доступ у всех обычных пользователей?"
    )
    await safe_edit(call, text, revoke_all_confirm_kb())


@router.callback_query(F.data == "revoke_all_yes")
async def revoke_all_do(call: CallbackQuery, bot: Bot):
    if not await require_admin(call):
        return
    from database import get_admins
    admins = set(await get_admins())
    revoked = []
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE approved=1")
        rows = await cur.fetchall()
        for (uid,) in rows:
            if uid in admins:
                continue
            await db.execute("UPDATE users SET approved=0 WHERE user_id=?", (uid,))
            revoked.append(uid)
        await db.commit()
    notified = 0
    for uid in revoked:
        try:
            await bot.send_message(
                uid,
                tg(T_ERR, "🚫") + " × <b>Доступ закрыт.</b>\n━━━━━━━━━━━━━━━━\nВы больше не сможете пользоваться ботом.",
                parse_mode="HTML"
            )
            notified += 1
        except Exception:
            pass
    text = (
        tg(T_OK, "✅") + " × <b>Доступ закрыт.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"<b>Забран:</b> <code>{len(revoked)}</code> — Пользователей\n"
        f"<b>Уведомлено:</b> <code>{notified}</code> — Пользователей"
    )
    await safe_edit(call, text, access_panel_kb())
    await cb_answer(call)


@router.callback_query(F.data == "grant_access")
async def grant_access_start(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    await safe_edit(call, tg(T_OK, "✅") + " × <b>Выдача доступа.</b>\n━━━━━━━━━━━━━━━━\nОтправьте Telegram ID пользователя.", reply_markup=cancel_kb("access_panel"))
    await state.set_state(AdminStates.waiting_grant_access)


@router.message(AdminStates.waiting_grant_access, F.text)
async def grant_access_process(msg: Message, state: FSMContext, bot: Bot):
    if not await is_admin(msg.from_user.id):
        return
    try:
        target_id = int(msg.text.strip())
    except ValueError:
        await msg.answer(tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\nОтправьте числовой Telegram ID.", reply_markup=cancel_kb("access_panel"), parse_mode="HTML")
        return
    await ensure_user_record(target_id, None)
    success = await set_approved(target_id, 1)
    if success:
        await msg.answer(tg(T_OK, "✅") + " × <b>Доступ выдан.</b>\n━━━━━━━━━━━━━━━━\n" + f"<b>ID:</b> <code>{target_id}</code>", reply_markup=access_panel_kb(), parse_mode="HTML")
        try:
            await bot.send_message(target_id, tg(T_OK, "✅") + " × <b>Доступ выдан.</b>\n━━━━━━━━━━━━━━━━\nНажмите /start — чтобы начать пользоваться ботом.", parse_mode="HTML")
        except Exception:
            pass
    else:
        await msg.answer(tg(T_INFO, "🔔") + " × <b>Не найден.</b>\n━━━━━━━━━━━━━━━━\n" + f"<b>ID:</b> <code>{target_id}</code>\nПусть напишет /start.", reply_markup=access_panel_kb(), parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "revoke_access")
async def revoke_access_start(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    await safe_edit(call, tg(T_ERR, "🚫") + " × <b>Забрать доступ.</b>\n━━━━━━━━━━━━━━━━\nОтправьте Telegram ID.", reply_markup=cancel_kb("access_panel"))
    await state.set_state(AdminStates.waiting_revoke_access)


@router.message(AdminStates.waiting_revoke_access, F.text)
async def revoke_access_process(msg: Message, state: FSMContext, bot: Bot):
    if not await is_admin(msg.from_user.id):
        return
    try:
        target_id = int(msg.text.strip())
    except ValueError:
        await msg.answer(tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\nОтправьте числовой Telegram ID.", reply_markup=cancel_kb("access_panel"), parse_mode="HTML")
        return
    if await is_admin(target_id):
        await msg.answer(tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\nНельзя забрать доступ у администратора или владельца.", reply_markup=access_panel_kb(), parse_mode="HTML")
        await state.clear()
        return
    success = await set_approved(target_id, 0)
    if success:
        await msg.answer(tg(T_ERR, "🚫") + " × <b>Доступ забран.</b>\n━━━━━━━━━━━━━━━━\n" + f"<b>ID:</b> <code>{target_id}</code>", reply_markup=access_panel_kb(), parse_mode="HTML")
        try:
            await bot.send_message(target_id, tg(T_ERR, "🚫") + " × <b>Доступ закрыт.</b>\n━━━━━━━━━━━━━━━━\nВы больше не сможете пользоваться ботом.", parse_mode="HTML")
        except Exception:
            pass
    else:
        await msg.answer(tg(T_INFO, "🔔") + " × <b>Не найден.</b>\n━━━━━━━━━━━━━━━━\n" + f"<b>ID:</b> <code>{target_id}</code>", reply_markup=access_panel_kb(), parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "list_no_access")
async def list_no_access(call: CallbackQuery):
    if not await require_admin(call):
        return
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT user_id, username FROM users WHERE approved=0 AND banned=0 ORDER BY registered_at DESC LIMIT 40"
        )
        rows = await cur.fetchall()
    if not rows:
        await safe_edit(call, tg(T_OK, "✅") + " × <b>Без доступа.</b>\n━━━━━━━━━━━━━━━━\nНет пользователей без доступа.", access_panel_kb())
        return
    text = tg(T_LIST, "🧑‍💻") + " × <b>Без доступа.</b>\n━━━━━━━━━━━━━━━━\n"
    for uid, uname in rows:
        text += f"Пользователь | <code>{uid}</code> — {('@'+uname) if uname else '@username'}\n"
    await safe_edit(call, text, access_panel_kb())


@router.callback_query(F.data == "list_with_access")
async def list_with_access(call: CallbackQuery):
    if not await require_admin(call):
        return
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT user_id, username, balance, total FROM users WHERE banned=0 AND subscribed=1 ORDER BY total DESC LIMIT 40"
        )
        rows = await cur.fetchall()
    if not rows:
        await safe_edit(call, tg(T_OK, "✅") + " × <b>С доступом.</b>\n━━━━━━━━━━━━━━━━\nНет пользователей с доступом.", access_panel_kb())
        return
    text = tg(T_LIST, "🧑‍💻") + " × <b>С доступом.</b>\n━━━━━━━━━━━━━━━━\n"
    for uid, uname, bal, total in rows:
        text += f"Пользователь | <code>{uid}</code> — {('@'+uname) if uname else '@username'}\n"
    await safe_edit(call, text, access_panel_kb())


# ---------- Админы (только команды, только владелец) ----------
@router.message(Command("add"))
async def add_moder_cmd(msg: Message, command: CommandObject, state: FSMContext):
    if not await is_owner(msg.from_user.id):
        return
    if not command.args or not command.args.strip():
        await msg.answer(
            tg(T_OK, "✅") + " × <b>Добавить админа.</b>\n━━━━━━━━━━━━━━━━\n"
            "<b>Использование:</b> /add ID",
            parse_mode="HTML"
        )
        return
    try:
        new_id = int(command.args.strip())
    except ValueError:
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\nОтправьте числовой Telegram ID.",
            parse_mode="HTML"
        )
        return
    if new_id == OWNER_ID:
        await msg.answer(
            tg(T_INFO, "🔔") + " × <b>Уже владелец.</b>\n━━━━━━━━━━━━━━━━\nЭто уже владелец.",
            parse_mode="HTML"
        )
        return
    await add_admin(new_id)
    await msg.answer(
        tg(T_OK, "✅") + " × <b>Админ добавлен.</b>\n━━━━━━━━━━━━━━━━\n"
        f"<b>ID:</b> <code>{new_id}</code>",
        parse_mode="HTML"
    )


@router.message(Command("del"))
async def delete_moder_cmd(msg: Message, command: CommandObject, state: FSMContext):
    if not await is_owner(msg.from_user.id):
        return
    if not command.args or not command.args.strip():
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Удалить админа.</b>\n━━━━━━━━━━━━━━━━\n"
            "<b>Использование:</b> /del ID",
            parse_mode="HTML"
        )
        return
    try:
        admin_id = int(command.args.strip())
    except ValueError:
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\nОтправьте числовой Telegram ID.",
            parse_mode="HTML"
        )
        return
    if admin_id == OWNER_ID:
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\nВладельца удалить нельзя.",
            parse_mode="HTML"
        )
        return
    removed = await remove_admin(admin_id)
    if removed:
        await msg.answer(
            tg(T_OK, "✅") + " × <b>Админ удалён.</b>\n━━━━━━━━━━━━━━━━\n"
            f"<b>ID:</b> <code>{admin_id}</code>",
            parse_mode="HTML"
        )
    else:
        await msg.answer(
            tg(T_INFO, "🔔") + " × <b>Не найден.</b>\n━━━━━━━━━━━━━━━━\nЭтот пользователь не админ.",
            parse_mode="HTML"
        )


@router.message(Command("list"))
async def list_moder_cmd(msg: Message):
    if not await is_owner(msg.from_user.id):
        return
    admins = await get_admins()
    text = tg(T_LIST, "🧑‍💻") + " × <b>Список администраторов.</b>\n━━━━━━━━━━━━━━━━\n"
    for aid in admins:
        uname = await get_username(aid)
        uname_s = f"@{uname}" if uname else "@username"
        text += f"{uname_s} | <code>{aid}</code>\n"
    await msg.answer(text, parse_mode="HTML")


# ---------- Резерв (баланс приложения @CryptoBot) ----------
@router.callback_query(F.data == "treasury")
async def treasury(call: CallbackQuery):
    if not await require_admin(call):
        return
    stats = await get_treasury_stats()
    wallet_balance = 0.0
    try:
        balances = await cp.get_balance()
        for b in balances:
            if b.get("currency_code") == DEFAULT_ASSET:
                raw = b.get("available", b.get("amount", "0"))
                try:
                    wallet_balance = float(raw or 0)
                except (TypeError, ValueError):
                    wallet_balance = 0.0
                break
    except (CryptoPayError, Exception):
        wallet_balance = 0.0

    text = (
        tg(T_PAY, "🛒") + " × <b>Резерв.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"<b>Баланс резерва:</b> <code>${wallet_balance:.2f}</code>\n"
        "\n"
        f"┌ <b>Успешных выплат:</b> <code>{stats['n_success_users']}</code>\n"
        f"├ <b>Неудачных выплат:</b> <code>{stats['n_failed_users']}</code>\n"
        f"├ <b>В обработке сейчас:</b> <code>${stats['sum_processing']:.2f}</code>\n"
        f"├ <b>Выплачено за 24ч:</b> <code>{stats['n_24h']}</code> на сумму <code>${stats['sum_24h']:.2f}</code>\n"
        f"├ <b>Средняя выплата:</b> <code>${stats['avg']:.2f}</code>\n"
        f"├ <b>Уникальных получателей:</b> <code>{stats['n_users']}</code>\n"
        f"└ <b>Общий баланс пользователей:</b> <code>${stats['total_balance']:.2f}</code>"
    )
    await show_menu(call, text, back_to_admin_kb())


# ---------- Блокировка пользователей ----------
@router.callback_query(F.data == "ban_user_start")
async def ban_user_start(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    await safe_edit(
        call,
        tg(T_ERR, "🚫") + " × <b>Блокировка пользователя.</b>\n━━━━━━━━━━━━━━━━\nОтправьте Telegram ID пользователя.",
        reply_markup=cancel_kb("access_panel"),
    )
    await state.set_state(AdminStates.waiting_ban_user)


@router.message(AdminStates.waiting_ban_user, F.text)
async def ban_user_process(msg: Message, state: FSMContext, bot: Bot):
    if not await is_admin(msg.from_user.id):
        return
    try:
        target_id = int(msg.text.strip())
    except ValueError:
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\nОтправьте числовой Telegram ID.",
            reply_markup=cancel_kb("access_panel"), parse_mode="HTML"
        )
        return
    if await is_admin(target_id):
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\nНельзя заблокировать администратора или владельца.",
            reply_markup=access_panel_kb(), parse_mode="HTML"
        )
        await state.clear()
        return
    ok = await set_banned(target_id, 1)
    if ok:
        await msg.answer(
            tg(T_OK, "✅") + " × <b>Пользователь заблокирован.</b>\n━━━━━━━━━━━━━━━━\n" + f"<b>ID:</b> <code>{target_id}</code>",
            reply_markup=access_panel_kb(), parse_mode="HTML"
        )
        try:
            await bot.send_message(
                target_id,
                tg(T_ERR, "🚫") + " × <b>Доступ ограничен.</b>\n━━━━━━━━━━━━━━━━\nОбратитесь в поддержку.",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        await msg.answer(
            tg(T_INFO, "🔔") + " × <b>Не найден.</b>\n━━━━━━━━━━━━━━━━\n" + f"<b>ID:</b> <code>{target_id}</code>",
            reply_markup=access_panel_kb(), parse_mode="HTML"
        )
    await state.clear()


@router.callback_query(F.data == "unban_user_start")
async def unban_user_start(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    await safe_edit(
        call,
        tg(T_OK, "✅") + " × <b>Разблокировка пользователя.</b>\n━━━━━━━━━━━━━━━━\nОтправьте Telegram ID пользователя.",
        reply_markup=cancel_kb("access_panel"),
    )
    await state.set_state(AdminStates.waiting_unban_user)


@router.message(AdminStates.waiting_unban_user, F.text)
async def unban_user_process(msg: Message, state: FSMContext, bot: Bot):
    if not await is_admin(msg.from_user.id):
        return
    try:
        target_id = int(msg.text.strip())
    except ValueError:
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\nОтправьте числовой Telegram ID.",
            reply_markup=cancel_kb("access_panel"), parse_mode="HTML"
        )
        return
    ok = await set_banned(target_id, 0)
    if ok:
        await msg.answer(
            tg(T_OK, "✅") + " × <b>Пользователь разблокирован.</b>\n━━━━━━━━━━━━━━━━\n" + f"<b>ID:</b> <code>{target_id}</code>",
            reply_markup=access_panel_kb(), parse_mode="HTML"
        )
        try:
            await bot.send_message(
                target_id,
                tg(T_OK, "✅") + " × <b>Доступ восстановлен.</b>\n━━━━━━━━━━━━━━━━\nНажмите /start, чтобы продолжить пользоваться ботом.",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        await msg.answer(
            tg(T_INFO, "🔔") + " × <b>Не найден.</b>\n━━━━━━━━━━━━━━━━\n" + f"<b>ID:</b> <code>{target_id}</code>",
            reply_markup=access_panel_kb(), parse_mode="HTML"
        )
    await state.clear()


