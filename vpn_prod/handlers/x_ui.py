from py3xui import Api
from py3xui.client import Client
from loguru import logger
from typing import Optional, Dict, Any
import aiohttp
from datetime import datetime, timedelta
import uuid
import random
import os
import secrets
from urllib.parse import quote, urlencode, urlsplit

BOT_SUBSCRIPTION_DAYS = 30
BOT_MAX_DEVICES = 1

class XUIManager:
    def __init__(self):
        self.clients = {}

    async def get_client(self, server_settings: Dict) -> Optional[Api]:
        """Получение или создание клиента для сервера"""
        server_id = server_settings['id']
        
        if server_id in self.clients:
            return self.clients[server_id]
        
        try:
            logger.info(f"Создание клиента для сервера {server_id}")
            logger.info(f"URL: {server_settings['url']}")
            logger.info(f"Port: {server_settings['port']}")
            logger.info(f"Path: {server_settings['secret_path']}")
            
            # Определяем протокол на основе connection_method (как в VPNHubBot)
            # connection_method: True (1) = HTTPS, False (0) = HTTP
            connection_method = server_settings.get('connection_method', False)
            connection_method = str(connection_method).lower() in {'1', 'true', 'yes', 'on'}
            protocol = 'https' if connection_method else 'http'
            
            url = str(server_settings['url']).strip().strip('/')
            # Удаляем протокол если он уже есть
            if url.startswith('http://') or url.startswith('https://'):
                url = url.split('://', 1)[1].strip().strip('/')
            
            # Удаляем порт из URL если он там есть (чтобы не было дубликата)
            if ':' in url:
                url = url.split(':')[0]
            url = url.strip().strip('/')
            
            # Формируем полный URL с нужным протоколом
            url = f"{protocol}://{url}:{server_settings['port']}/{server_settings['secret_path']}"
            
            logger.info(f"API URL: {url}")
            logger.info(f"Протокол подключения: {protocol.upper()}")
            
            client = Api(
                url,
                server_settings['username'],
                server_settings['password'],
                use_tls_verify=False
            )
            
            client.login()
            inbounds = client.inbound.get_list()
            logger.info(f"Подключение успешно. Найдено {len(inbounds)} inbounds")
            
            self.clients[server_id] = client
            return client
            
        except Exception as e:
            logger.error(f"Ошибка при создании клиента X-UI для сервера {server_id}: {e}")
            return None

    def _find_inbound(self, inbounds: list, inbound_id: int) -> Optional[Any]:
        """Поиск inbound по ID"""
        return next((i for i in inbounds if i.id == inbound_id), None)

    def _normalize_host(self, raw_url: str) -> str:
        if not raw_url:
            return ""
        if "://" not in raw_url:
            raw_url = f"//{raw_url}"
        parsed = urlsplit(raw_url)
        return parsed.hostname or raw_url.split(":", 1)[0].strip("/")

    def _build_subscription_url(self, server_settings: Dict, sub_id: str) -> str:
        connection_method = server_settings.get('connection_method', False)
        default_scheme = 'https' if connection_method else 'http'
        scheme = os.getenv("XUI_SUBSCRIPTION_SCHEME", default_scheme).strip(":/")
        host = os.getenv("XUI_SUBSCRIPTION_HOST") or self._normalize_host(server_settings.get('url', ''))
        port = os.getenv("XUI_SUBSCRIPTION_PORT") or str(server_settings.get('port', '')).strip()
        path = os.getenv("XUI_SUBSCRIPTION_PATH", "/sub/").strip()

        if not path.startswith("/"):
            path = f"/{path}"
        if not path.endswith("/"):
            path = f"{path}/"

        host_part = host
        if port:
            host_part = f"{host}:{port}"
        return f"{scheme}://{host_part}{path}{quote(sub_id, safe='')}"

    async def create_trial_user(self, server_settings: Dict, trial_settings: Dict, telegram_id: int, connection_type: str = 'tcp', max_devices: int = 1, traffic_limit_gb: int = 0) -> Optional[Dict[str, str]]:
        """Создание пользователя"""
        try:
            logger.info(f"Начало создания пользователя для telegram_id: {telegram_id}")
            
            client = await self.get_client(server_settings)
            if not client:
                logger.error(f"Не удалось получить клиента для сервера {server_settings['id']}")
                return None

            subscription_days = BOT_SUBSCRIPTION_DAYS
            max_devices = BOT_MAX_DEVICES
            end_time = datetime.now() + timedelta(days=subscription_days)
            
            inbound_id = server_settings.get('inbound_id', 1)
            
            unique_id = ''.join([str(random.randint(0, 9)) for _ in range(5)])
            email = f"tg_{telegram_id}@{unique_id}"
            
            # Конвертируем ГБ в байты (для 3x-ui)
            # 0 означает безлимит
            total_gb_bytes = (traffic_limit_gb * 1024 * 1024 * 1024) if traffic_limit_gb > 0 else 0
            
            logger.info(f"Создание пользователя в inbound {inbound_id}")
            logger.info(f"Email: {email}")
            logger.info(f"Дата окончания: {end_time}")
            logger.info(f"Лимит устройств (IP Limit): {max_devices}")
            logger.info(f"Лимит трафика: {traffic_limit_gb} ГБ ({total_gb_bytes} байт, 0 = безлимит)")

            inbounds = client.inbound.get_list()
            logger.info(f"Подключение успешно. Найдено {len(inbounds)} inbounds")
            
            inbound = self._find_inbound(inbounds, inbound_id)
            if not inbound:
                logger.error(f"Inbound {inbound_id} не найден на сервере {server_settings['id']}")
                return None
            
            logger.debug(f"Текущий inbound: {inbound}")

            client_id = str(uuid.uuid4())
            sub_id = secrets.token_urlsafe(16)
            
            # Определяем тип inbound и устанавливаем правильные параметры
            has_reality = hasattr(inbound.stream_settings, 'reality_settings') and inbound.stream_settings.reality_settings
            
            # Параметры зависят от типа inbound
            if has_reality:
                # Для Reality TCP нужен flow
                client_flow = "xtls-rprx-vision"
            else:
                # Для других типов flow не нужен
                client_flow = ""
            
            new_client = Client(
                id=client_id,
                email=email,
                enable=True,
                flow=client_flow,  # Для Reality: xtls-rprx-vision, для других: ""
                tg_id=str(telegram_id),
                total_gb=total_gb_bytes,  # Лимит трафика в байтах (0 = безлимит)
                expiry_time=int(end_time.timestamp() * 1000),
                limit_ip=max_devices,  # Количество устройств из тарифа
                reset=0,
                password="",
                method="",
                sub_id=sub_id,
                up=0,
                down=0,
                total=0,
                inbound_id=inbound_id
            )
            
            logger.info(f"Создание клиента с параметрами: email={email}, limit_ip={max_devices}, flow={client_flow}")

            success = False
            try:
                logger.debug("Попытка создания клиента первым способом...")
                client.client.add(inbound_id, new_client)
                logger.info("Клиент успешно создан первым способом")
                success = True
            except Exception as e:
                logger.debug(f"Ошибка при добавлении клиента первым способом: {e}")
                try:
                    logger.debug("Попытка создания клиента вторым способом...")
                    client.client.add(inbound_id, [new_client])
                    logger.info("Клиент успешно создан вторым способом")
                    success = True
                except Exception as e:
                    logger.error(f"Ошибка при добавлении клиента вторым способом: {e}")

            if not success:
                logger.error(f"Не удалось создать клиента для пользователя {telegram_id}")
                return None

            logger.debug("Начало формирования ссылки для подключения")
            host = server_settings['url']
            # Удаляем протокол если он есть
            if host.startswith('http://') or host.startswith('https://'):
                host = host.split('://', 1)[1]
            
            # Удаляем порт из host если он там есть (для VLESS ссылки нужен только IP/домен)
            if ':' in host:
                host = host.split(':')[0]

            # ВАЖНО: Reality работает ТОЛЬКО с TCP!
            # Проверяем, настроен ли Reality на этом inbound
            has_reality = hasattr(inbound.stream_settings, 'reality_settings') and inbound.stream_settings.reality_settings
            
            if has_reality:
                # Reality inbound - ВСЕГДА используем TCP (игнорируем выбор пользователя)
                logger.info(f"Reality inbound обнаружен - принудительное использование TCP вместо {connection_type}")
                reality_settings = inbound.stream_settings.reality_settings
                
                params = {
                    'type': 'tcp',  # Reality работает только с TCP!
                    'security': 'reality',
                    'pbk': reality_settings['settings']['publicKey'],
                    'fp': 'chrome',
                    'sni': reality_settings['serverNames'][0],
                    'sid': reality_settings['shortIds'][0],
                    'spx': '/',
                    'flow': 'xtls-rprx-vision'  # Обязательно для Reality
                }
            else:
                # Обычный inbound без Reality - используем выбранный тип
                logger.info(f"Обычный inbound - используется тип подключения: {connection_type}")
                
                params = {
                    'type': connection_type,
                    'security': 'none'  # Без Reality используем none или tls
                }
                
                # Специфичные параметры для каждого типа
                if connection_type == 'ws':
                    params['path'] = '/'
                    params['host'] = host
                elif connection_type == 'http':
                    params['path'] = '/'
                elif connection_type == 'tcp':
                    # Для обычного TCP можно добавить headerType
                    params['headerType'] = 'none'
            
            params_str = urlencode(params)
            
            link = f"vless://{client_id}@{host}:{inbound.port}?{params_str}#{email}"
            subscription_url = self._build_subscription_url(server_settings, sub_id)
            
            logger.info(f"Ссылка для клиента успешно сгенерирована: {link}")
            logger.info(f"Subscription URL для клиента успешно сгенерирован: {subscription_url}")
            return {
                "vless": link,
                "subscription_url": subscription_url,
                "client_uuid": client_id,
                "client_email": email,
                "sub_id": sub_id,
            }

        except Exception as e:
            logger.error(f"Критическая ошибка при создании пользователя {telegram_id}: {e}")
            logger.exception("Полный стек ошибки:")
            return None

    async def extend_client_expiry(self, server_settings: Dict, client_uuid: str, client_email: str, new_end_date) -> bool:
        """Продление существующего клиента в 3x-ui."""
        try:
            client_api = await self.get_client(server_settings)
            if not client_api:
                return False

            target_client = None
            if client_email:
                target_client = client_api.client.get_by_email(client_email)

            if not target_client:
                inbound_id = server_settings.get('inbound_id', 1)
                inbounds = client_api.inbound.get_list()
                inbound = self._find_inbound(inbounds, inbound_id)
                if inbound:
                    for existing_client in inbound.settings.clients:
                        existing_uuid = getattr(existing_client, 'id', None) or getattr(existing_client, 'uuid', None)
                        if existing_uuid == client_uuid or getattr(existing_client, 'email', None) == client_email:
                            target_client = existing_client
                            break

            if not target_client:
                logger.error(f"Не найден клиент 3x-ui для продления: uuid={client_uuid}, email={client_email}")
                return False

            update_uuid = client_uuid or getattr(target_client, 'id', None) or getattr(target_client, 'uuid', None)
            if not update_uuid:
                logger.error(f"Не найден UUID клиента 3x-ui для продления: email={client_email}")
                return False

            target_client.expiry_time = int(new_end_date.timestamp() * 1000)
            client_api.client.update(update_uuid, target_client)
            logger.info(f"Клиент 3x-ui продлен до {new_end_date}: uuid={update_uuid}, email={client_email}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при продлении клиента 3x-ui: {e}")
            return False

    async def delete_user(self, server_settings: Dict, telegram_id: int) -> bool:
        """Удаление пользователя"""
        try:
            client = await self.get_client(server_settings)
            if not client:
                return False

            inbound_id = server_settings.get('inbound_id', 1)
            email = f"tg_{telegram_id}_trial"
            
            success = client.client.remove(inbound_id, email)
            return success

        except Exception as e:
            logger.error(f"Ошибка при удалении пользователя {telegram_id}: {e}")
            return False

xui_manager = XUIManager()
