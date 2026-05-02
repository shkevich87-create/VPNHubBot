# Модуль для совместимости со старым кодом
# Теперь используется tron_pay.py для оплаты USDT TRC20

from loguru import logger
from handlers.tron_pay import tron_pay_manager

class CryptoPayManager:
    """Заглушка для совместимости со старым кодом"""
    
    def __init__(self):
        self.api = None
        logger.info("CryptoPayManager инициализирован (используется USDT TRC20)")
        
    async def init_api(self) -> bool:
        """Проверка доступности USDT TRC20 оплаты"""
        try:
            settings = await tron_pay_manager.get_crypto_settings()
            if settings and settings.get('usdt_wallet'):
                logger.info("USDT TRC20 оплата доступна")
                return True
            logger.warning("USDT TRC20 кошелек не настроен")
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке настроек USDT TRC20: {e}")
            return False

# Глобальный экземпляр менеджера для совместимости
crypto_pay_manager = CryptoPayManager() 