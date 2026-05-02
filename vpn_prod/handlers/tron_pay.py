import aiohttp
import random
from typing import Optional, Dict
from loguru import logger
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import db_compat as aiosqlite
from handlers.database import db

class TronPayAPI:
    """API для работы с TronScan и USDT TRC20"""
    
    def __init__(self):
        self.tronscan_api = "https://apilist.tronscanapi.com/api"
        self.binance_api = "https://api.binance.com/api/v3"
        
    async def get_usdt_to_rub_rate(self) -> float:
        """Получение актуального курса USDT к RUB из нескольких источников"""
        providers = [
            ("CoinGecko", self._get_rate_from_coingecko),
            ("Binance", self._get_rate_from_binance),
            ("ExchangeRateHost", self._get_rate_from_exchangerate_host),
        ]

        for provider_name, provider in providers:
            try:
                rate = await provider()
                if rate and rate > 0:
                    rounded_rate = round(rate, 2)
                    logger.info(f"Курс USDT/RUB ({provider_name}): {rounded_rate}")
                    return rounded_rate
                logger.warning(f"Пустой курс USDT/RUB от провайдера {provider_name}")
            except Exception as e:
                logger.warning(f"Не удалось получить курс от {provider_name}: {e}")

        fallback_rate = 90.0
        logger.warning(f"Используется резервный курс USDT/RUB: {fallback_rate}")
        return fallback_rate

    async def _get_rate_from_coingecko(self) -> Optional[float]:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=rub"
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                return float(data['tether']['rub'])

    async def _get_rate_from_binance(self) -> Optional[float]:
        async with aiohttp.ClientSession() as session:
            url = f"{self.binance_api}/ticker/price?symbol=USDTRUB"
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                return float(data['price'])

    async def _get_rate_from_exchangerate_host(self) -> Optional[float]:
        async with aiohttp.ClientSession() as session:
            url = "https://api.exchangerate.host/latest?base=USD&symbols=RUB"
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                rate = data.get('rates', {}).get('RUB')
                return float(rate) if rate else None
    
    def convert_rub_to_usdt(self, rub_amount: float, rate: float) -> float:
        """Конвертация рублей в USDT"""
        usdt_amount = rub_amount / rate
        return round(usdt_amount, 2)  # Округляем до 2 знаков
    
    def generate_unique_amount(self, base_amount: float) -> float:
        """Генерация уникальной суммы с небольшой разбежкой"""
        # Добавляем случайную разбежку от 0.01 до 0.99 USDT
        random_cents = random.randint(1, 99) / 100
        unique_amount = base_amount + random_cents
        return round(unique_amount, 6)  # Точность до 6 знаков для USDT
    
    async def check_transaction(self, wallet_address: str, expected_amount: float,
                                time_window_minutes: int = 15) -> Optional[Dict]:
        """
        Проверка транзакции на кошельке TRC20
        
        Args:
            wallet_address: Адрес USDT TRC20 кошелька
            expected_amount: Ожидаемая сумма в USDT
            time_window_minutes: Временное окно проверки в минутах
        
        Returns:
            dict с данными транзакции при успехе, None если не найдена
        """
        try:
            wallet_upper = wallet_address.upper()
            expected = Decimal(str(expected_amount))
            tolerance = Decimal('0.0001')  # допускаем разницу из-за округления

            # Используем TronScan API для проверки транзакций
            async with aiohttp.ClientSession() as session:
                url = f"{self.tronscan_api}/contract/events"
                params = {
                    'address': wallet_address,
                    'event_name': 'Transfer',
                    'limit': 50,
                    'start': 0,
                    'sort': '-timestamp'
                }

                async with session.get(url, params=params, timeout=10) as response:
                    if response.status != 200:
                        logger.error(f"Ошибка при запросе TronScan API: {response.status}")
                        return None

                    data = await response.json()

                    transactions = data.get('data', [])
                    if not transactions:
                        logger.warning("Нет транзакций для проверки")
                        return None

                    time_threshold = datetime.utcnow() - timedelta(minutes=time_window_minutes)
                    time_threshold_ms = int(time_threshold.timestamp() * 1000)

                    logger.info(
                        f"Проверка {len(transactions)} транзакций на сумму {expected} USDT за последние {time_window_minutes} минут"
                    )

                    for transaction in transactions:
                        print(transaction)
                        try:
                            tx_timestamp = int(transaction.get('timestamp', 0))
                        except (TypeError, ValueError):
                            continue

                        if tx_timestamp < time_threshold_ms:
                            continue

                        to_address = (transaction.get('transferToAddress') or '').upper()
                        if to_address != wallet_upper:
                            continue

                        token_name = (transaction.get('tokenName') or '').lower()
                        if 'tether' not in token_name:
                            continue

                        decimals_raw = transaction.get('decimals') or transaction.get('tokenDecimal') or 6
                        try:
                            decimals = int(decimals_raw)
                        except (TypeError, ValueError):
                            decimals = 6

                        amount_raw = transaction.get('amount') or transaction.get('result') or '0'
                        try:
                            amount_decimal = Decimal(str(amount_raw)) / (Decimal(10) ** decimals)
                        except (InvalidOperation, ZeroDivisionError):
                            logger.warning(f"Не удалось распарсить сумму транзакции: {amount_raw}")
                            continue

                        if abs(amount_decimal - expected) <= tolerance:
                            logger.info(
                                "✅ Найдена транзакция %s: %s USDT от %s",
                                transaction.get('transactionHash'),
                                amount_decimal,
                                transaction.get('transferFromAddress')
                            )
                            transaction['amount_parsed'] = float(amount_decimal)
                            transaction['timestamp_ms'] = tx_timestamp
                            return transaction

                    logger.warning(f"Транзакция на сумму {expected} USDT не найдена")
                    return None
        except Exception as e:
            logger.error(f"Ошибка при проверке транзакции: {e}")
            return None
    
    async def get_wallet_balance(self, wallet_address: str) -> Optional[float]:
        """Получение баланса USDT TRC20 на кошельке"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.tronscan_api}/account"
                params = {'address': wallet_address}
                
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Ошибка при получении баланса: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    # Ищем USDT в токенах
                    for token in data.get('trc20token_balances', []):
                        if token.get('tokenAbbr') == 'USDT':
                            balance = float(token.get('balance', '0'))
                            decimals = int(token.get('tokenDecimal', 6))
                            usdt_balance = balance / (10 ** decimals)
                            return usdt_balance
                    
                    return 0.0
        except Exception as e:
            logger.error(f"Ошибка при получении баланса кошелька: {e}")
            return None

class TronPayManager:
    """Менеджер для управления криптоплатежами USDT TRC20"""
    
    def __init__(self):
        self.api = TronPayAPI()
    
    async def get_crypto_settings(self) -> Optional[Dict]:
        """Получение настроек криптоплатежей"""
        try:
            async with aiosqlite.connect(db.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute(
                    'SELECT * FROM crypto_settings WHERE is_enable = 1 LIMIT 1'
                ) as cursor:
                    settings = await cursor.fetchone()
                    return dict(settings) if settings else None
        except Exception as e:
            logger.error(f"Ошибка при получении настроек криптоплатежей: {e}")
            return None
    
    async def create_payment(self, user_id: int, tariff_id: int, 
                           amount_rub: float) -> Optional[Dict]:
        """
        Создание платежа с уникальной суммой
        
        Returns:
            Dict с информацией о платеже или None
        """
        try:
            settings = await self.get_crypto_settings()
            if not settings or not settings.get('usdt_wallet'):
                logger.error("USDT кошелек не настроен")
                return None
            
            # Получаем курс
            rate = await self.api.get_usdt_to_rub_rate()
            if not rate:
                logger.error("Не удалось получить курс USDT/RUB")
                return None
            
            # Конвертируем рубли в USDT
            amount_usdt = self.api.convert_rub_to_usdt(amount_rub, rate)
            
            # Генерируем уникальную сумму
            unique_amount = self.api.generate_unique_amount(amount_usdt)
            
            # Время истечения - 15 минут
            expires_at = datetime.now() + timedelta(minutes=15)
            
            # Сохраняем в базу
            async with aiosqlite.connect(db.db_path) as conn:
                cursor = await conn.execute("""
                    INSERT INTO crypto_pending_payments 
                    (user_id, tariff_id, amount_rub, amount_usdt, unique_amount_usdt, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, tariff_id, amount_rub, amount_usdt, unique_amount, expires_at))
                await conn.commit()
                payment_id = cursor.lastrowid
            
            logger.info(f"Создан платеж #{payment_id} для пользователя {user_id}: {unique_amount} USDT")
            
            return {
                'payment_id': payment_id,
                'wallet': settings['usdt_wallet'],
                'amount_rub': amount_rub,
                'amount_usdt': amount_usdt,
                'unique_amount_usdt': unique_amount,
                'rate': rate,
                'expires_at': expires_at
            }
            
        except Exception as e:
            logger.error(f"Ошибка при создании платежа: {e}")
            return None
    
    async def check_payment(self, payment_id: int) -> Dict:
        """
        Проверка статуса платежа
        
        Returns:
            Dict со статусом проверки
        """
        try:
            # Получаем информацию о платеже
            async with aiosqlite.connect(db.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute(
                    'SELECT * FROM crypto_pending_payments WHERE id = ?',
                    (payment_id,)
                ) as cursor:
                    payment = await cursor.fetchone()
            
            if not payment:
                return {
                    'success': False,
                    'message': 'Платеж не найден',
                    'code': 'payment_not_found'
                }
            
            payment = dict(payment)
            
            # Проверяем, не истек ли платеж
            expires_at = datetime.fromisoformat(payment['expires_at'])
            if datetime.now() > expires_at:
                # Обновляем статус
                async with aiosqlite.connect(db.db_path) as conn:
                    await conn.execute(
                        'UPDATE crypto_pending_payments SET status = ? WHERE id = ?',
                        ('expired', payment_id)
                    )
                    await conn.commit()
                return {
                    'success': False,
                    'message': 'Время ожидания платежа истекло',
                    'code': 'expired'
                }
            
            # Проверяем статус
            if payment['status'] == 'paid':
                return {
                    'success': False,
                    'message': 'Платеж уже обработан',
                    'code': 'already_paid'
                }
            
            if payment['status'] == 'expired':
                return {
                    'success': False,
                    'message': 'Платеж истек',
                    'code': 'expired'
                }
            
            # Получаем адрес кошелька
            settings = await self.get_crypto_settings()
            if not settings or not settings.get('usdt_wallet'):
                return {
                    'success': False,
                    'message': 'Ошибка конфигурации',
                    'code': 'config_error'
                }
            
            # Проверяем транзакцию
            transaction_info = await self.api.check_transaction(
                wallet_address=settings['usdt_wallet'],
                expected_amount=payment['unique_amount_usdt'],
                time_window_minutes=15
            )
            
            if transaction_info:
                # Обновляем статус платежа
                async with aiosqlite.connect(db.db_path) as conn:
                    await conn.execute(
                        'UPDATE crypto_pending_payments SET status = ? WHERE id = ?',
                        ('paid', payment_id)
                    )
                    await conn.commit()
                
                payment['status'] = 'paid'
                payment['tx_hash'] = transaction_info.get('transactionHash')
                payment['tx_timestamp'] = transaction_info.get('timestamp_ms')
                logger.info(f"✅ Платеж #{payment_id} подтвержден")
                return {
                    'success': True,
                    'message': 'Платеж подтвержден',
                    'payment': payment
                }
            else:
                return {
                    'success': False,
                    'message': 'Транзакция не найдена. Пожалуйста, подождите или проверьте правильность суммы.',
                    'code': 'not_found',
                    'payment': payment
                }
                
        except Exception as e:
            logger.error(f"Ошибка при проверке платежа: {e}")
            return {
                'success': False,
                'message': f'Ошибка при проверке: {str(e)}',
                'code': 'error'
            }
    
    async def cleanup_expired_payments(self):
        """Очистка истекших платежей"""
        try:
            async with aiosqlite.connect(db.db_path) as conn:
                await conn.execute("""
                    UPDATE crypto_pending_payments 
                    SET status = 'expired' 
                    WHERE status = 'pending' AND datetime(expires_at) < datetime('now')
                """)
                await conn.commit()
                logger.info("Очистка истекших платежей выполнена")
        except Exception as e:
            logger.error(f"Ошибка при очистке истекших платежей: {e}")

tron_pay_manager = TronPayManager()

