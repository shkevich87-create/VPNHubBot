"""
Модуль для автоматической деактивации истекших подписок
Удаляет пользователей из 3x-ui панели когда подписка истекает
"""
import asyncio
import aiosqlite
import re
from datetime import datetime
from loguru import logger
from typing import List, Dict
import py3xui

from handlers.database import db


async def get_expired_subscriptions(limit: int = 500) -> List[Dict]:
    """Получение истекших подписок, которые еще активны в БД"""
    try:
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT 
                    us.id,
                    us.user_id,
                    us.vless,
                    us.client_uuid,
                    us.server_id,
                    us.end_date,
                    s.url,
                    s.port,
                    s.secret_path,
                    s.username,
                    s.password,
                    s.inbound_id,
                    s.connection_method
                FROM user_subscription us
                JOIN server_settings s ON us.server_id = s.id
                WHERE us.is_active = 1 
                AND datetime(us.end_date) < datetime('now', 'localtime')
                ORDER BY datetime(us.end_date) ASC
                LIMIT ?
            """, (limit,)) as cursor:
                expired = await cursor.fetchall()
                return [dict(row) for row in expired]
    except Exception as e:
        logger.error(f"Ошибка при получении истекших подписок: {e}")
        return []


async def deactivate_expired_subscription(subscription: Dict) -> bool:
    """Деактивация одной истекшей подписки в 3x-ui и БД"""
    try:
        client_uuid = subscription.get('client_uuid')
        if not client_uuid:
            uuid_match = re.search(r'vless://([^@]+)@', subscription.get('vless') or '')
            if not uuid_match:
                logger.error(f"Не удалось извлечь UUID из подписки ID {subscription['id']}")
                return False
            client_uuid = uuid_match.group(1)
        
        # Определяем протокол (HTTP или HTTPS) на основе connection_method
        protocol = 'https' if subscription.get('connection_method', 0) == 1 else 'http'
        
        # Убираем протокол из URL если он там уже есть
        url = subscription['url']
        url = url.replace('https://', '').replace('http://', '')
        
        # Формируем полный URL для API
        api_url = f"{protocol}://{url}:{subscription['port']}/{subscription['secret_path']}"
        
        logger.info(f"Подключение к 3x-ui: {api_url}")
        
        # Подключаемся к 3x-ui
        api = py3xui.AsyncApi(
            host=api_url,
            username=subscription['username'],
            password=subscription['password'],
            use_tls_verify=False
        )
        
        await api.login()
        logger.info(f"Подключились к 3x-ui: {api_url}")
        
        # Удаляем клиента из inbound
        await api.client.delete(subscription['inbound_id'], client_uuid)
        logger.info(f"Клиент {client_uuid} удален из 3x-ui (inbound: {subscription['inbound_id']})")
        
        # Деактивируем подписку в БД
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                "UPDATE user_subscription SET is_active = 0 WHERE id = ?",
                (subscription['id'],)
            )
            await conn.commit()
        
        logger.info(f"✅ Подписка ID {subscription['id']} деактивирована (user: {subscription['user_id']})")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при деактивации подписки ID {subscription['id']}: {e}")
        logger.error(f"Детали: UUID={client_uuid if 'client_uuid' in locals() else 'N/A'}, URL={api_url if 'api_url' in locals() else 'N/A'}")
        
        # Деактивируем в БД даже если не удалось удалить из 3x-ui
        try:
            async with aiosqlite.connect(db.db_path) as conn:
                await conn.execute(
                    "UPDATE user_subscription SET is_active = 0 WHERE id = ?",
                    (subscription['id'],)
                )
                await conn.commit()
            logger.warning(f"⚠️ Подписка ID {subscription['id']} деактивирована только в БД (ошибка удаления из 3x-ui)")
        except Exception as db_error:
            logger.error(f"Критическая ошибка при деактивации в БД: {db_error}")
        
        return False


async def process_expired_subscriptions():
    """Основная функция обработки истекших подписок"""
    try:
        logger.info("🔍 Начало проверки истекших подписок...")
        
        expired = await get_expired_subscriptions()
        
        if not expired:
            logger.info("✅ Истекших подписок не найдено")
            return
        
        logger.info(f"⚠️ Найдено истекших подписок: {len(expired)}")
        
        success_count = 0
        failed_count = 0
        
        for subscription in expired:
            success = await deactivate_expired_subscription(subscription)
            if success:
                success_count += 1
            else:
                failed_count += 1
            
            # Небольшая задержка между запросами к API
            await asyncio.sleep(0.5)
        
        logger.info(f"📊 Обработка завершена: успешно {success_count}, ошибок {failed_count}")
        
    except Exception as e:
        logger.error(f"Критическая ошибка при обработке истекших подписок: {e}")


async def start_expiration_checker(bot):
    """Запуск планировщика проверки истекших подписок"""
    logger.info("🚀 Запуск планировщика деактивации истекших подписок")
    
    while True:
        try:
            await process_expired_subscriptions()
        except Exception as e:
            logger.error(f"Ошибка в цикле планировщика деактивации: {e}")
        
        # Проверяем каждые 5 минут
        await asyncio.sleep(300)

