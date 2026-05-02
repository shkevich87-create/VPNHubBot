"""
Модуль для парсинга логов 3x-ui/Xray и извлечения IP-адресов клиентов
Работает с access.log файлами на удаленных серверах
"""

import re
import asyncio
import aiosqlite
from loguru import logger
from typing import Dict, List, Optional, Set
from datetime import datetime
import paramiko
from io import StringIO

from handlers.database import db


class LogParser:
    """Парсер логов Xray для извлечения IP-адресов"""
    
    def __init__(self):
        # Регулярное выражение для парсинга логов Xray
        # Формат: [timestamp] [level] [app/proxyman/inbound] email:192.168.1.1:port
        self.ip_pattern = re.compile(
            r'email:([a-zA-Z0-9_@.]+).*?from\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',
            re.IGNORECASE
        )
        
        # Альтернативный паттерн
        self.alt_pattern = re.compile(
            r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):\d+\s+accepted.*?email:([a-zA-Z0-9_@.]+)',
            re.IGNORECASE
        )
        
        # Паттерн для простого формата: IP ... email
        self.simple_pattern = re.compile(
            r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?([a-zA-Z0-9_@.]+@\d+)',
            re.IGNORECASE
        )
    
    def parse_log_line(self, line: str) -> Optional[Dict[str, str]]:
        """
        Парсинг одной строки лога
        Возвращает: {"email": "tg_123@456", "ip": "192.168.1.1"}
        """
        # Пробуем первый паттерн
        match = self.ip_pattern.search(line)
        if match:
            return {
                "email": match.group(1),
                "ip": match.group(2)
            }
        
        # Пробуем альтернативный паттерн
        match = self.alt_pattern.search(line)
        if match:
            return {
                "ip": match.group(1),
                "email": match.group(2)
            }
        
        # Пробуем простой паттерн
        match = self.simple_pattern.search(line)
        if match:
            return {
                "ip": match.group(1),
                "email": match.group(2)
            }
        
        return None
    
    def parse_log_content(self, content: str) -> Dict[str, Set[str]]:
        """
        Парсинг содержимого лог-файла
        Возвращает: {"email1": {"ip1", "ip2"}, "email2": {"ip3"}}
        """
        email_ips = {}
        
        for line in content.split('\n'):
            if not line.strip():
                continue
            
            parsed = self.parse_log_line(line)
            if parsed:
                email = parsed['email']
                ip = parsed['ip']
                
                if email not in email_ips:
                    email_ips[email] = set()
                email_ips[email].add(ip)
        
        return email_ips


class RemoteLogReader:
    """Чтение логов с удаленного сервера через SSH"""
    
    def __init__(self, host: str, port: int, username: str, password: str, log_path: str = "/var/log/xray/access.log"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.log_path = log_path
    
    async def read_logs(self, lines: int = 1000) -> Optional[str]:
        """
        Чтение последних N строк лога через SSH
        """
        try:
            # Создаем SSH подключение
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Подключаемся
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: ssh.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=10,
                    look_for_keys=False,
                    allow_agent=False
                )
            )
            
            # Читаем последние N строк
            command = f"tail -n {lines} {self.log_path}"
            stdin, stdout, stderr = ssh.exec_command(command)
            
            # Получаем вывод
            output = stdout.read().decode('utf-8', errors='ignore')
            error = stderr.read().decode('utf-8', errors='ignore')
            
            ssh.close()
            
            if error and "No such file" in error:
                logger.warning(f"Лог файл не найден на {self.host}: {self.log_path}")
                return None
            
            return output
            
        except Exception as e:
            logger.error(f"Ошибка при чтении логов с {self.host}: {e}")
            return None


