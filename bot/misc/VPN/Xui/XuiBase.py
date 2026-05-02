from abc import ABC
from urllib.parse import urlsplit

from pyxui_async import XUI

from bot.misc.VPN.BaseVpn import BaseVpn
from bot.misc.util import CONFIG


class XuiBase(BaseVpn, ABC):

    NAME_VPN: str

    def __init__(self, server):
        adress = server.ip.split(':', 1)
        adress_port = f'{adress[0]}:{adress[1]}'
        if server.connection_method:
            full_address = f'https://{adress_port}'
        else:
            full_address = f'http://{adress_port}'
        self.adress = f'{adress[0]}'
        self.full_address = full_address.rstrip('/')
        self.subscription_domain = self._get_subscription_domain()
        self.xui = XUI(
            full_address=full_address,
            panel=server.panel,
            https=server.connection_method
        )
        self.inbound_id = int(server.inbound_id)
        self.login_user = server.login
        self.password = server.password

    async def login(self):
        await self.xui.login(username=self.login_user, password=self.password)

    async def get_inbound_server(self):
        try:
            info = await self.xui.get_inbounds()
            obj = info['obj']
            for inbound in obj:
                if inbound['id'] == self.inbound_id:
                    return inbound
        except IndexError:
            return "Error inbound"

    async def get_all_user_server(self):
        try:
            inbound_server = await self.get_inbound_server()
            return inbound_server.get('clientStats')
        except IndexError:
            return "Error inbound"

    def _get_subscription_domain(self):
        parsed = urlsplit(self.full_address)
        return parsed.hostname or self.adress

    def get_subscription_link(self, client):
        sub_id = client.get('subId')
        if not sub_id:
            raise ValueError('Client subId not found')
        host = CONFIG.xui_subscription_host or self.subscription_domain
        scheme = CONFIG.xui_subscription_scheme
        if not scheme:
            scheme = 'https' if self.xui.https else 'http'
        return (
            f'{scheme}://{host}:'
            f'{CONFIG.xui_subscription_port}'
            f'{CONFIG.xui_subscription_path}'
            f'{sub_id}'
        )
