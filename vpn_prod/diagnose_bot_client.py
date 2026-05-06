#!/usr/bin/env python3
"""
Read-only diagnostics for comparing bot-created 3x-ui clients with manual clients.

Run from /opt/vpn on the production server.
Examples:
    /opt/vpn/venv/bin/python diagnose_bot_client.py --email tg_8731687640@47570
    /opt/vpn/venv/bin/python diagnose_bot_client.py --email tg_8731687640@47570 --manual-email Vlad
"""

import argparse
import asyncio
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import db_compat as aiosqlite

from handlers.database import db
from handlers.x_ui import xui_manager


FIELDS = (
    "email",
    "id",
    "uuid",
    "enable",
    "flow",
    "limit_ip",
    "expiry_time",
    "total_gb",
    "total",
    "sub_id",
    "tg_id",
    "up",
    "down",
)


def get_field(client, field):
    return getattr(client, field, None)


def fmt_expiry(value):
    if not value:
        return "0 (no expiry)"
    try:
        return datetime.fromtimestamp(int(value) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def print_client(title, client):
    print(f"\n{title}")
    print("-" * len(title))
    if not client:
        print("not found")
        return

    for field in FIELDS:
        value = get_field(client, field)
        if field == "expiry_time":
            print(f"{field:12}: {value} ({fmt_expiry(value)})")
        else:
            print(f"{field:12}: {value}")


def parse_vless(link):
    if not link:
        return {}
    parsed = urlparse(link)
    return {
        "scheme": parsed.scheme,
        "uuid": parsed.username,
        "host": parsed.hostname,
        "port": parsed.port,
        "params": {key: values[0] for key, values in parse_qs(parsed.query).items()},
        "tag": parsed.fragment,
    }


def print_vless(title, link):
    print(f"\n{title}")
    print("-" * len(title))
    if not link:
        print("empty")
        return

    parsed = parse_vless(link)
    for key in ("scheme", "uuid", "host", "port", "tag"):
        print(f"{key:12}: {parsed.get(key)}")
    print("params:")
    for key, value in sorted(parsed.get("params", {}).items()):
        print(f"  {key:10}: {value}")


async def get_server_settings(subscription_email=None):
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row

        if subscription_email:
            async with conn.execute(
                """
                SELECT s.*
                FROM user_subscription us
                JOIN server_settings s ON us.server_id = s.id
                WHERE us.client_email = ? OR us.vless LIKE ?
                ORDER BY us.id DESC
                LIMIT 1
                """,
                (subscription_email, f"%{subscription_email}%"),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)

        async with conn.execute(
            "SELECT * FROM server_settings WHERE is_enable = 1 ORDER BY id LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_subscription(email):
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            """
            SELECT *
            FROM user_subscription
            WHERE client_email = ? OR vless LIKE ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (email, f"%{email}%"),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


def find_client(inbounds, email):
    for inbound in inbounds:
        for client in inbound.settings.clients:
            if getattr(client, "email", None) == email:
                return inbound, client
    return None, None


def compare_clients(bot_client, manual_client):
    if not bot_client or not manual_client:
        return

    print("\nDifferences")
    print("-----------")
    found = False
    for field in FIELDS:
        bot_value = get_field(bot_client, field)
        manual_value = get_field(manual_client, field)
        if bot_value != manual_value:
            found = True
            print(f"{field:12}: bot={bot_value!r} manual={manual_value!r}")
    if not found:
        print("No differences in inspected fields.")


async def main():
    parser = argparse.ArgumentParser(description="Compare bot and manual 3x-ui clients.")
    parser.add_argument("--email", required=True, help="Bot-created client email, for example tg_123@45678")
    parser.add_argument("--manual-email", help="Manual client email to compare against")
    args = parser.parse_args()

    await db.init_db()

    subscription = await get_subscription(args.email)
    server = await get_server_settings(args.email)
    if not server:
        raise SystemExit("No enabled server_settings row found.")

    api = await xui_manager.get_client(server)
    if not api:
        raise SystemExit("Could not connect to 3x-ui API.")

    inbounds = api.inbound.get_list()
    bot_inbound, bot_client = find_client(inbounds, args.email)
    print(f"Server: {server.get('name')} ({server.get('url')}), inbound_id={server.get('inbound_id')}")
    print(f"Bot inbound found: {getattr(bot_inbound, 'id', None)}")
    print_client("Bot client", bot_client)

    if subscription:
        print("\nBot subscription")
        print("----------------")
        print(f"db_id       : {subscription.get('id')}")
        print(f"is_active   : {subscription.get('is_active')}")
        print(f"end_date    : {subscription.get('end_date')}")
        print(f"first_ip    : {subscription.get('first_ip')}")
        print(f"sub_id      : {subscription.get('sub_id')}")
        print(f"sub_url     : {subscription.get('subscription_url')}")
        print_vless("Stored VLESS", subscription.get("vless"))
    else:
        print("\nBot subscription: not found in DB")

    if args.manual_email:
        manual_inbound, manual_client = find_client(inbounds, args.manual_email)
        print(f"\nManual inbound found: {getattr(manual_inbound, 'id', None)}")
        print_client("Manual client", manual_client)
        compare_clients(bot_client, manual_client)


if __name__ == "__main__":
    asyncio.run(main())
