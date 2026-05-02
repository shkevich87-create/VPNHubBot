"""
Скрипт для мониторинга IP-адресов через логи серверов
Использует SSH для чтения логов Xray/3x-ui
"""

import asyncio
from loguru import logger
from handlers.log_parser import monitor_all_servers_logs, test_log_parser


async def main():
    """Главная функция"""
    try:
        logger.add("logs/ip_monitor_logs.log", rotation="10 MB", level="DEBUG")
        
        print("=" * 60)
        print("🔍 МОНИТОРИНГ IP ЧЕРЕЗ ЛОГИ СЕРВЕРОВ")
        print("=" * 60)
        print()
        
        # Запускаем мониторинг
        stats = await monitor_all_servers_logs()
        
        print("\n✅ Мониторинг завершен!")
        print(f"📄 Подробный лог: logs/ip_monitor_logs.log")
        
        if stats:
            print(f"\n📊 Результаты:")
            print(f"   • Обработано: {stats['processed']}")
            print(f"   • Новых IP: {stats['new_ips']}")
            print(f"   • Заблокировано: {stats['blocked']}")
            print(f"   • Ошибок: {stats['errors']}")
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())

