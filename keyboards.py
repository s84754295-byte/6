from aiogram.utils.keyboard import InlineKeyboardBuilder
from emojis import *


def main_menu(user_id: int, is_admin: bool = False):
    b = InlineKeyboardBuilder()
    b.button(text="Сдать", callback_data="submit_menu", icon_custom_emoji_id=B_SUBMIT)
    b.button(text="Кабинет", callback_data="profile", icon_custom_emoji_id=B_PROFILE)
    b.button(text="Вывод", callback_data="withdraw", icon_custom_emoji_id=B_WITHDRAW)
    b.button(text="История", callback_data="my_numbers", icon_custom_emoji_id=B_MY)
    b.button(text="Очередь", callback_data="public_queue", icon_custom_emoji_id=B_QUEUE)
    b.button(text="Помощь", callback_data="support", icon_custom_emoji_id=B_SUPPORT)
    if is_admin:
        b.button(text="Панель", callback_data="admin_panel", icon_custom_emoji_id=B_ADMIN)
        b.adjust(1, 2, 2, 1, 1)
    else:
        b.adjust(1, 2, 2, 1)
    return b.as_markup()


def support_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Написать", url="https://t.me/forestmx", icon_custom_emoji_id=B_SUPPORT)
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


def admin_panel_kb(is_owner: bool = False, bot_enabled: bool = True):
    b = InlineKeyboardBuilder()
    b.button(text="Выплаты", callback_data="wd_panel", icon_custom_emoji_id=B_PAY)
    b.button(text="Цены", callback_data="price_menu", icon_custom_emoji_id=B_MIN)
    b.button(text="Инфо", callback_data="stats", icon_custom_emoji_id=B_STATS)
    b.button(text="Рассылка", callback_data="broadcast", icon_custom_emoji_id=B_CAST)
    if bot_enabled:
        b.button(text="Стоп", callback_data="bot_stop", icon_custom_emoji_id=B_STOP)
    else:
        b.button(text="Старт", callback_data="bot_start", icon_custom_emoji_id=B_START)
    b.button(text="Очистка", callback_data="clear_queue_menu", icon_custom_emoji_id=B_CLR_REG)
    if is_owner:
        b.button(text="Админы", callback_data="manage_admins", icon_custom_emoji_id=B_ADMINS)
        b.button(text="Главная", callback_data="main_menu", icon_custom_emoji_id=B_HOME)
        b.adjust(2, 2, 2, 1, 1)
    else:
        b.button(text="Главная", callback_data="main_menu", icon_custom_emoji_id=B_HOME)
        b.adjust(2, 2, 2, 1)
    return b.as_markup()



def price_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="MAX • Нерег", callback_data="set_price_unregistered", icon_custom_emoji_id=B_PRICE_NEW)
    b.button(text="MAX • Рег", callback_data="set_price_registered", icon_custom_emoji_id=B_PRICE_REG)
    b.button(text="Мин. вывод", callback_data="set_min_withdraw", icon_custom_emoji_id=B_MIN)
    b.button(text="Назад", callback_data="admin_panel", icon_custom_emoji_id=B_BACK)
    b.adjust(2, 1, 1)
    return b.as_markup()


def queue_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="MAX • Нерег", callback_data="queue_unregistered", icon_custom_emoji_id=B_CAT_NEW)
    b.button(text="MAX • Рег", callback_data="queue_registered", icon_custom_emoji_id=B_CAT_REG)
    b.button(text="Вся очередь", callback_data="queue_all", icon_custom_emoji_id=B_AQUEUE)
    b.button(text="Назад", callback_data="admin_panel", icon_custom_emoji_id=B_BACK)
    b.adjust(3, 1)
    return b.as_markup()


def clear_queue_confirm_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Удалить", callback_data="clear_q_yes_all", icon_custom_emoji_id=B_CLR_OK)
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


def back_to_admin_kb():
    return back_kb("admin_panel")


def number_request_kb(number_id: int, user_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="Запр.", callback_data=f"reqcode_{number_id}_{user_id}", icon_custom_emoji_id=B_CODE)
    b.button(text="Откл.", callback_data=f"cancelnum_{number_id}_{user_id}", icon_custom_emoji_id=B_REJECT)
    b.adjust(2)
    return b.as_markup()


