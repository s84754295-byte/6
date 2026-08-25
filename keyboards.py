from aiogram.utils.keyboard import InlineKeyboardBuilder
from emojis import *


def main_menu(user_id: int, is_admin: bool = False):
    b = InlineKeyboardBuilder()
    b.button(text="MAX - CODE", callback_data="submit_menu", icon_custom_emoji_id=B_SUBMIT)
    b.button(text="Личный кабинет", callback_data="profile", icon_custom_emoji_id=B_PROFILE)
    b.button(text="Вывод средств", callback_data="withdraw", icon_custom_emoji_id=B_WITHDRAW)
    b.button(text="История заявок", callback_data="my_numbers", icon_custom_emoji_id=B_MY)
    b.button(text="Очередь номеров", callback_data="public_queue", icon_custom_emoji_id=B_QUEUE)
    b.button(text="Отменить заявку", callback_data="cancel_menu", icon_custom_emoji_id=B_CLR_REG)
    b.button(text="Служба поддержки", callback_data="support", icon_custom_emoji_id=B_SUPPORT)
    b.adjust(1, 2, 2, 1, 1)
    return b.as_markup()


def support_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Написать в поддержку", url="https://t.me/sobrovsky", icon_custom_emoji_id=B_SUPPORT)
    b.button(text="Назад", callback_data="main_menu", icon_custom_emoji_id=B_BACK)
    b.adjust(1, 1)
    return b.as_markup()


def submit_category_kb():
    b = InlineKeyboardBuilder()
    b.button(text="MAX • Нерег", callback_data="submit_cat_unregistered", icon_custom_emoji_id=B_CAT_NEW)
    b.button(text="MAX • Рег", callback_data="submit_cat_registered", icon_custom_emoji_id=B_CAT_REG)
    b.button(text="Назад", callback_data="main_menu", icon_custom_emoji_id=B_BACK)
    b.adjust(2, 1)
    return b.as_markup()


def cancel_numbers_kb(rows):
    """rows: список (number_id, seq, number) заявок пользователя в статусе 'pending'."""
    b = InlineKeyboardBuilder()
    for number_id, seq, number in rows:
        b.button(text=number, callback_data=f"user_cancel_{number_id}", icon_custom_emoji_id=B_REJECT)
    b.button(text="Назад", callback_data="main_menu", icon_custom_emoji_id=B_BACK)
    b.adjust(1)
    return b.as_markup()


def admin_panel_kb(is_owner: bool = False, bot_enabled: bool = True):
    b = InlineKeyboardBuilder()
    b.button(text="Казна", callback_data="treasury", icon_custom_emoji_id=B_PAY)
    b.button(text="Управление ценами", callback_data="price_menu", icon_custom_emoji_id=B_MIN)
    b.button(text="Информация о боте", callback_data="stats", icon_custom_emoji_id=B_STATS)
    b.button(text="Массовая рассылка", callback_data="broadcast", icon_custom_emoji_id=B_CAST)
    b.button(text="Обзор очереди", callback_data="queue_overview", icon_custom_emoji_id=B_QUEUE)
    b.button(text="Очистить очередь", callback_data="clear_queue_menu", icon_custom_emoji_id=B_CLR_REG)
    if bot_enabled:
        b.button(text="Остановить бота", callback_data="bot_stop", icon_custom_emoji_id=B_STOP)
    else:
        b.button(text="Запустить бота", callback_data="bot_start", icon_custom_emoji_id=B_START)
    b.adjust(2, 2, 2, 1)
    return b.as_markup()




def price_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="MAX • Незарегистрированный", callback_data="set_price_unregistered", icon_custom_emoji_id=B_PRICE_NEW)
    b.button(text="MAX • Зарегистрированный", callback_data="set_price_registered", icon_custom_emoji_id=B_PRICE_REG)
    b.button(text="Минимальная сумма вывода", callback_data="set_min_withdraw", icon_custom_emoji_id=B_MIN)
    b.button(text="Назад", callback_data="admin_panel", icon_custom_emoji_id=B_BACK)
    b.adjust(2, 1, 1)
    return b.as_markup()


def queue_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="MAX • Незарегистрированный", callback_data="queue_unregistered", icon_custom_emoji_id=B_CAT_NEW)
    b.button(text="MAX • Зарегистрированный", callback_data="queue_registered", icon_custom_emoji_id=B_CAT_REG)
    b.button(text="Показать всю очередь", callback_data="queue_all", icon_custom_emoji_id=B_AQUEUE)
    b.button(text="Назад", callback_data="admin_panel", icon_custom_emoji_id=B_BACK)
    b.adjust(2, 1, 1)
    return b.as_markup()


