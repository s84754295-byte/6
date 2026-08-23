"""Временные действия админа (номер / вывод), т.к. reply-кнопки без callback_data."""

# admin_id -> dict
_admin_number: dict[int, dict] = {}
_admin_withdraw: dict[int, dict] = {}


def set_number_action(admin_id: int, number_id: int, user_id: int, number: str = "", mode: str = "request"):
    """mode: request | confirm"""
    _admin_number[admin_id] = {
        "number_id": number_id,
        "user_id": user_id,
        "number": number,
        "mode": mode,
    }


def get_number_action(admin_id: int) -> dict | None:
    return _admin_number.get(admin_id)


def clear_number_action(admin_id: int):
    _admin_number.pop(admin_id, None)


def set_withdraw_action(admin_id: int, withdraw_id: int, user_id: int = 0, amount: float = 0):
    _admin_withdraw[admin_id] = {
        "withdraw_id": withdraw_id,
        "user_id": user_id,
        "amount": amount,
    }


def get_withdraw_action(admin_id: int) -> dict | None:
    return _admin_withdraw.get(admin_id)


def clear_withdraw_action(admin_id: int):
    _admin_withdraw.pop(admin_id, None)