def number_confirm_kb(number_id: int, user_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="Прин.", callback_data=f"confirmnum_{number_id}_{user_id}", icon_custom_emoji_id=B_ACCEPT)
    b.button(text="Откл.", callback_data=f"rejectnum_{number_id}_{user_id}", icon_custom_emoji_id=B_REJECT)
    b.adjust(2)
    return b.as_markup()


def withdraw_confirm_user_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Подтвердить", callback_data="withdraw_user_yes", icon_custom_emoji_id=B_YES)
    b.button(text="Назад", callback_data="withdraw_user_no", icon_custom_emoji_id=B_BACK)
    b.adjust(1, 1)
    return b.as_markup()


def withdraw_item_kb(withdraw_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="Оплатить", callback_data=f"confirm_withdraw_{withdraw_id}", icon_custom_emoji_id=B_PAY)
    b.button(text="Откл.", callback_data=f"reject_withdraw_{withdraw_id}", icon_custom_emoji_id=B_DECLINE)
    b.adjust(2)
    return b.as_markup()


def withdraw_action_kb(withdraw_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="Оплатить", callback_data=f"confirm_withdraw_{withdraw_id}", icon_custom_emoji_id=B_PAY)
    b.button(text="Откл.", callback_data=f"reject_withdraw_{withdraw_id}", icon_custom_emoji_id=B_DECLINE)
    b.button(text="В админ-панель", callback_data="admin_panel", icon_custom_emoji_id=B_BACK)
    b.adjust(2, 1)
    return b.as_markup()


def manage_admins_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Добавить", callback_data="add_admin", icon_custom_emoji_id=B_ADD)
    b.button(text="Удалить", callback_data="remove_admin", icon_custom_emoji_id=B_DEL)
    b.button(text="Список", callback_data="list_admins", icon_custom_emoji_id=B_LIST)
    b.button(text="Назад", callback_data="admin_panel", icon_custom_emoji_id=B_BACK)
    b.adjust(2, 1, 1)
    return b.as_markup()


def access_panel_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Открыть всем", callback_data="grant_all_access", icon_custom_emoji_id=B_GRANT_ALL)
    b.button(text="Закрыть всем", callback_data="revoke_all_access", icon_custom_emoji_id=B_REVOKE_ALL)
    b.button(text="Без доступа", callback_data="list_no_access", icon_custom_emoji_id=B_NOACC)
    b.button(text="С доступом", callback_data="list_with_access", icon_custom_emoji_id=B_YESACC)
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


CHANNEL_URL = "https://t.me/forest_afisha"


def subscribe_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Подписаться на канал", url=CHANNEL_URL, icon_custom_emoji_id=B_CAST)
    b.button(text="Проверить подписку", callback_data="check_sub", icon_custom_emoji_id=B_YES)
    b.adjust(1, 1)
    return b.as_markup()


def wd_item_actions_kb(withdraw_id: int, user_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="Оплатить", url=f"tg://user?id={user_id}", icon_custom_emoji_id=B_PAY)
    b.button(text="Оплачено", callback_data=f"wd_mark_paid_{withdraw_id}", icon_custom_emoji_id=B_ACCEPT)
    b.button(text="Откл.", callback_data=f"wd_reject_{withdraw_id}", icon_custom_emoji_id=B_REJECT)
    b.button(text="Назад", callback_data="wd_panel", icon_custom_emoji_id=B_BACK)
    b.adjust(2, 1, 1)
    return b.as_markup()


def wd_panel_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Оплач.", callback_data="wd_list_paid", icon_custom_emoji_id=B_ACCEPT)
    b.button(text="Откл.", callback_data="wd_list_rejected", icon_custom_emoji_id=B_REJECT)
    b.button(text="Актив.", callback_data="wd_list_pending", icon_custom_emoji_id=B_PAY)
    b.button(text="Назад", callback_data="admin_panel", icon_custom_emoji_id=B_BACK)
    b.adjust(2, 1, 1)
    return b.as_markup()