def clear_queue_confirm_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Удалить все заявки", callback_data="clear_q_yes_all", icon_custom_emoji_id=B_CLR_OK)
    b.button(text="Назад", callback_data="admin_panel", icon_custom_emoji_id=B_BACK)
    b.adjust(1, 1)
    return b.as_markup()


def cancel_kb(back_data: str = "main_menu", with_back: bool = True):
    """Только кнопка Назад (кнопки Отмена убраны везде)."""
    b = InlineKeyboardBuilder()
    b.button(text="Назад", callback_data=back_data, icon_custom_emoji_id=B_BACK)
    return b.as_markup()


def back_kb(callback_data: str = "main_menu"):
    b = InlineKeyboardBuilder()
    b.button(text="Назад", callback_data=callback_data, icon_custom_emoji_id=B_BACK)
    return b.as_markup()


def back_to_main_kb():
    return back_kb("main_menu")


def my_numbers_kb(page: int, total_pages: int):
    """Клавиатура истории номеров: кнопки страниц (если их больше одной) над кнопкой Назад."""
    b = InlineKeyboardBuilder()
    if total_pages > 1:
        for p in range(1, total_pages + 1):
            label = f"• {p} •" if p == page else str(p)
            b.button(text=label, callback_data=f"my_numbers_page_{p}")
        b.button(text="Назад", callback_data="main_menu", icon_custom_emoji_id=B_BACK)
        row_size = min(total_pages, 5)
        rows = []
        remaining = total_pages
        while remaining > 0:
            chunk = min(row_size, remaining)
            rows.append(chunk)
            remaining -= chunk
        rows.append(1)
        b.adjust(*rows)
    else:
        b.button(text="Назад", callback_data="main_menu", icon_custom_emoji_id=B_BACK)
        b.adjust(1)
    return b.as_markup()


def back_to_admin_kb():
    return back_kb("admin_panel")


def number_request_kb(number_id: int, user_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="Запросить код", callback_data=f"reqcode_{number_id}_{user_id}", icon_custom_emoji_id=B_CODE)
    b.button(text="Отклонить заявку", callback_data=f"cancelnum_{number_id}_{user_id}", icon_custom_emoji_id=B_REJECT)
    b.adjust(2)
    return b.as_markup()


def number_confirm_kb(number_id: int, user_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="Принять номер", callback_data=f"confirmnum_{number_id}_{user_id}", icon_custom_emoji_id=B_ACCEPT)
    b.button(text="Отклонить номер", callback_data=f"rejectnum_{number_id}_{user_id}", icon_custom_emoji_id=B_REJECT)
    b.adjust(2)
    return b.as_markup()


def withdraw_confirm_user_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Подтвердить вывод", callback_data="withdraw_user_yes", icon_custom_emoji_id=B_YES)
    b.button(text="Назад", callback_data="withdraw_user_no", icon_custom_emoji_id=B_BACK)
    b.adjust(1, 1)
    return b.as_markup()


def access_panel_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Открыть доступ всем", callback_data="grant_all_access", icon_custom_emoji_id=B_GRANT_ALL)
    b.button(text="Закрыть доступ всем", callback_data="revoke_all_access", icon_custom_emoji_id=B_REVOKE_ALL)
    b.button(text="Пользователи без доступа", callback_data="list_no_access", icon_custom_emoji_id=B_NOACC)
    b.button(text="Пользователи с доступом", callback_data="list_with_access", icon_custom_emoji_id=B_YESACC)
    b.button(text="Назад", callback_data="admin_panel", icon_custom_emoji_id=B_BACK)
    b.adjust(2, 2, 1)
    return b.as_markup()


def grant_all_confirm_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Да, открыть всем", callback_data="grant_all_yes", icon_custom_emoji_id=B_GRANT_ALL)
    b.button(text="Назад", callback_data="access_panel", icon_custom_emoji_id=B_BACK)
    b.adjust(1, 1)
    return b.as_markup()


def revoke_all_confirm_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Да, закрыть всем", callback_data="revoke_all_yes", icon_custom_emoji_id=B_REVOKE_ALL)
    b.button(text="Назад", callback_data="access_panel", icon_custom_emoji_id=B_BACK)
    b.adjust(1, 1)
    return b.as_markup()


CHANNEL_URL = "https://t.me/sobr_channel"


def subscribe_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Подписаться на канал", url=CHANNEL_URL, icon_custom_emoji_id=B_CAST)
    b.button(text="Проверить подписку", callback_data="check_sub", icon_custom_emoji_id=B_YES)
    b.adjust(1, 1)
    return b.as_markup()
