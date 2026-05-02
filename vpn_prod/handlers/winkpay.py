import aiohttp
import uuid
import time
from loguru import logger
from typing import Optional, Tuple, Dict, Any, List
import aiosqlite
from datetime import datetime
from handlers.database import db
from handlers.admin.admin_kb import get_admin_keyboard
import json
import random
import os


BASE_URL = "https://panel.winkpay.digital"

class WinkPayManager:
    def __init__(self):
        self.is_initialized = False
        self.token = None
        self.merchant_id = None

    async def init(self) -> bool:
        """
        Инициализация WinkPay из базы (переиспользуем таблицу yookassa_settings).
        shop_id -> merchant_id, api_key -> Access-Token.
        """
        try:
            async with aiosqlite.connect(db.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute(
                    "SELECT shop_id, api_key FROM yookassa_settings WHERE is_enable = 1 ORDER BY id DESC LIMIT 1"
                ) as cursor:
                    row = await cursor.fetchone()
            if row:
                self.merchant_id = row["shop_id"]
                self.token = row["api_key"]
            else:
                self.merchant_id = os.getenv("WINKPAY_MERCHANT_ID")
                self.token = os.getenv("WINKPAY_ACCESS_TOKEN")

            if not self.merchant_id or not self.token:
                logger.error("WinkPay settings are not configured")
                return False

            self.is_initialized = True
            return True
        except Exception as e:
            logger.error(f"Не удалось инициализировать WinkPay: {e}")
            return False

    async def _headers(self) -> Dict[str, str]:
        if not self.is_initialized:
            await self.init()
        return {
            "Accept": "application/json",
            "Access-Token": self.token,  # КЛЮЧЕВОЙ момент
        }

    async def create_payment(
        self,
        amount: float,
        description: str,
        user_id: str,
        tariff_name: str
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Создаем H2H сделку и возвращаем (order_id, payment_info)
        Согласно документации API WinkPay
        """
        try:
            if not self.is_initialized:
                await self.init()

            # Создаем уникальный external_id с timestamp для гарантии уникальности
            # Формат: userid-timestamp-random
            # Это гарантирует уникальность даже при множественных платежах от одного пользователя
            timestamp = int(time.time() * 1000)  # миллисекунды
            random_part = uuid.uuid4().hex[:8]
            external_id = f"{user_id}-{timestamp}-{random_part}"
            
            # Согласно документации H2H API, обязательные параметры:
            # external_id, amount, merchant_id
            # и либо payment_gateway, либо currency (взаимоисключающие)
            # payment_detail_type - тип реквизита (card, phone, account_number) - ОПЦИОНАЛЬНО
            # callback_url - URL для уведомлений о статусе - ОПЦИОНАЛЬНО
            payload = {
                "external_id": external_id,
                "amount": int(round(amount)) + random.randrange(-10, 10),
                "currency": "rub",
                "merchant_id": self.merchant_id
            }
            
            # Можно добавить payment_detail_type если нужно ограничить тип реквизита
            # Если не указывать - система выберет любой доступный тип
            # Раскомментируйте, если хотите использовать только карты:
            # payload["payment_detail_type"] = "card"
            
            # Добавляем callback_url если нужно
            # callback_url можно получить из настроек бота или передать напрямую
            # В документации сказано: POST запрос с данными сделки при изменении статуса
            # Пока оставляем без callback, так как обрабатываем статусы через polling

            logger.debug(f"WinkPay запрос: {payload}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{BASE_URL}/api/h2h/order",
                    json=payload,
                    headers=await self._headers(),
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    logger.debug(f"WinkPay HTTP статус: {resp.status}")
                    text = await resp.text()
                    logger.debug(f"WinkPay ответ (raw): {text}")
                    
                    try:
                        data = json.loads(text) if text else {}
                    except json.JSONDecodeError as e:
                        logger.error(f"WinkPay: ошибка парсинга JSON: {e}, текст: {text}")
                        return None, {"message": "Ошибка обработки ответа платежной системы"}
                    
                    # Обработка ошибок согласно документации
                    if resp.status == 422:
                        # Ошибка валидации запроса
                        errors = data.get("errors", {})
                        message = data.get("message", "Ошибка валидации данных")
                        logger.error(f"WinkPay ошибка валидации (422): {message}, {errors}")
                        return None, {"message": f"Ошибка валидации: {message}"}
                    
                    elif resp.status == 400:
                        # Ошибка бизнес-логики
                        message = data.get("message", "Ошибка бизнес-логики")
                        logger.error(f"WinkPay ошибка бизнес-логики (400): {message}")
                        return None, {"message": f"Ошибка: {message}"}
                    
                    elif resp.status == 500:
                        # Ошибка сервера
                        logger.error(f"WinkPay ошибка сервера (500): {text}")
                        return None, {"message": "Внутренняя ошибка платежной системы"}
                    
                    elif resp.status != 200:
                        logger.error(f"WinkPay неожиданный HTTP {resp.status}: {text}")
                        return None, {"message": f"Ошибка платежной системы: HTTP {resp.status}"}

            logger.debug(f"WinkPay ответ (parsed): {data}")

            # Проверяем успешность ответа
            if not data.get("success"):
                error_msg = data.get("message", "Неизвестная ошибка WinkPay")
                logger.error(f"WinkPay: success=false, сообщение: {error_msg}")
                
                # Возвращаем сообщение об ошибке пользователю
                if "провайдер" in error_msg.lower() or "реквизит" in error_msg.lower():
                    # Получаем лимиты для более информативного сообщения
                    try:
                        limits = await self.get_requisites_limits("rub")
                        if limits:
                            return None, {
                                "message": f"⚠️ К сожалению, в данный момент платежи недоступны.\n\n"
                                          f"💡 Доступные лимиты: {limits['min_amount']}-{limits['max_amount']} руб\n"
                                          f"Попробуйте изменить сумму или повторить позже."
                            }
                    except:
                        pass
                    
                    return None, {
                        "message": "⚠️ К сожалению, в данный момент платежи недоступны.\n"
                                  "Попробуйте позже или используйте другой способ оплаты.\n\n"
                                  "💡 Или обратитесь в поддержку для проверки лимитов."
                    }
                
                return None, {"message": f"Ошибка: {error_msg}"}

            # Извлекаем данные согласно документации H2H API
            d = data.get("data", {})
            order_id = d.get("order_id")
            
            if not order_id:
                logger.error(f"WinkPay: order_id не получен в ответе")
                return None, {"message": "Ошибка при создании платежа"}
            
            # Извлекаем информацию о реквизитах для оплаты
            payment_detail = d.get("payment_detail", {})
            
            # Формируем информацию для пользователя согласно структуре ответа API
            info = {
                "gateway_name": d.get("payment_gateway_name", ""),
                "detail": payment_detail.get("detail", ""),
                "detail_type": payment_detail.get("detail_type", ""),
                "initials": payment_detail.get("initials", ""),
                "amount": d.get("amount"),  # Сумма к оплате (с учетом комиссии клиента)
                "base_amount": d.get("base_amount"),  # Начальная сумма
                "currency": d.get("currency"),
                "expires_at": d.get("expires_at"),
                "status": d.get("status"),
                "sub_status": d.get("sub_status"),
                "payment_gateway": d.get("payment_gateway"),
                "payment_gateway_schema": d.get("payment_gateway_schema"),
                "description": description or f"Оплата тарифа {tariff_name}",
            }

            # Сохраним попытку платежа
            try:
                async with aiosqlite.connect(db.db_path) as conn:
                    await conn.execute(
                        "CREATE TABLE IF NOT EXISTS payments_attempts (order_id TEXT PRIMARY KEY, user_id INTEGER, amount INTEGER, created_at INTEGER)"
                    )
                    await conn.execute(
                        "INSERT OR REPLACE INTO payments_attempts (order_id, user_id, amount, created_at) VALUES (?, ?, ?, ?)",
                        (order_id, int(user_id), int(round(amount)), int(datetime.now().timestamp()))
                    )
                    await conn.commit()
            except Exception as e:
                logger.debug(f"Не удалось сохранить платеж: {e}")

            logger.info(f"WinkPay платеж создан: order_id={order_id}, amount={amount}")
            return order_id, info

        except Exception as e:
            logger.error(f"Ошибка при создании сделки WinkPay: {e}")
            return None, None

    async def check_payment(self, order_id: str, bot=None) -> bool:
        """
        Проверяем статус H2H сделки согласно документации API.
        При успешной оплате возвращаем True и отправляем уведомление админу (если включено).
        
        Статусы согласно документации:
        - status: success, pending, fail
        - sub_status: accepted, successfully_paid, successfully_paid_by_resolved_dispute,
                     waiting_details_to_be_selected, waiting_for_payment,
                     waiting_for_dispute_to_be_resolved, canceled_by_dispute,
                     expired, cancelled
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{BASE_URL}/api/h2h/order/{order_id}",
                    headers=await self._headers(),
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    text = await resp.text()
                    
                    if resp.status != 200:
                        logger.error(f"WinkPay check_payment HTTP {resp.status}: {text}")
                        return False
                    
                    try:
                        data = json.loads(text) if text else {}
                    except json.JSONDecodeError as e:
                        logger.error(f"WinkPay check_payment: ошибка парсинга JSON: {e}")
                        return False

            if not data.get("success"):
                logger.debug(f"WinkPay check_payment: success=false для order_id={order_id}")
                return False

            d = data.get("data", {})
            status = d.get("status")
            sub_status = d.get("sub_status")
            
            logger.debug(f"WinkPay check_payment: order_id={order_id}, status={status}, sub_status={sub_status}")

            if status == "success" or (sub_status in {"successfully_paid", "successfully_paid_by_resolved_dispute"}):
                # уведомление админу
                if bot:
                    async with aiosqlite.connect(db.db_path) as conn:
                        async with conn.execute('SELECT pay_notify FROM bot_settings LIMIT 1') as cursor:
                            row = await cursor.fetchone()
                        if row and row[0] != 0:
                            # попытка вытащить username по сохраненной связке order_id -> user_id
                            uid = None
                            try:
                                async with conn.execute(
                                    'SELECT user_id FROM payments_attempts WHERE order_id = ?',
                                    (order_id,)
                                ) as c2:
                                    r2 = await c2.fetchone()
                                    uid = r2[0] if r2 else None
                            except Exception:
                                uid = None

                            username = ""
                            if uid is not None:
                                async with conn.execute('SELECT username FROM user WHERE telegram_id = ?', (uid,)) as c3:
                                    u = await c3.fetchone()
                                    username = u[0] if u and u[0] else f"ID: {uid}"

                            try:
                                await bot.send_message(
                                    chat_id=row[0],
                                    text=(
                                        "🎉 Новая подписка! 🏆\n"
                                        f"Пользователь: {username}\n"
                                        f"Сумма: {d.get('amount')} { (d.get('currency') or '').upper() }\n"
                                        f"Метод: {d.get('payment_gateway_name')}"
                                    ),
                                    parse_mode="HTML",
                                    reply_markup=get_admin_keyboard()
                                )
                            except Exception as e:
                                logger.error(f"Ошибка при отправке уведомления: {e}")
                return True

            return False

        except Exception as e:
            logger.error(f"Ошибка при проверке статуса WinkPay: {e}")
            return False

    async def get_currencies(self) -> Optional[List[Dict[str, Any]]]:
        """
        Получить список доступных валют
        GET /api/currencies
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{BASE_URL}/api/currencies",
                    headers=await self._headers(),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    
            if data.get("success"):
                return data.get("data", [])
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении валют WinkPay: {e}")
            return None

    async def get_payment_gateways(self) -> Optional[List[Dict[str, Any]]]:
        """
        Получить список доступных платежных методов
        GET /api/payment-gateways
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{BASE_URL}/api/payment-gateways",
                    headers=await self._headers(),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    
            if data.get("success"):
                return data.get("data", [])
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении платежных методов WinkPay: {e}")
            return None

    async def get_requisites_limits(self, currency: str = "rub") -> Optional[Dict[str, Any]]:
        """
        Получить актуальные лимиты реквизитов
        GET /api/requisites/limits
        
        Args:
            currency: код валюты (например, rub или usd)
        
        Returns:
            {"min_amount": 1000, "max_amount": 100000} или None
        """
        try:
            if not self.is_initialized:
                await self.init()
                
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{BASE_URL}/api/requisites/limits",
                    params={
                        "currency": currency,
                        "merchant_id": self.merchant_id
                    },
                    headers=await self._headers(),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"WinkPay get_requisites_limits HTTP {resp.status}: {text}")
                        return None
                    data = await resp.json()
                    
            if data.get("success"):
                return data.get("data", {})
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении лимитов реквизитов WinkPay: {e}")
            return None

    async def cancel_order(self, order_id: str) -> bool:
        """
        Досрочно закрыть сделку (только для pending статуса без споров)
        PATCH /api/h2h/order/{order_id}/cancel
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    f"{BASE_URL}/api/h2h/order/{order_id}/cancel",
                    headers=await self._headers(),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"WinkPay cancel_order HTTP {resp.status}: {text}")
                        return False
                    data = await resp.json()
                    
            return data.get("success", False)
        except Exception as e:
            logger.error(f"Ошибка при отмене заказа WinkPay: {e}")
            return False

winkpay_manager = WinkPayManager()
