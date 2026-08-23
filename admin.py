from aiogram.filters import Command
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
    manage_admins_kb, access_panel_kb, number_request_kb, number_confirm_kb,
    withdraw_item_kb, withdraw_action_kb, queue_menu_kb, wd_panel_kb, wd_item_actions_kb,
    clear_queue_confirm_kb, grant_all_confirm_kb, revoke_all_confirm_kb
)
from emojis import tg, T_HOME, T_ADMIN, T_QUEUE, T_OK, T_ERR, T_NEW, T_CODE, T_PAY, T_ACCESS, T_STATS, T_LIST, T_BROADCAST, T_PRICE, T_STOP, T_CLEAR, T_WARN, T_USERS, T_PROFILE, T_INFO, T_CHECK, T_SUBMIT, T_WITHDRAW, T_CAT
from database import (
    get_setting, set_setting, is_admin, is_owner,
    get_admins, add_admin, remove_admin, is_bot_enabled,
    set_approved, ensure_user_record, get_price, clear_queue, count_queue,
    get_username,
    CAT_REG, CAT_NEW, CAT_LABEL
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WELCOME_PHOTO = os.path.join(BASE_DIR, "welcome.jpg")
router = Router()


class AdminStates(StatesGroup):
    waiting_price_registered = State()
    waiting_price_unregistered = State()
    waiting_min_withdraw = State()
    waiting_broadcast = State()
    waiting_add_admin = State()
    waiting_remove_admin = State()
    waiting_grant_access = State()
    waiting_revoke_access = State()


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
    q_all = await count_queue()
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'")
        pending_wd = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM users")
        users_count = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE registered_at >= datetime('now', '-1 day')")
        new_24h = (await cur.fetchone())[0]
    return (
        tg(T_ADMIN, "🛡") + " × <b>Админ-панель.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"┌ {tg(T_STOP, '🖥')} <b>Статус:</b> {status}\n"
        f"├ {tg(T_QUEUE, '🕓')} <b>Очередь:</b> <code>{q_all}</code>\n"
        f"├ {tg(T_PAY, '🛒')} <b>Выводы:</b> <code>{pending_wd}</code>\n"
        f"├ {tg(T_USERS, '👥')} <b>Пользователей:</b> <code>{users_count}</code>\n"
        f"└ {tg(T_NEW, '🧪')} <b>Новых за 24ч:</b> <code>{new_24h}</code>"
    )


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
    owner = await is_owner(call.from_user.id)
    text = await build_admin_panel_text()
    await show_menu(call, text, admin_panel_kb(is_owner=owner, bot_enabled=False))
    await cb_answer(call)


@router.callback_query(F.data == "bot_start")
async def bot_start(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        await cb_answer(call)
        return
    await set_setting("bot_enabled", "1")
    owner = await is_owner(call.from_user.id)
    text = await build_admin_panel_text()
    await show_menu(call, text, admin_panel_kb(is_owner=owner, bot_enabled=True))
    await cb_answer(call)


# ---------- Очередь ----------
@router.callback_query(F.data == "queue_menu")
async def queue_menu(call: CallbackQuery):
    if not await require_admin(call):
        return
    c_reg = await count_queue(CAT_REG)
    c_new = await count_queue(CAT_NEW)
    text = (
        tg(T_QUEUE, "🕓") + " × <b>Очередь на проверку.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"<b>MAX • Нерег:</b> <code>{c_new}</code>\n"
        f"<b>MAX • Рег:</b> <code>{c_reg}</code>\n"
        f"<b>Всего:</b> <code>{c_reg + c_new}</code>\n"
        "<b>Выберите категорию:</b>"
    )
    await show_menu(call, text, queue_menu_kb())


@router.callback_query(F.data.in_({"queue_registered", "queue_unregistered", "queue_all"}))
async def show_queue(call: CallbackQuery):
    if not await require_admin(call):
        return
    if call.data == "queue_registered":
        category = CAT_REG
        title = "MAX • Рег"
    elif call.data == "queue_unregistered":
        category = CAT_NEW
        title = "MAX • Нерег"
    else:
        category = None
        title = "Вся очередь"

    async with aiosqlite.connect(DB_NAME) as db:
        if category:
            cur = await db.execute(
                """
                SELECT n.id, n.number, n.user_id, u.username, n.status, n.code, n.created_at, n.category
                FROM numbers n LEFT JOIN users u ON u.user_id = n.user_id
                WHERE n.status IN ('pending','code_requested','code_submitted') AND n.category=?
                ORDER BY n.id ASC LIMIT 25
                """,
                (category,)
            )
        else:
            cur = await db.execute(
                """
                SELECT n.id, n.number, n.user_id, u.username, n.status, n.code, n.created_at, n.category
                FROM numbers n LEFT JOIN users u ON u.user_id = n.user_id
                WHERE n.status IN ('pending','code_requested','code_submitted')
                ORDER BY n.id ASC LIMIT 25
                """
            )
        rows = await cur.fetchall()

    if not rows:
        text = (
            tg(T_QUEUE, "🕓") + f" × <b>{title}.</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "Очередь пуста."
        )
        await show_menu(call, text, queue_menu_kb())
        return

    status_map = {"pending": "ожидает", "code_requested": "код запрошен", "code_submitted": "код получен"}
    text = tg(T_QUEUE, "🕓") + f" × <b>{title}.</b>\n━━━━━━━━━━━━━━━━\n"
    for row in rows:
        num_id, number, user_id, username, status, code, created, cat = row
        st = status_map.get(status, status)
        cl = CAT_LABEL.get(cat or CAT_REG, "")
        text += (
            f"#{num_id} | <code>{number}</code>\n"
            f"<b>От:</b> {('@'+username) if username else '@username'} (<code>{user_id}</code>)\n"
            f"<b>Категория:</b> {cl}\n"
            f"<b>Статус:</b> {st}\n"
        )
        if code:
            text += f"<b>Код:</b> <code>{code}</code>\n"
        text += f"{created}\n"
    await show_menu(call, text, queue_menu_kb())


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
        if price <= 0:
            raise ValueError
    except ValueError:
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\n"
            "Введите положительное число.",
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
        if price <= 0:
            raise ValueError
    except ValueError:
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\n"
            "Введите положительное число.",
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
        if value <= 0:
            raise ValueError
    except ValueError:
        await msg.answer(
            tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\n"
            "Введите положительное число.",
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
        new_24h = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE registered_at >= datetime('now', '-1 day')"
        )).fetchone())[0]
        new_7d = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE registered_at >= datetime('now', '-7 day')"
        )).fetchone())[0]
        total_numbers = (await (await db.execute("SELECT COUNT(*) FROM numbers")).fetchone())[0]
        accepted = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status='accepted'"
        )).fetchone())[0]
        rejected = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status IN ('rejected','cancelled')"
        )).fetchone())[0]
        in_queue = await count_queue()
        paid_sum = (await (await db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM withdrawals WHERE status='paid'"
        )).fetchone())[0]
        pending_wd_sum = (await (await db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM withdrawals WHERE status='pending'"
        )).fetchone())[0]
        total_balance = (await (await db.execute(
            "SELECT COALESCE(SUM(balance),0) FROM users"
        )).fetchone())[0]
        pending_wd = (await (await db.execute(
            "SELECT COUNT(*) FROM withdrawals WHERE status='pending'"
        )).fetchone())[0]
        paid_wd = (await (await db.execute(
            "SELECT COUNT(*) FROM withdrawals WHERE status='paid'"
        )).fetchone())[0]
        acc_reg = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status='accepted' AND category='registered'"
        )).fetchone())[0]
        acc_new = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE status='accepted' AND (category='unregistered' OR category IS NULL OR category='')"
        )).fetchone())[0]
    price_reg = await get_price(CAT_REG)
    price_new = await get_price(CAT_NEW)
    earned_est = acc_reg * price_reg + acc_new * price_new
    bot_on = await is_bot_enabled()
    # unique emoji per line within this section
    text = (
        tg(T_STATS, "📊") + " × <b>Информация.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"┌ {tg(T_STOP, '🖥')} <b>Сервис:</b> {'Включён' if bot_on else 'Выключен'}\n"
        f"├ {tg(T_OK, '✅')} <b>Успешных номеров:</b> <code>{accepted}</code>\n"
        f"├ {tg(T_ERR, '🚫')} <b>Не успешных:</b> <code>{rejected}</code>\n"
        f"├ {tg(T_QUEUE, '🕓')} <b>В обработке:</b> <code>{in_queue}</code>\n"
        f"├ {tg(T_SUBMIT, '📥')} <b>Всего сдано:</b> <code>{total_numbers}</code>\n"
        f"├ {tg(T_PAY, '🛒')} <b>Оборот (оценка):</b> <code>${earned_est:.2f}</code>\n"
        f"├ {tg(T_WITHDRAW, '💼')} <b>Выплачено:</b> <code>${paid_sum:.2f}</code> (<code>{paid_wd}</code>)\n"
        f"├ {tg(T_CODE, '📨')} <b>Ожидает выплаты:</b> <code>${pending_wd_sum:.2f}</code> (<code>{pending_wd}</code>)\n"
        f"├ {tg(T_PROFILE, 'ℹ️')} <b>Балансы пользователей:</b> <code>${total_balance:.2f}</code>\n"
        f"├ {tg(T_USERS, '👥')} <b>Пользователей всего:</b> <code>{users_count}</code>\n"
        f"├ {tg(T_ACCESS, '🔓')} <b>Активных:</b> <code>{active_users}</code>\n"
        f"├ {tg(T_NEW, '🧪')} <b>Новых за 24ч:</b> <code>{new_24h}</code>\n"
        f"└ {tg(T_CAT, '⭐️')} <b>Новых за 7 дней:</b> <code>{new_7d}</code>"
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


# ---------- Пользователи ----------
@router.callback_query(F.data == "users_list")
async def users_list(call: CallbackQuery):
    if not await require_admin(call):
        return
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM users WHERE banned=0 AND subscribed=1"
        )
        active_count = (await cur.fetchone())[0]
    text = (
        tg(T_USERS, "👥") + " × <b>Активные пользователи.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"<b>Всего активных:</b> <code>{active_count}</code>"
    )
    await safe_edit(call, text, back_to_admin_kb())


