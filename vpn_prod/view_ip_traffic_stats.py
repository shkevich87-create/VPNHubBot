"""
Скрипт для просмотра статистики по IP и трафику
Показывает общую информацию о тарифах и подписках
"""

import asyncio
import aiosqlite
from loguru import logger
from datetime import datetime


async def get_tariff_stats():
    """Статистика по тарифам"""
    db_path = 'instance/database.db'
    
    try:
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            # Общая статистика
            async with conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN traffic_limit_gb = 0 THEN 1 END) as unlimited,
                    COUNT(CASE WHEN traffic_limit_gb > 0 THEN 1 END) as limited,
                    AVG(CASE WHEN traffic_limit_gb > 0 THEN traffic_limit_gb END) as avg_limit,
                    MIN(CASE WHEN traffic_limit_gb > 0 THEN traffic_limit_gb END) as min_limit,
                    MAX(traffic_limit_gb) as max_limit
                FROM tariff
                WHERE is_enable = 1
            """) as cursor:
                stats = dict(await cursor.fetchone())
            
            # Детали по тарифам
            async with conn.execute("""
                SELECT 
                    id,
                    name,
                    price,
                    left_day,
                    max_devices,
                    traffic_limit_gb,
                    is_enable
                FROM tariff
                ORDER BY price DESC
            """) as cursor:
                tariffs = [dict(row) for row in await cursor.fetchall()]
            
            return stats, tariffs
            
    except Exception as e:
        logger.error(f"Ошибка при получении статистики тарифов: {e}")
        return None, []


async def get_subscription_stats():
    """Статистика по подпискам"""
    db_path = 'instance/database.db'
    
    try:
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            # Общая статистика
            async with conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN is_active = 1 THEN 1 END) as active,
                    COUNT(CASE WHEN is_active = 0 THEN 1 END) as inactive,
                    COUNT(CASE WHEN first_ip IS NOT NULL THEN 1 END) as with_ip,
                    COUNT(CASE WHEN first_ip IS NULL THEN 1 END) as without_ip
                FROM user_subscription
            """) as cursor:
                stats = dict(await cursor.fetchone())
            
            # IP статистика
            async with conn.execute("""
                SELECT 
                    first_ip,
                    COUNT(*) as count
                FROM user_subscription
                WHERE first_ip IS NOT NULL AND is_active = 1
                GROUP BY first_ip
                ORDER BY count DESC
                LIMIT 10
            """) as cursor:
                ip_stats = [dict(row) for row in await cursor.fetchall()]
            
            return stats, ip_stats
            
    except Exception as e:
        logger.error(f"Ошибка при получении статистики подписок: {e}")
        return None, []


async def get_detailed_subscriptions():
    """Детальная информация о активных подписках"""
    db_path = 'instance/database.db'
    
    try:
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            async with conn.execute("""
                SELECT 
                    us.id,
                    us.user_id,
                    us.first_ip,
                    us.start_date,
                    us.end_date,
                    t.name as tariff_name,
                    t.traffic_limit_gb,
                    t.max_devices,
                    s.name as server_name,
                    u.username
                FROM user_subscription us
                JOIN tariff t ON us.tariff_id = t.id
                JOIN server_settings s ON us.server_id = s.id
                JOIN user u ON us.user_id = u.telegram_id
                WHERE us.is_active = 1
                ORDER BY us.start_date DESC
                LIMIT 20
            """) as cursor:
                subscriptions = [dict(row) for row in await cursor.fetchall()]
            
            return subscriptions
            
    except Exception as e:
        logger.error(f"Ошибка при получении детальной информации: {e}")
        return []


