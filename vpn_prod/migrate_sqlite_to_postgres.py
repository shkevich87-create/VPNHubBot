import argparse
import asyncio
import os
import sqlite3
from pathlib import Path
from typing import Any

import asyncpg


TABLES = [
    "bot_settings",
    "server_settings",
    "bot_message",
    "user",
    "tariff",
    "trial_settings",
    "user_subscription",
    "yookassa_settings",
    "promocodes",
    "payments",
    "support_info",
    "notify_settings",
    "payments_code",
    "tariff_promo",
    "Reviews",
    "payments_attempts",
    "crypto_settings",
    "crypto_pending_payments",
]

SERIAL_TABLES = [
    "server_settings",
    "user",
    "tariff",
    "trial_settings",
    "user_subscription",
    "yookassa_settings",
    "promocodes",
    "payments",
    "support_info",
    "notify_settings",
    "payments_code",
    "tariff_promo",
    "Reviews",
    "crypto_pending_payments",
]


def quote_ident(name: str) -> str:
    if name == "user":
        return f'"{name}"'
    if name == "Reviews":
        return "reviews"
    return name


def target_table_name(name: str) -> str:
    if name == "Reviews":
        return "reviews"
    return name.lower()


def normalize_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    return value


async def pg_columns(conn, table: str) -> list[str]:
    return await conn.fetchval(
        """
        SELECT array_agg(column_name::text ORDER BY ordinal_position)
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        """,
        target_table_name(table),
    ) or []


def sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]


async def load_schema(pg, schema_path: Path):
    sql = schema_path.read_text(encoding="utf-8")
    await pg.execute(sql)


async def truncate_tables(pg):
    tables = ", ".join(quote_ident(table) for table in reversed(TABLES))
    await pg.execute(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")


async def copy_table(sqlite_conn: sqlite3.Connection, pg, table: str) -> int:
    source_columns = sqlite_columns(sqlite_conn, table)
    if not source_columns:
        return 0

    target_columns = await pg_columns(pg, table)
    columns = [column for column in source_columns if column in target_columns]
    if not columns:
        return 0

    rows = sqlite_conn.execute(
        f'SELECT {", ".join(columns)} FROM "{table}"'
    ).fetchall()
    if not rows:
        return 0

    placeholders = ", ".join(f"${index}" for index in range(1, len(columns) + 1))
    column_sql = ", ".join(f'"{column}"' for column in columns)
    sql = f"INSERT INTO {quote_ident(table)} ({column_sql}) VALUES ({placeholders})"

    values = [tuple(normalize_value(row[column]) for column in columns) for row in rows]
    await pg.executemany(sql, values)
    return len(values)


async def reset_sequences(pg):
    for table in SERIAL_TABLES:
        quoted = quote_ident(table)
        await pg.execute(
            f"""
            SELECT setval(
                pg_get_serial_sequence('{quoted}', 'id'),
                COALESCE((SELECT MAX(id) FROM {quoted}), 1),
                COALESCE((SELECT MAX(id) FROM {quoted}), 0) > 0
            )
            """
        )


async def main():
    parser = argparse.ArgumentParser(description="Migrate /opt/vpn SQLite database to PostgreSQL")
    parser.add_argument("--sqlite", default=os.getenv("SQLITE_PATH", "instance/database.db"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--schema", default="postgres_schema.sql")
    parser.add_argument("--truncate", action="store_true")
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL is required")

    sqlite_path = Path(args.sqlite)
    schema_path = Path(args.schema)
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite database not found: {sqlite_path}")
    if not schema_path.exists():
        raise SystemExit(f"PostgreSQL schema not found: {schema_path}")

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    pg = await asyncpg.connect(args.database_url)

    try:
        await load_schema(pg, schema_path)
        if args.truncate:
            await truncate_tables(pg)

        for table in TABLES:
            count = await copy_table(sqlite_conn, pg, table)
            print(f"{table}: {count}")

        await reset_sequences(pg)
        print("Migration complete")
    finally:
        await pg.close()
        sqlite_conn.close()


if __name__ == "__main__":
    asyncio.run(main())
