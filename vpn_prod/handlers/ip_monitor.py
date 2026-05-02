"""
Модуль для мониторинга IP-адресов клиентов VPN
Автоматически запускается как фоновая задача
"""

import asyncio
import db_compat as aiosqlite
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
                    us.client_uuid,
                    us.client_email,
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


async def get_client_info(api: py3xui.AsyncApi, inbound_id: int, client_email: str) -> Optional[Dict]:
    """Получение информации о клиенте через API"""
    try:
        # Получаем всех клиентов inbound
        try:
            clients_response = api.client.get_by_email(email=client_email)
        except TypeError as type_error:
            try:
                clients_response = api.client.get_by_email(inbound_id, client_email)
            except TypeError:
                raise type_error
        
        if clients_response and hasattr(clients_response, 'obj'):
            client_data = clients_response.obj
            if isinstance(client_data, list) and len(client_data) > 0:
                client = client_data[0]
            else:
                client = client_data
            
            return {
                'email': getattr(client, 'email', ''),
                'enable': getattr(client, 'enable', False),
                'up': getattr(client, 'up', 0),
                'down': getattr(client, 'down', 0),
            }
        
        return None
        
    except Exception as e:
        logger.debug(f"Не удалось получить информацию о клиенте: {e}")
        return None


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
        api.client.update(inbound_id, client_uuid, enable=False)
        
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
    """Мониторинг IP для одной подписки
    
    ПРИМЕЧАНИЕ: 3x-ui API не предоставляет прямой доступ к IP-адресам клиентов.
    Эта функция служит основой для будущей реализации, когда такая возможность появится.
    
    Возможные способы получения IP:
    1. Парсинг логов 3x-ui сервера
    2. Использование расширенного API (если появится в будущих версиях)
    3. Настройка webhooks для логирования подключений
    """
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
        client_uuid = subscription.get('client_uuid') or await extract_client_uuid(subscription['vless'])
        if not client_uuid:
            result['status'] = 'error'
            result['message'] = 'Не удалось извлечь UUID из VLESS ключа'
            return result
        
        # Извлекаем email клиента
        email_match = re.search(r'#(.+)$', subscription['vless'])
        client_email = subscription.get('client_email') or (email_match.group(1) if email_match else f"tg_{subscription['user_id']}")
        
        # Определяем протокол
        protocol = 'https' if subscription.get('connection_method', 0) == 1 else 'http'
        url = subscription['url'].replace('https://', '').replace('http://', '')
        api_url = f"{protocol}://{url}:{subscription['port']}/{subscription['secret_path']}"
        
        # Подключаемся к 3x-ui
        api = py3xui.Api(
            host=api_url,
            username=subscription['username'],
            password=subscription['password'],
            use_tls_verify=False
        )
        
        api.login()
        
        # Получаем информацию о клиенте
        client_info = await get_client_info(api, subscription['inbound_id'], client_email)
        
        if not client_info:
            result['message'] = 'Клиент не найден или не активен'
            return result
        
        # Проверяем, есть ли трафик (признак активности)
        has_traffic = (client_info['up'] > 0 or client_info['down'] > 0)
        
        if has_traffic and not subscription['first_ip']:
            # Клиент активен, но IP пока не сохранен
            # В будущем здесь можно добавить логику получения IP
            result['status'] = 'needs_ip'
            result['message'] = 'Клиент активен, IP будет сохранен при наличии данных'
        else:
            result['message'] = 'Клиент активен' if has_traffic else 'Клиент не активен'
            
    except Exception as e:
        result['status'] = 'error'
        result['message'] = f'Ошибка: {str(e)}'
        logger.debug(f"Ошибка при мониторинге подписки {subscription['id']}: {e}")
    
    return result


async def monitor_all_clients():
    """Основная функция мониторинга всех клиентов"""
    try:
        logger.debug("🔍 Проверка IP-адресов клиентов...")
        
        subscriptions = await get_active_subscriptions()
        
        if not subscriptions:
            return
        
        stats = {
            'ok': 0,
            'needs_ip': 0,
            'blocked': 0,
            'error': 0
        }
        
        # Обрабатываем подписки
        for subscription in subscriptions:
            result = await monitor_subscription_ip(subscription)
            
            # Обновляем статистику
            if result['status'] in stats:
                stats[result['status']] += 1
            
            # Логируем только важные события
            if result['action'] == 'blocked':
                logger.warning(f"🚫 User {result['user_id']} ({result['server_name']}): {result['message']}")
            elif result['status'] == 'error':
                logger.debug(f"⚠️ User {result['user_id']} ({result['server_name']}): {result['message']}")
            
            # Небольшая задержка между запросами
            await asyncio.sleep(0.3)
        
        # Логируем статистику только если есть что сообщить
        if stats['blocked'] > 0 or stats['error'] > 0:
            logger.info(f"IP Monitor: OK={stats['ok']}, Needs IP={stats['needs_ip']}, Blocked={stats['blocked']}, Errors={stats['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при мониторинге IP: {e}")


async def start_ip_monitoring(bot):
    """Запуск мониторинга IP-адресов клиентов"""
    logger.info("🚀 Запуск мониторинга IP-адресов клиентов")
    logger.info("⏱️  Интервал проверки: 10 минут")
    logger.info("ℹ️  Примечание: Для полноценной работы требуется расширенный API 3x-ui")
    
    while True:
        try:
            await monitor_all_clients()
        except Exception as e:
            logger.error(f"Ошибка в цикле мониторинга IP: {e}")
        
        # Проверяем каждые 10 минут
        await asyncio.sleep(600)

