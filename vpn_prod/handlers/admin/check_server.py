import aiohttp
import asyncio
from typing import Dict
from loguru import logger
import time

async def check_server_availability(server: Dict) -> Dict:
    """Проверка доступности сервера и измерение задержки"""
    
    # Определяем протокол на основе connection_method
    connection_method = server.get('connection_method', False)
    protocol = 'https' if connection_method else 'http'
    
    # Берем URL и очищаем его
    base_url = server['url']
    # Удаляем протокол если он есть
    if base_url.startswith('http://') or base_url.startswith('https://'):
        base_url = base_url.split('://', 1)[1]
    
    # Удаляем порт из URL если он там есть
    if ':' in base_url:
        base_url = base_url.split(':')[0]
    
    # Формируем полный URL для проверки
    secret_path = server.get('secret_path', '').strip('/')
    if secret_path:
        url = f"{protocol}://{base_url}:{server['port']}/{secret_path}/"
    else:
        url = f"{protocol}://{base_url}:{server['port']}/"
    
    try:
        start_time = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5, ssl=False) as response:
                end_time = time.time()
                delay = round((end_time - start_time) * 1000)
                
                logger.info(f"Проверка сервера {url}: статус {response.status}")
                return {
                    'available': True,
                    'delay': delay,
                    'status_code': response.status
                }
    except asyncio.TimeoutError:
        logger.error(f"Таймаут при проверке сервера {url}")
        return {
            'available': False,
            'delay': None,
            'status_code': None
        }
    except Exception as e:
        logger.error(f"Ошибка при проверке сервера {url}: {e}")
        return {
            'available': False,
            'delay': None,
            'status_code': None
        }

async def check_all_servers(servers: list[Dict]) -> list[Dict]:
    """Проверка всех серверов"""
    for server in servers:
        result = await check_server_availability(server)
        server.update(result)
    return servers