# ---------- Выводы ----------
@router.callback_query(F.data == "withdrawals_admin")
async def withdrawals_admin(call: CallbackQuery):
    if not await require_admin(call):
        return
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            SELECT w.id, w.user_id, w.amount, w.created_at, u.username
            FROM withdrawals w LEFT JOIN users u ON u.user_id = w.user_id
            WHERE w.status = 'pending' ORDER BY w.id ASC LIMIT 15
            """
        )
        rows = await cur.fetchall()
    if not rows:
        await safe_edit(call, tg(T_PAY, "🛒") + " × <b>Заявки на вывод.</b>\n━━━━━━━━━━━━━━━━\nАктивных заявок нет.", back_to_admin_kb())
        return
    await safe_edit(
        call,
        tg(T_PAY, "🛒") + f" × <b>Заявки на вывод.</b>\n━━━━━━━━━━━━━━━━\n<b>Всего:</b> <code>{len(rows)}</code>\nКнопки под каждой заявкой ниже.",
        back_to_admin_kb()
    )
    for row in rows:
        wid, uid, amount, created, uname = row
        try:
            await call.message.answer(
                tg(T_PAY, "🛒") + f" <b>Заявка #{wid}.</b>\n"
                f"<b>Username:</b> {('@'+uname) if uname else '@username'}\n"
                f"<b>ID:</b> <code>{uid}</code>\n"
                f"<b>Сумма:</b> <code>${amount:.2f}</code>\n"
                f"{created}\n"
                "━━━━━━━━━━━━━━━━",
                reply_markup=withdraw_item_kb(wid),
                parse_mode="HTML"
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("confirm_withdraw_"))
async def confirm_withdraw(call: CallbackQuery, bot: Bot):
    if not await is_admin(call.from_user.id):
        await cb_answer(call)
        return
    withdraw_id = int(call.data.split("_")[-1])
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT user_id, amount, status FROM withdrawals WHERE id=?", (withdraw_id,))
        row = await cur.fetchone()
        if not row or row[2] != "pending":
            await cb_answer(call)
            return
        user_id, amount, _ = row
        cur = await db.execute(
            "UPDATE withdrawals SET status='paid' WHERE id=? AND status='pending'",
            (withdraw_id,),
        )
        if cur.rowcount == 0:
            await cb_answer(call)
            return
        await db.commit()
    try:
        await bot.send_message(user_id, tg(T_OK, "✅") + " × <b>Вывод оплачен.</b>\n━━━━━━━━━━━━━━━━\n" + f"<b>Сумма:</b> <code>${amount:.2f}</code>", parse_mode="HTML")
    except Exception:
        pass
    try:
        await call.message.edit_text(tg(T_OK, "✅") + " × <b>Оплачено.</b>\n━━━━━━━━━━━━━━━━\n" + f"<b>Сумма:</b> <code>${amount:.2f}</code>", parse_mode="HTML")
    except Exception:
        pass
    await cb_answer(call)


@router.callback_query(F.data.startswith("reject_withdraw_"))
async def reject_withdraw(call: CallbackQuery, bot: Bot):
    if not await is_admin(call.from_user.id):
        await cb_answer(call)
        return
    withdraw_id = int(call.data.split("_")[-1])
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT user_id, amount, status FROM withdrawals WHERE id=?", (withdraw_id,))
        row = await cur.fetchone()
        if not row or row[2] != "pending":
            await cb_answer(call)
            return
        user_id, amount, _ = row
        cur = await db.execute(
            "UPDATE withdrawals SET status='rejected' WHERE id=? AND status='pending'",
            (withdraw_id,),
        )
        if cur.rowcount == 0:
            await cb_answer(call)
            return
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        await db.commit()
    try:
        await bot.send_message(user_id, tg(T_ERR, "🚫") + " × <b>Вывод отклонён.</b>\n━━━━━━━━━━━━━━━━\n" + f"<b>Сумма:</b> <code>${amount:.2f}</code>\nВозвращена на баланс.", parse_mode="HTML")
    except Exception:
        pass
    try:
        await call.message.edit_text(tg(T_ERR, "🚫") + " × <b>Отклонено.</b>\n━━━━━━━━━━━━━━━━\n" + f"<code>${amount:.2f}</code> возвращено на баланс.", parse_mode="HTML")
    except Exception:
        pass
    await cb_answer(call)


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
        "Выдать доступ всем не заблокированным пользователям?"
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


# ---------- Админы ----------
@router.callback_query(F.data == "manage_admins")
async def manage_admins(call: CallbackQuery, state: FSMContext):
    if not await is_owner(call.from_user.id):
        await cb_answer(call)
        return
    await state.clear()
    await safe_edit(call, tg(T_ADMIN, "🛡") + " × <b>Администраторы.</b>\n━━━━━━━━━━━━━━━━\nТолько владелец может менять список.", manage_admins_kb())


@router.callback_query(F.data == "list_admins")
async def list_admins(call: CallbackQuery):
    if not await is_owner(call.from_user.id):
        await cb_answer(call)
        return
    admins = await get_admins()
    text = tg(T_LIST, "🧑‍💻") + " × <b>Список администраторов.</b>\n━━━━━━━━━━━━━━━━\n"
    for aid in admins:
        uname = await get_username(aid)
        uname_s = f"@{uname}" if uname else "@username"
        text += f"{uname_s} | <code>{aid}</code>\n"
    await safe_edit(call, text, manage_admins_kb())


@router.callback_query(F.data == "add_admin")
async def add_admin_start(call: CallbackQuery, state: FSMContext):
    if not await is_owner(call.from_user.id):
        await cb_answer(call)
        return
    await safe_edit(call, tg(T_OK, "✅") + " × <b>Добавить админа.</b>\n━━━━━━━━━━━━━━━━\nОтправьте Telegram ID.", reply_markup=cancel_kb("manage_admins"))
    await state.set_state(AdminStates.waiting_add_admin)


@router.message(AdminStates.waiting_add_admin, F.text)
async def add_admin_process(msg: Message, state: FSMContext):
    if not await is_owner(msg.from_user.id):
        return
    try:
        new_id = int(msg.text.strip())
    except ValueError:
        await msg.answer(tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\nОтправьте числовой Telegram ID.", reply_markup=cancel_kb("manage_admins"), parse_mode="HTML")
        return
    if new_id == OWNER_ID:
        await msg.answer(tg(T_INFO, "🔔") + " × <b>Уже владелец.</b>\n━━━━━━━━━━━━━━━━\nЭто уже владелец.", reply_markup=manage_admins_kb(), parse_mode="HTML")
        await state.clear()
        return
    await add_admin(new_id)
    await state.clear()
    try:
        await msg.delete()
    except Exception:
        pass


@router.callback_query(F.data == "remove_admin")
async def remove_admin_start(call: CallbackQuery, state: FSMContext):
    if not await is_owner(call.from_user.id):
        await cb_answer(call)
        return
    await safe_edit(call, tg(T_ERR, "🚫") + " × <b>Удалить админа.</b>\n━━━━━━━━━━━━━━━━\nОтправьте Telegram ID.", reply_markup=cancel_kb("manage_admins"))
    await state.set_state(AdminStates.waiting_remove_admin)


@router.message(AdminStates.waiting_remove_admin, F.text)
async def remove_admin_process(msg: Message, state: FSMContext):
    if not await is_owner(msg.from_user.id):
        return
    try:
        admin_id = int(msg.text.strip())
    except ValueError:
        await msg.answer(tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\nОтправьте числовой Telegram ID.", reply_markup=cancel_kb("manage_admins"), parse_mode="HTML")
        return
    if admin_id == OWNER_ID:
        await msg.answer(tg(T_ERR, "🚫") + " × <b>Ошибка.</b>\n━━━━━━━━━━━━━━━━\nВладельца удалить нельзя.", reply_markup=manage_admins_kb(), parse_mode="HTML")
        await state.clear()
        return
    await remove_admin(admin_id)
    await state.clear()
    try:
        await msg.delete()
    except Exception:
        pass


# ---------- Выплаты (панель) ----------
@router.callback_query(F.data == "wd_panel")
async def wd_panel(call: CallbackQuery):
    if not await require_admin(call):
        return
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'")
        n_pending = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM withdrawals WHERE status='paid'")
        n_paid = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM withdrawals WHERE status='rejected'")
        n_rej = (await cur.fetchone())[0]
    text = (
        tg(T_PAY, "🛒") + " × <b>Выплаты.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"<b>Активных:</b> <code>{n_pending}</code>\n"
        f"<b>Оплаченных:</b> <code>{n_paid}</code>\n"
        f"<b>Отклонённых:</b> <code>{n_rej}</code>"
    )
    await show_menu(call, text, wd_panel_kb())


@router.callback_query(F.data.in_({"wd_list_pending", "wd_list_paid", "wd_list_rejected"}))
async def wd_list(call: CallbackQuery):
    if not await require_admin(call):
        return
    status_map = {
        "wd_list_pending": ("pending", "Активные заявки"),
        "wd_list_paid": ("paid", "Оплаченные"),
        "wd_list_rejected": ("rejected", "Отклонённые"),
    }
    st, title = status_map[call.data]
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            SELECT w.id, w.user_id, w.amount, u.username
            FROM withdrawals w LEFT JOIN users u ON u.user_id = w.user_id
            WHERE w.status=? ORDER BY w.id DESC LIMIT 20
            """,
            (st,),
        )
        rows = await cur.fetchall()
    if not rows:
        await show_menu(call, tg(T_PAY, "🛒") + f" × <b>{title}.</b>\n━━━━━━━━━━━━━━━━\nЗаявок нет.", wd_panel_kb())
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    text = tg(T_PAY, "🛒") + f" × <b>{title}.</b>\n━━━━━━━━━━━━━━━━\n"
    for wid, uid, amount, uname in rows:
        uname_s = f"@{uname}" if uname else "@username"
        if st == "pending":
            text += f"{uname_s} | <code>{uid}</code> — <code>${amount:.2f}</code>\n"
            b.button(text=f"#{wid} ${amount:.2f}", callback_data=f"wd_open_{wid}")
        else:
            text += f"{uname_s} | <code>{uid}</code> — <code>${amount:.2f}</code>\n"
    b.button(text="Назад", callback_data="wd_panel")
    if st == "pending":
        b.adjust(1)
    else:
        b.adjust(1)
    await show_menu(call, text, b.as_markup())


