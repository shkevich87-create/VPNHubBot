import os
import aiohttp
import asyncio
import logging
from typing import Optional

from bot.keyboards.inline.user_inline import pay_and_check
from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.language import get_lang, Localization

log = logging.getLogger(__name__)
_ = Localization.text

WINKPAY_BASE = os.getenv("WINKPAY_BASE_URL", "https://panel.winkpay.digital")

class WinkPay:
    """
    Провайдер WinkPay Merchant API:
    - создаём сделку: POST /api/merchant/order
    - получаем payment_link
    - опционально пуллим статус GET /api/merchant/order/{order_id} ограниченное время
    Интерфейс совместим с существующими провайдерами (to_pay/invoice).
    """
    def __init__(self, config, message, user_id: int, price: int, data):
        self.config = config
        self.message = message
        self.user_id = user_id
        self.price = int(price)
        # data переиспользуем как external_id, если есть
        self.external_id = str(data) if data else f"INV-{user_id}-{int(asyncio.get_event_loop().time()*1000)}"

        self.token = os.getenv("WINKPAY_API_TOKEN")
        self.merchant_id = os.getenv("WINKPAY_MERCHANT_ID")
        self.callback_url = os.getenv("WINKPAY_CALLBACK_URL", "")  # POST
        self.success_url = os.getenv("WINKPAY_SUCCESS_URL", "")    # GET
        self.fail_url    = os.getenv("WINKPAY_FAIL_URL", "")       # GET
        self.max_wait_ms = os.getenv("WINKPAY_MAX_WAIT_MS", "30000")

        if not self.token or not self.merchant_id:
            raise ValueError("WINKPAY_API_TOKEN / WINKPAY_MERCHANT_ID не заданы в .env")

        self.headers = {
            "Accept": "application/json",
            "Access-Token": self.token,
            "X-Max-Wait-Ms": self.max_wait_ms
        }

    async def _post(self, path: str, json_payload: dict):
        async with aiohttp.ClientSession(headers=self.headers) as s:
            async with s.post(f"{WINKPAY_BASE}{path}", json=json_payload,
                              timeout=aiohttp.ClientTimeout(total=40)) as r:
                data = await r.json()
                if r.status != 200 or not data.get("success"):
                    raise RuntimeError(f"WinkPay POST {path} error: {r.status} {data}")
                return data["data"]

    async def _get(self, path: str):
        async with aiohttp.ClientSession(headers=self.headers) as s:
            async with s.get(f"{WINKPAY_BASE}{path}",
                             timeout=aiohttp.ClientTimeout(total=30)) as r:
                data = await r.json()
                if r.status != 200 or not data.get("success"):
                    raise RuntimeError(f"WinkPay GET {path} error: {r.status} {data}")
                return data["data"]

    async def create_order(self, currency: str = "rub",
                           payment_detail_type: Optional[str] = None,
                           payment_gateway: Optional[str] = None,
                           manually: int = 1) -> dict:
        payload = {
            "external_id": self.external_id,
            "amount": self.price,
            "merchant_id": self.merchant_id,
            "callback_url": self.callback_url,
            "success_url": self.success_url,
            "fail_url": self.fail_url,
            "manually": str(manually),
        }
        if payment_gateway:
            payload["payment_gateway"] = payment_gateway
        else:
            payload["currency"] = currency
        if payment_detail_type:
            payload["payment_detail_type"] = payment_detail_type

        created = await self._post("/api/merchant/order", payload)
        return created

    async def get_order(self, order_id: str) -> dict:
        return await self._get(f"/api/merchant/order/{order_id}")

    async def invoice(self) -> str:
        created = await self.create_order(currency="rub", manually=1)
        self._last_order = created
        return created.get("payment_link")

    async def _poll_until_done(self, order_id: str, timeout_sec: int = 600, interval_sec: int = 7):
        """
        Опросуим статус pending → success/fail ограниченное время.
        """
        deadline = asyncio.get_event_loop().time() + timeout_sec
        while asyncio.get_event_loop().time() < deadline:
            try:
                od = await self.get_order(order_id)
                status = od.get("status")
                if status in ("success", "fail"):
                    return od
            except Exception as e:
                log.warning(f"WinkPay poll error: {e}")
            await asyncio.sleep(interval_sec)
        return None

    async def to_pay(self):
        lang_user = await get_lang(self.user_id)
        try:
            created = await self.create_order(currency="rub", manually=1)
        except Exception as e:
            log.error(f"WinkPay create_order failed: {e}")
            await self.message.answer(_("error_payment_system", lang_user))
            return

        link = created.get("payment_link")
        order_id = created.get("order_id")
        await self.message.answer(
            _("payment_balance_text", lang_user).format(price=self.price),
            reply_markup=await pay_and_check(link, lang_user)
        )
        log.info(f"WinkPay link created for user {self.user_id} order {order_id}")

        # Не блокируем UX: пробуем негромкий опрос статуса
        try:
            polled = await self._poll_until_done(order_id, timeout_sec=600, interval_sec=7)
            if polled and polled.get("status") == "success":
                ps = PaymentSystem(self.message, self.user_id, price=self.price)
                await ps.successful_payment(self.price, "WinkPay")
        except Exception as e:
            log.warning(f"WinkPay poll exception: {e}")

    def __str__(self):
        return "Платежная система WinkPay"
