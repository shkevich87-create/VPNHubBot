"""
Скрипт для мониторинга IP-адресов клиентов VPN
Функции:
1. Запоминает IP-адрес первого подключения клиента
2. Блокирует клиента если обнаружено подключение с другого IP
3. Предотвращает передачу конфигов другим пользователям
"""

import asyncio
import aiosqlite
import re
from datetime import datetime
from loguru import logger
from typing import List, Dict, Optional
import py3xui

from handlers.database import db


async def get_active_subscriptions() -> List[Dict]:
    """Получение активных подписок"""
    try:
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT 
                    us.id,
                    us.user_id,
                    us.vless,
                    us.server_id,
                    us.first_ip,
                    s.url,
                    s.port,
                    s.secret_path,
                    s.username,
                    s.password,
                    s.inbound_id,
                    s.connection_method,
                    s.name as server_name
                FROM user_subscription us
                JOIN server_settings s ON us.server_id = s.id
                WHERE us.is_active = 1
            """) as cursor:
                subscriptions = await cursor.fetchall()
                return [dict(row) for row in subscriptions]
    except Exception as e:
        logger.error(f"Ошибка при получении активных подписок: {e}")
        return []


async def extract_client_uuid(vless_link: str) -> Optional[str]:
    """Извлечение UUID клиента из VLESS ключа"""
    uuid_match = re.search(r'vless://([^@]+)@', vless_link)
    if uuid_match:
        return uuid_match.group(1)
    return None


async def get_client_ips(api: py3xui.AsyncApi, inbound_id: int, client_uuid: str) -> List[str]:
    """Получение списка IP-адресов клиента из статистики"""
    try:
        # Получаем статистику клиента
        # API 3x-ui может предоставить информацию о подключениях
        # В зависимости от версии 3x-ui, метод может отличаться
        
        # Получаем информацию о клиенте
        client_info = await api.client.get_ips(client_uuid)
        
        if client_info and hasattr(client_info, 'ips'):
            return client_info.ips
        
        return []
        
    except Exception as e:
        logger.debug(f"Не удалось получить IP клиента {client_uuid}: {e}")
        return []


async def update_first_ip(subscription_id: int, ip_address: str) -> bool:
    """Сохранение первого IP-адреса клиента"""
    try:
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                "UPDATE user_subscription SET first_ip = ? WHERE id = ?",
                (ip_address, subscription_id)
            )
            await conn.commit()
        logger.info(f"✅ Сохранен первый IP {ip_address} для подписки ID {subscription_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении IP: {e}")
        return False


async def block_client(api: py3xui.AsyncApi, inbound_id: int, client_uuid: str, subscription_id: int, reason: str) -> bool:
    """Блокировка клиента (отключение enable)"""
    try:
        # Отключаем клиента в 3x-ui
        await api.client.update(inbound_id, client_uuid, enable=False)
        
        # Деактивируем в БД
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                "UPDATE user_subscription SET is_active = 0 WHERE id = ?",
                (subscription_id,)
            )
            await conn.commit()
        
        logger.warning(f"🚫 Клиент заблокирован: {reason}")
        logger.warning(f"   Подписка ID: {subscription_id}, UUID: {client_uuid}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при блокировке клиента: {e}")
        return False


async def monitor_subscription_ip(subscription: Dict) -> Dict:
    """Мониторинг IP для одной подписки"""
    result = {
        'subscription_id': subscription['id'],
        'user_id': subscription['user_id'],
        'server_name': subscription['server_name'],
        'status': 'ok',
        'message': '',
        'action': None
    }
    
    try:
        # Извлекаем UUID клиента
        client_uuid = await extract_client_uuid(subscription['vless'])
        if not client_uuid:
            result['status'] = 'error'
            result['message'] = 'Не удалось извлечь UUID из VLESS ключа'
            return result
        
        # Определяем протокол
        protocol = 'https' if subscription.get('connection_method', 0) == 1 else 'http'
        url = subscription['url'].replace('https://', '').replace('http://', '')
        api_url = f"{protocol}://{url}:{subscription['port']}/{subscription['secret_path']}"
        
        # Подключаемся к 3x-ui
        api = py3xui.AsyncApi(
            host=api_url,
            username=subscription['username'],
            password=subscription['password'],
            use_tls_verify=False
        )
        
        await api.login()
        
        # Получаем IP-адреса клиента
        client_ips = await get_client_ips(api, subscription['inbound_id'], client_uuid)
        
        if not client_ips:
            # Клиент еще не подключался или нет активных подключений
            result['message'] = 'Нет активных подключений'
            return result
        
        # Берем первый IP из списка (основной)
        current_ip = client_ips[0] if isinstance(client_ips, list) else client_ips
        
        # Проверяем first_ip
        if not subscription['first_ip']:
            # Сохраняем первый IP
            await update_first_ip(subscription['id'], current_ip)
            result['status'] = 'first_ip_saved'
            result['message'] = f'Сохранен первый IP: {current_ip}'
            result['action'] = 'saved_ip'
            
        elif subscription['first_ip'] != current_ip:
            # IP изменился - блокируем клиента
            reason = f"Подключение с другого IP. Ожидался: {subscription['first_ip']}, Получен: {current_ip}"
            await block_client(api, subscription['inbound_id'], client_uuid, subscription['id'], reason)
            result['status'] = 'blocked'
            result['message'] = reason
            result['action'] = 'blocked'
            
        else:
            # Все в порядке
            result['message'] = f'IP совпадает: {current_ip}'
            
    except Exception as e:
        result['status'] = 'error'
        result['message'] = f'Ошибка: {str(e)}'
        logger.error(f"Ошибка при мониторинге подписки {subscription['id']}: {e}")
    
    return result


async def monitor_all_clients():
    """Основная функция мониторинга всех клиентов"""
    try:
        logger.info("=" * 60)
        logger.info("🔍 МОНИТОРИНГ IP-АДРЕСОВ КЛИЕНТОВ")
        logger.info(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        subscriptions = await get_active_subscriptions()
        
        if not subscriptions:
            logger.info("Нет активных подписок для мониторинга")
            return
        
        logger.info(f"Найдено активных подписок: {len(subscriptions)}")
        
        stats = {
            'ok': 0,
            'first_ip_saved': 0,
            'blocked': 0,
            'error': 0
        }
        
        # Обрабатываем подписки последовательно
        for subscription in subscriptions:
            result = await monitor_subscription_ip(subscription)
            
            # Обновляем статистику
            if result['status'] in stats:
                stats[result['status']] += 1
            
            # Логируем важные события
            if result['action'] == 'saved_ip':
                logger.info(f"💾 User {result['user_id']} ({result['server_name']}): {result['message']}")
            elif result['action'] == 'blocked':
                logger.warning(f"🚫 User {result['user_id']} ({result['server_name']}): {result['message']}")
            elif result['status'] == 'error':
                logger.error(f"❌ User {result['user_id']} ({result['server_name']}): {result['message']}")
            
            # Небольшая задержка между запросами
            await asyncio.sleep(0.5)
        
        # Итоговая статистика
        logger.info("\n" + "=" * 60)
        logger.info("📊 СТАТИСТИКА МОНИТОРИНГА")
        logger.info("=" * 60)
        logger.info(f"✅ Все в порядке: {stats['ok']}")
        logger.info(f"💾 Сохранено первых IP: {stats['first_ip_saved']}")
        logger.info(f"🚫 Заблокировано: {stats['blocked']}")
        logger.info(f"❌ Ошибок: {stats['error']}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Критическая ошибка при мониторинге: {e}")


async def start_monitoring_loop():
    """Запуск цикла мониторинга"""
    logger.info("🚀 Запуск мониторинга IP-адресов клиентов")
    logger.info("⏱️  Интервал проверки: 5 минут")
    
    while True:
        try:
            await monitor_all_clients()
        except Exception as e:
            logger.error(f"Ошибка в цикле мониторинга: {e}")
        
        # Проверяем каждые 5 минут
        await asyncio.sleep(300)


async def main():
    """Главная функция для ручного запуска"""
    try:
        logger.add("logs/ip_monitor.log", rotation="10 MB", level="DEBUG")
        await monitor_all_clients()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())