async def main():
    """Главная функция"""
    
    print("=" * 80)
    print("📊 СТАТИСТИКА ПО IP И ТРАФИКУ")
    print("=" * 80)
    print()
    
    # 1. Статистика по тарифам
    print("🎯 ТАРИФЫ")
    print("-" * 80)
    
    tariff_stats, tariffs = await get_tariff_stats()
    
    if tariff_stats:
        print(f"Всего тарифов: {tariff_stats['total']}")
        print(f"  • Безлимитных: {tariff_stats['unlimited']}")
        print(f"  • С лимитом: {tariff_stats['limited']}")
        
        if tariff_stats['avg_limit']:
            print(f"  • Средний лимит: {tariff_stats['avg_limit']:.0f} ГБ")
            print(f"  • Минимум: {tariff_stats['min_limit']:.0f} ГБ")
            print(f"  • Максимум: {tariff_stats['max_limit']:.0f} ГБ")
        
        print("\nДетали тарифов:")
        print(f"{'ID':<5} {'Название':<20} {'Цена':<10} {'Дней':<8} {'Устр':<6} {'Трафик':<15} {'Статус'}")
        print("-" * 80)
        
        for tariff in tariffs:
            traffic = f"{tariff['traffic_limit_gb']} ГБ" if tariff['traffic_limit_gb'] > 0 else "Безлимит"
            devices = f"{tariff['max_devices']}" if tariff['max_devices'] > 0 else "∞"
            status = "✅" if tariff['is_enable'] else "❌"
            
            print(f"{tariff['id']:<5} {tariff['name'][:19]:<20} {tariff['price']:<10.0f} {tariff['left_day']:<8} {devices:<6} {traffic:<15} {status}")
    
    print()
    
    # 2. Статистика по подпискам
    print("👥 ПОДПИСКИ")
    print("-" * 80)
    
    sub_stats, ip_stats = await get_subscription_stats()
    
    if sub_stats:
        print(f"Всего подписок: {sub_stats['total']}")
        print(f"  • Активных: {sub_stats['active']}")
        print(f"  • Неактивных: {sub_stats['inactive']}")
        print(f"  • С установленным IP: {sub_stats['with_ip']} ({sub_stats['with_ip']/sub_stats['total']*100:.1f}%)")
        print(f"  • Без IP: {sub_stats['without_ip']} ({sub_stats['without_ip']/sub_stats['total']*100:.1f}%)")
        
        if ip_stats:
            print("\nТоп-10 IP по количеству подписок:")
            for idx, ip in enumerate(ip_stats, 1):
                print(f"  {idx}. {ip['first_ip']}: {ip['count']} подписок")
    
    print()
    
    # 3. Детальная информация
    print("📋 АКТИВНЫЕ ПОДПИСКИ (последние 20)")
    print("-" * 80)
    
    subscriptions = await get_detailed_subscriptions()
    
    if subscriptions:
        print(f"{'ID':<6} {'User':<15} {'Тариф':<20} {'IP':<16} {'Трафик':<10} {'Устр'}")
        print("-" * 80)
        
        for sub in subscriptions:
            username = (sub['username'] or f"ID{sub['user_id']}")[:14]
            tariff_name = sub['tariff_name'][:19]
            ip = sub['first_ip'] or "Не установлен"
            traffic = f"{sub['traffic_limit_gb']} ГБ" if sub['traffic_limit_gb'] > 0 else "∞"
            devices = f"{sub['max_devices']}" if sub['max_devices'] > 0 else "∞"
            
            print(f"{sub['id']:<6} {username:<15} {tariff_name:<20} {ip:<16} {traffic:<10} {devices}")
    else:
        print("Нет активных подписок")
    
    print()
    print("=" * 80)
    
    # Рекомендации
    print("\n💡 РЕКОМЕНДАЦИИ:")
    
    if sub_stats and sub_stats['without_ip'] > 0:
        print(f"  • {sub_stats['without_ip']} подписок без IP - запустите monitor_client_ips.py")
    
    if tariff_stats and tariff_stats['unlimited'] == tariff_stats['total']:
        print("  • Все тарифы безлимитные - рассмотрите добавление лимитов для оптимизации")
    
    if ip_stats:
        duplicate_ips = [ip for ip in ip_stats if ip['count'] > 1]
        if duplicate_ips:
            print(f"  ⚠️  Обнаружено {len(duplicate_ips)} IP с несколькими подписками - возможно передача конфигов")
    
    print()


if __name__ == "__main__":
    asyncio.run(main())