async def get_servers_with_ssh() -> List[Dict]:
    """Получение серверов с SSH доступом"""
    try:
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT 
                    id,
                    name,
                    ip,
                    url,
                    port,
                    username,
                    password
                FROM server_settings
                WHERE is_enable = 1
            """) as cursor:
                servers = await cursor.fetchall()
                return [dict(row) for row in servers]
    except Exception as e:
        logger.error(f"Ошибка при получении серверов: {e}")
        return []


async def get_subscriptions_by_email(email: str) -> List[Dict]:
    """Получение подписок по email клиента"""
    try:
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            # Email в формате tg_123456789@12345
            # Извлекаем telegram_id
            email_parts = email.replace('tg_', '').split('@')
            if not email_parts:
                return []
            
            telegram_id_str = email_parts[0]
            
            # Ищем подписки по vless (содержит email)
            async with conn.execute("""
                SELECT 
                    id,
                    user_id,
                    first_ip,
                    vless,
                    client_email,
                    is_active
                FROM user_subscription
                WHERE is_active = 1 
                AND (client_email = ? OR vless LIKE ?)
            """, (email, f"%{email}%")) as cursor:
                subscriptions = await cursor.fetchall()
                return [dict(row) for row in subscriptions]
    except Exception as e:
        logger.error(f"Ошибка при получении подписок для {email}: {e}")
        return []


async def update_subscription_ip(subscription_id: int, ip: str, is_new: bool = False) -> bool:
    """Обновление IP подписки"""
    try:
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                "UPDATE user_subscription SET first_ip = ? WHERE id = ?",
                (ip, subscription_id)
            )
            await conn.commit()
        
        if is_new:
            logger.info(f"💾 Сохранен первый IP {ip} для подписки ID {subscription_id}")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении IP: {e}")
        return False


async def block_subscription(subscription_id: int, reason: str) -> bool:
    """Блокировка подписки"""
    try:
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                "UPDATE user_subscription SET is_active = 0 WHERE id = ?",
                (subscription_id,)
            )
            await conn.commit()
        
        logger.warning(f"🚫 Подписка {subscription_id} заблокирована: {reason}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при блокировке: {e}")
        return False


async def process_server_logs(server: Dict, ssh_port: int = 22) -> Dict:
    """Обработка логов одного сервера"""
    result = {
        'server_name': server['name'],
        'processed': 0,
        'new_ips': 0,
        'blocked': 0,
        'errors': 0
    }
    
    try:
        # Определяем SSH креды (используем те же что для панели или root)
        ssh_username = 'root'  # Обычно логи доступны только root
        ssh_password = server.get('password', '')
        
        # Определяем хост для SSH (используем IP если есть, иначе URL)
        ssh_host = server.get('ip') or server.get('url', '').replace('http://', '').replace('https://', '').split(':')[0]
        
        logger.info(f"📂 Чтение логов с сервера {server['name']} ({ssh_host})")
        
        # Читаем логи
        log_reader = RemoteLogReader(
            host=ssh_host,
            port=ssh_port,
            username=ssh_username,
            password=ssh_password
        )
        
        log_content = await log_reader.read_logs(lines=5000)
        
        if not log_content:
            logger.warning(f"Не удалось прочитать логи с {server['name']}")
            return result
        
        # Парсим логи
        parser = LogParser()
        email_ips = parser.parse_log_content(log_content)
        
        logger.info(f"📊 Найдено {len(email_ips)} уникальных email в логах")
        
        # Обрабатываем каждый email
        for email, ips in email_ips.items():
            result['processed'] += 1
            
            # Получаем подписки для этого email
            subscriptions = await get_subscriptions_by_email(email)
            
            if not subscriptions:
                continue
            
            for subscription in subscriptions:
                # Берем самый частый IP (или первый из множества)
                current_ip = list(ips)[0] if len(ips) == 1 else max(ips, key=lambda x: list(ips).count(x))
                
                if not subscription['first_ip']:
                    # Сохраняем первый IP
                    await update_subscription_ip(subscription['id'], current_ip, is_new=True)
                    result['new_ips'] += 1
                    
                elif subscription['first_ip'] != current_ip:
                    # IP изменился - блокируем
                    reason = f"IP изменился: {subscription['first_ip']} → {current_ip}"
                    await block_subscription(subscription['id'], reason)
                    result['blocked'] += 1
                    
                    # Также можно отключить клиента в 3x-ui через API
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при обработке логов {server['name']}: {e}")
        result['errors'] += 1
        return result


async def monitor_all_servers_logs() -> Dict:
    """Мониторинг логов всех серверов"""
    try:
        logger.info("=" * 60)
        logger.info("🔍 МОНИТОРИНГ IP ЧЕРЕЗ ЛОГИ СЕРВЕРОВ")
        logger.info(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        servers = await get_servers_with_ssh()
        
        if not servers:
            logger.warning("Нет серверов для мониторинга")
            return {}
        
        logger.info(f"📡 Найдено серверов: {len(servers)}")
        
        total_stats = {
            'processed': 0,
            'new_ips': 0,
            'blocked': 0,
            'errors': 0
        }
        
        # Обрабатываем серверы последовательно
        for server in servers:
            result = await process_server_logs(server)
            
            # Обновляем общую статистику
            total_stats['processed'] += result['processed']
            total_stats['new_ips'] += result['new_ips']
            total_stats['blocked'] += result['blocked']
            total_stats['errors'] += result['errors']
            
            # Небольшая задержка
            await asyncio.sleep(1)
        
        # Итоговая статистика
        logger.info("\n" + "=" * 60)
        logger.info("📊 ИТОГОВАЯ СТАТИСТИКА")
        logger.info("=" * 60)
        logger.info(f"Обработано email: {total_stats['processed']}")
        logger.info(f"💾 Сохранено новых IP: {total_stats['new_ips']}")
        logger.info(f"🚫 Заблокировано: {total_stats['blocked']}")
        logger.info(f"❌ Ошибок: {total_stats['errors']}")
        logger.info("=" * 60)
        
        return total_stats
        
    except Exception as e:
        logger.error(f"Критическая ошибка при мониторинге: {e}")
        return {}


async def start_log_monitoring_loop(bot):
    """Запуск цикла мониторинга логов"""
    logger.info("🚀 Запуск мониторинга IP через логи серверов")
    logger.info("⏱️  Интервал проверки: 15 минут")
    
    while True:
        try:
            await monitor_all_servers_logs()
        except Exception as e:
            logger.error(f"Ошибка в цикле мониторинга логов: {e}")
        
        # Проверяем каждые 15 минут
        await asyncio.sleep(900)


# Тестовая функция
async def test_log_parser():
    """Тест парсера логов"""
    parser = LogParser()
    
    # Тестовые строки из реальных логов Xray
    test_logs = [
        '2024/11/05 10:23:45 [Info] [123456789] email:tg_987654321@12345 from 192.168.1.100:54321',
        '2024/11/05 10:24:12 192.168.1.101:54322 accepted tcp:example.com:443 email:tg_111222333@54321',
        '2024/11/05 10:25:30 [Info] proxyman/inbound: connection from 192.168.1.102 email:tg_444555666@99999',
    ]
    
    print("🧪 Тест парсера логов:")
    print("=" * 60)
    
    for log in test_logs:
        result = parser.parse_log_line(log)
        print(f"Лог: {log[:60]}...")
        print(f"Результат: {result}")
        print()


if __name__ == "__main__":
    # Тест парсера
    asyncio.run(test_log_parser())

