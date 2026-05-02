import json
import secrets
import uuid

import pyxui_async.errors

from bot.misc.VPN.Xui.XuiBase import XuiBase
from bot.misc.util import CONFIG


def generate_subscription_id():
    return secrets.token_hex(12)


class Vless(XuiBase):
    NAME_VPN = 'Vless 🐊'

    def __init__(self, server):
        super().__init__(server)

    async def get_client(self, name):
        try:
            return await self.xui.get_client(
                inbound_id=self.inbound_id,
                email=name,
            )
        except pyxui_async.errors.NotFound:
            return 'User not found'

    async def add_client(self, name):
        try:
            response = await self.xui.add_client(
                inbound_id=self.inbound_id,
                email=str(name),
                uuid=str(uuid.uuid4()),
                limit_ip=CONFIG.limit_ip,
                total_gb=CONFIG.limit_GB * 1073741824,
                flow='xtls-rprx-vision',
                subscription_id=generate_subscription_id()
            )
            if response['success']:
                return True
            return False
        except pyxui_async.errors.NotFound:
            return False

    async def ensure_subscription_id(self, client):
        if client.get('subId'):
            return client
        subscription_id = generate_subscription_id()
        await self.xui.update_client(
            inbound_id=self.inbound_id,
            email=client['email'],
            uuid=client['id'],
            enable=client.get('enable', True),
            flow=client.get('flow', 'xtls-rprx-vision'),
            limit_ip=client.get('limitIp', CONFIG.limit_ip),
            total_gb=client.get('totalGB', CONFIG.limit_GB * 1073741824),
            expire_time=client.get('expiryTime', 0),
            telegram_id=client.get('tgId', ''),
            subscription_id=subscription_id
        )
        client['subId'] = subscription_id
        return client

    async def delete_client(self, telegram_id):
        try:
            response = await self.xui.delete_client(
                inbound_id=self.inbound_id,
                email=telegram_id,
            )
            return response['success']
        except pyxui_async.errors.NotFound:
            return False

    async def get_key_user(self, name, name_key):
        info = await self.get_inbound_server()
        client = await self.get_client(name)
        if client == 'User not found':
            await self.add_client(name)
            client = await self.get_client(name)
        if CONFIG.xui_use_subscription_link:
            client = await self.ensure_subscription_id(client)
            return self.get_subscription_link(client)
        stream_settings = json.loads(info['streamSettings'])
        fp = stream_settings["realitySettings"]["settings"]["fingerprint"]
        pbk = stream_settings["realitySettings"]["settings"]["publicKey"]
        key = (f'vless://{client["id"]}@'
               f'{self.adress}:{info["port"]}?'
               f'type={stream_settings["network"]}&'
               f'security={stream_settings["security"]}&'
               f'pbk={pbk}&'
               f'fp={fp}&'
               f'sni={stream_settings["realitySettings"]["serverNames"][0]}&'
               f'sid={stream_settings["realitySettings"]["shortIds"][0]}&'
               f'spx=%2F&'
               f'flow=xtls-rprx-vision'
               f'#{name_key}')
        return key
