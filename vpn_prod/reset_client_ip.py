"""
Утилита для сброса IP-адреса клиента
Используется когда клиент сменил провайдера или переехал
"""

import asyncio
import aiosqlite
from loguru import logger
import sys

async def get_user_subscriptions(user_telegram_id: int):
    """Получение подписок пользователя"""
    db_path = 'instance/database.db'
    
    try:
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT 
                    us.id,
                    us.user_id,
                    us.first_ip,
                    us.is_active,
                    us.start_date,
                    us.end_date,
                    t.name as tariff_name,
                    s.name as server_name
                FROM user_subscription us
                JOIN tariff t ON us.tariff_id = t.id
                JOIN server_settings s ON us.server_id = s.id
                WHERE us.user_id = ?
                ORDER BY us.id DESC
            """, (user_telegram_id,)) as cursor:
                subscriptions = await cursor.fetchall()
                return [dict(row) for row in subscriptions]
    except Exception as e:
        logger.error(f"Ошибка при получении подписок: {e}")
        return []


async def reset_ip(subscription_id: int):
    """Сброс IP-адреса для подписки"""
    db_path = 'instance/database.db'
    
    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute(
                "UPDATE user_subscription SET first_ip = NULL WHERE id = ?",
                (subscription_id,)
            )
            await conn.commit()
        
        logger.success(f"✅ IP-адрес сброшен для подписки ID {subscription_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при сбросе IP: {e}")
        return False


async def main():
    """Главная функция"""
    
    print("=" * 60)
    print("🔧 УТИЛИТА СБРОСА IP-АДРЕСА КЛИЕНТА")
    print("=" * 60)
    print()
    
    # Запрашиваем Telegram ID пользователя
    try:
        user_telegram_id = int(input("Введите Telegram ID пользователя: "))
    except ValueError:
        print("❌ Ошибка: Введите корректный числовой ID")
        return
    
    # Получаем подписки пользователя
    subscriptions = await get_user_subscriptions(user_telegram_id)
    
    if not subscriptions:
        print(f"❌ Подписки не найдены для пользователя {user_telegram_id}")
        return
    
    print(f"\n📋 Найдено подписок: {len(subscriptions)}\n")
    
    # Показываем список подписок
    for idx, sub in enumerate(subscriptions, 1):
        status = "✅ Активна" if sub['is_active'] else "❌ Неактивна"
        ip_status = f"🔒 IP: {sub['first_ip']}" if sub['first_ip'] else "⚪ IP не установлен"
        
        print(f"{idx}. Подписка ID: {sub['id']}")
        print(f"   Тариф: {sub['tariff_name']}")
        print(f"   Сервер: {sub['server_name']}")
        print(f"   Статус: {status}")
        print(f"   {ip_status}")
        print(f"   Период: {sub['start_date']} → {sub['end_date']}")
        print()
    
    # Запрашиваем номер подписки для сброса
    try:
        choice = input("Введите номер подписки для сброса IP (или 'all' для всех): ").strip()
        
        if choice.lower() == 'all':
            # Сбрасываем IP для всех подписок
            confirm = input(f"⚠️  Сбросить IP для ВСЕХ {len(subscriptions)} подписок? (yes/no): ").strip().lower()
            if confirm == 'yes':
                success_count = 0
                for sub in subscriptions:
                    if await reset_ip(sub['id']):
                        success_count += 1
                        await asyncio.sleep(0.1)
                
                print(f"\n✅ Сброшено IP для {success_count} из {len(subscriptions)} подписок")
            else:
                print("❌ Отменено")
        else:
            idx = int(choice)
            if 1 <= idx <= len(subscriptions):
                subscription = subscriptions[idx - 1]
                
                # Подтверждение
                print(f"\n⚠️  Вы собираетесь сбросить IP для подписки:")
                print(f"   ID: {subscription['id']}")
                print(f"   Тариф: {subscription['tariff_name']}")
                print(f"   Текущий IP: {subscription['first_ip'] or 'не установлен'}")
                
                confirm = input("\nПродолжить? (yes/no): ").strip().lower()
                
                if confirm == 'yes':
                    if await reset_ip(subscription['id']):
                        print("\n✅ IP успешно сброшен!")
                        print("ℹ️  При следующем подключении будет установлен новый IP")
                    else:
                        print("\n❌ Ошибка при сбросе IP")
                else:
                    print("\n❌ Отменено")
            else:
                print("❌ Неверный номер подписки")
                
    except ValueError:
        print("❌ Ошибка: Введите корректный номер")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

