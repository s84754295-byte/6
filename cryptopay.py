"""
Обёртка над Crypto Pay API (@CryptoBot) + готовый клиент для бота.
Документация: https://help.send.tg/en/articles/10279948-crypto-pay-api

Схема "единый пул" (казна):
- Виртуальный баланс пользователя хранится в users.balance (как и раньше — начисляется
  за принятые номера).
- Реальные деньги лежат одним пулом на балансе приложения Crypto Pay ("казна").
- При выводе бот атомарно списывает виртуальный баланс и сразу отправляет реальные
  деньги с баланса приложения на CryptoBot-кошелёк пользователя методом transfer() —
  без участия администратора, пользователь получает деньги мгновенно.
"""
import hashlib
import hmac
import logging
from typing import Any, Optional

import aiohttp

from config import CRYPTO_PAY_TOKEN, CRYPTO_PAY_BASE_URL

logger = logging.getLogger(__name__)


class CryptoPayError(Exception):
    """Ошибка ответа Crypto Pay API."""

    def __init__(self, code: Any, message: str):
        self.code = code
        self.message = message
        super().__init__(f"CryptoPay API error [{code}]: {message}")


class CryptoPayClient:
    def __init__(self, token: str, base_url: str):
        self.token = token
        self.base_url = base_url

    def _headers(self) -> dict:
        return {"Crypto-Pay-API-Token": self.token}

    async def _request(self, method: str, params: Optional[dict] = None) -> dict:
        url = self.base_url + method
        params = {k: v for k, v in (params or {}).items() if v is not None}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self._headers(), json=params) as resp:
                data = await resp.json()
        if not data.get("ok"):
            err = data.get("error", {})
            raise CryptoPayError(err.get("code"), err.get("name", "unknown_error"))
        return data["result"]

    # ---------- Вывод средств (мгновенная выплата пользователю) ----------

    async def transfer(
        self,
        user_id: int,
        asset: str,
        amount: float,
        spend_id: str,
        comment: Optional[str] = None,
    ) -> dict:
        """
        Перевести деньги с баланса приложения (казны) на CryptoBot-кошелёк пользователя.
        user_id — Telegram ID пользователя, который ранее писал @CryptoBot.
        spend_id — уникальный ключ идемпотентности: генерируется и сохраняется в БД
        ДО вызова transfer, чтобы при обрыве соединения повторный вызов не отправил деньги дважды.
        """
        return await self._request(
            "transfer",
            {
                "user_id": user_id,
                "asset": asset,
                "amount": str(amount),
                "spend_id": spend_id,
                "comment": comment,
            },
        )

    async def get_transfers(self, transfer_ids: Optional[list[int]] = None) -> dict:
        return await self._request(
            "getTransfers",
            {"transfer_ids": ",".join(map(str, transfer_ids)) if transfer_ids else None},
        )

    # ---------- Баланс приложения (казна) ----------

    async def get_balance(self) -> list[dict]:
        """Баланс вашего Crypto Pay приложения по каждому активу — это и есть казна."""
        return await self._request("getBalance")

    async def get_me(self) -> dict:
        return await self._request("getMe")

    # ---------- Приём платежей (создание счёта — используется, если понадобится пополнение) ----------

    async def create_invoice(
        self,
        amount: float,
        asset: str = "USDT",
        description: Optional[str] = None,
        payload: Optional[str] = None,
        expires_in: Optional[int] = 3600,
    ) -> dict:
        return await self._request(
            "createInvoice",
            {
                "asset": asset,
                "amount": str(amount),
                "description": description,
                "payload": payload,
                "expires_in": expires_in,
            },
        )

    # ---------- Проверка подписи вебхука (если позже подключите приём платежей) ----------

    def check_signature(self, body: bytes, signature_header: str) -> bool:
        secret_key = hashlib.sha256(self.token.encode()).digest()
        computed = hmac.new(secret_key, body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, signature_header or "")


# Единый клиент казны на весь бот
cp = CryptoPayClient(CRYPTO_PAY_TOKEN, CRYPTO_PAY_BASE_URL)