@router.callback_query(F.data.regexp(r"^wd_open_\d+$"))
async def wd_open(call: CallbackQuery):
    if not await require_admin(call):
        return
    wid = int(call.data.split("_")[-1])
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            SELECT w.user_id, w.amount, w.status, u.username
            FROM withdrawals w LEFT JOIN users u ON u.user_id = w.user_id
            WHERE w.id=?
            """,
            (wid,),
        )
        row = await cur.fetchone()
    if not row or row[2] != "pending":
        await cb_answer(call)
        return
    uid, amount, status, uname = row
    uname_s = f"@{uname}" if uname else "@username"
    text = (
        tg(T_PAY, "🛒") + f" × <b>Заявка #{wid}.</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"<b>От:</b> {uname_s}\n"
        f"<b>ID:</b> <code>{uid}</code>\n"
        f"<b>Сумма:</b> <code>${amount:.2f}</code>"
    )
    await show_menu(call, text, wd_item_actions_kb(wid, uid))


@router.callback_query(F.data.regexp(r"^wd_mark_paid_\d+$"))
async def wd_mark_paid(call: CallbackQuery, bot: Bot):
    if not await require_admin(call):
        return
    wid = int(call.data.split("_")[-1])
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT user_id, amount, status FROM withdrawals WHERE id=?", (wid,))
        row = await cur.fetchone()
        if not row or row[2] != "pending":
            await cb_answer(call)
            return
        uid, amount, _ = row
        await db.execute("UPDATE withdrawals SET status='paid' WHERE id=? AND status='pending'", (wid,))
        await db.commit()
    try:
        await bot.send_message(
            uid,
            tg(T_OK, "✅") + " × <b>Вывод оплачен.</b>\n━━━━━━━━━━━━━━━━\n"
            f"<b>Сумма:</b> <code>${amount:.2f}</code>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb_answer(call)
    # refresh panel
    call.data = "wd_list_pending"
    await wd_list(call)


@router.callback_query(F.data.regexp(r"^wd_reject_\d+$"))
async def wd_reject(call: CallbackQuery, bot: Bot):
    if not await require_admin(call):
        return
    wid = int(call.data.split("_")[-1])
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT user_id, amount, status FROM withdrawals WHERE id=?", (wid,))
        row = await cur.fetchone()
        if not row or row[2] != "pending":
            await cb_answer(call)
            return
        uid, amount, _ = row
        cur = await db.execute(
            "UPDATE withdrawals SET status='rejected' WHERE id=? AND status='pending'", (wid,)
        )
        if cur.rowcount:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
        await db.commit()
    try:
        await bot.send_message(
            uid,
            tg(T_ERR, "🚫") + " × <b>Вывод отклонён.</b>\n━━━━━━━━━━━━━━━━\n"
            f"<code>${amount:.2f}</code> возвращено на баланс.",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb_answer(call)
    call.data = "wd_list_pending"
    await wd_list(call)

