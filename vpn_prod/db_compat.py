import os
import re
from datetime import date, datetime
from typing import Any, Iterable, Optional

import aiosqlite as _sqlite

try:
    from dotenv import load_dotenv

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    load_dotenv(os.path.join(BASE_DIR, "web-module", ".env"))
except Exception:
    pass


Row = _sqlite.Row
Connection = Any


def _use_postgres() -> bool:
    backend = os.getenv("DB_BACKEND", "").lower()
    database_url = os.getenv("DATABASE_URL", "")
    return backend in {"postgres", "postgresql"} or database_url.startswith(("postgres://", "postgresql://"))


def connect(database: Optional[str] = None):
    if not _use_postgres():
        return _sqlite.connect(database)

    return PostgresConnectContext()


class PostgresConnectContext:
    def __init__(self):
        self.connection = None

    def __await__(self):
        return self._connect().__await__()

    async def __aenter__(self):
        self.connection = await self._connect()
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        if self.connection is not None:
            await self.connection.close()
        return False

    async def _connect(self):
        import asyncpg

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL is required when DB_BACKEND=postgres")
        raw = await asyncpg.connect(database_url)
        return PostgresConnection(raw)


class PostgresRow:
    def __init__(self, keys: list[str], values: Iterable[Any]):
        self._keys = keys
        self._values = tuple(values)
        self._mapping = dict(zip(keys, self._values))

    def __getitem__(self, item):
        if isinstance(item, str):
            return self._mapping[item]
        return self._values[item]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def keys(self):
        return self._keys


class PostgresCursor:
    def __init__(self, rows=None, lastrowid=None):
        self._rows = rows or []
        self.lastrowid = lastrowid
        self.description = [(key,) for key in self._rows[0].keys()] if self._rows else []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def fetchone(self):
        return self._rows[0] if self._rows else None

    async def fetchall(self):
        return self._rows


class ExecuteContext:
    def __init__(self, connection: "PostgresConnection", sql: str, params=None):
        self.connection = connection
        self.sql = sql
        self.params = params
        self.cursor = None

    def __await__(self):
        return self._run().__await__()

    async def __aenter__(self):
        self.cursor = await self._run()
        return self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def _run(self):
        return await self.connection._execute(self.sql, self.params)


class PostgresConnection:
    row_factory = None

    def __init__(self, raw):
        self.raw = raw

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
        return False

    def execute(self, sql: str, params=None):
        return ExecuteContext(self, sql, params)

    async def commit(self):
        return None

    async def rollback(self):
        return None

    async def close(self):
        try:
            await self.raw.close()
        except RuntimeError:
            pass

    async def _execute(self, sql: str, params=None):
        translated, values = _translate_sql(sql, params)
        if not translated:
            return PostgresCursor([])

        if _is_select_like(translated):
            records = await self.raw.fetch(translated, *values)
            return PostgresCursor([_to_row(record) for record in records])

        if _insert_needs_returning(translated):
            translated = f"{translated.rstrip().rstrip(';')} RETURNING id"
            records = await self.raw.fetch(translated, *values)
            rows = [_to_row(record) for record in records]
            lastrowid = rows[0][0] if rows else None
            return PostgresCursor(rows, lastrowid=lastrowid)

        await self.raw.execute(translated, *values)
        return PostgresCursor([])


def _to_row(record) -> PostgresRow:
    keys = list(record.keys())
    return PostgresRow(keys, [_normalize_value(record[key]) for key in keys])


def _normalize_value(value):
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _is_select_like(sql: str) -> bool:
    head = sql.lstrip().split(None, 1)[0].lower() if sql.strip() else ""
    return head in {"select", "with", "show"}


def _insert_needs_returning(sql: str) -> bool:
    lowered = sql.lower()
    if not lowered.lstrip().startswith("insert into"):
        return False
    if " returning " in lowered:
        return False
    return any(
        f"insert into {table}" in lowered or f'insert into "{table}"' in lowered
        for table in _SERIAL_TABLES
    )


_SERIAL_TABLES = {
    "server_settings",
    "user",
    "tariff",
    "trial_settings",
    "user_subscription",
    "yookassa_settings",
    "payments",
    "promocodes",
    "payments_code",
    "referral_rewards",
    "crypto_pending_payments",
    "notify_settings",
    "support_info",
    "tariff_promo",
    "reviews",
}


def _translate_sql(sql: str, params=None):
    sql = sql.strip()
    if not sql:
        return "", []

    pragma_match = re.match(r"PRAGMA\s+table_info\((\w+)\)", sql, re.I)
    if pragma_match:
        table = pragma_match.group(1)
        query = """
            SELECT ordinal_position - 1 as cid,
                   column_name as name,
                   data_type as type,
                   CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END as notnull,
                   column_default as dflt_value,
                   0 as pk
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            ORDER BY ordinal_position
        """
        return query, [table.lower()]

    if sql.upper().startswith("PRAGMA "):
        return "", []

    translated = sql
    translated = _translate_sqlite_functions(translated)
    translated = _translate_schema(translated)
    translated = _quote_user_table(translated)
    translated = _translate_insert_or_replace(translated)
    translated = _translate_like_casts(translated)
    translated = _replace_placeholders(translated)
    return translated, _normalize_params(params)


def _translate_sqlite_functions(sql: str) -> str:
    sql = re.sub(
        r"date\('now'\s*,\s*'-([0-9]+)\s+days'\)",
        r"(CURRENT_TIMESTAMP - INTERVAL '\1 days')",
        sql,
        flags=re.I,
    )
    sql = re.sub(r"date\('now'\)", "CURRENT_DATE", sql, flags=re.I)
    sql = re.sub(r"datetime\('now'\s*,\s*'localtime'\)", "CURRENT_TIMESTAMP", sql, flags=re.I)
    sql = re.sub(r"datetime\('now'\)", "CURRENT_TIMESTAMP", sql, flags=re.I)
    sql = re.sub(r"datetime\(([\w.?]+)\s*,\s*'localtime'\)", r"(\1)::timestamp", sql, flags=re.I)
    sql = re.sub(r"datetime\(([\w.?]+)\)", r"(\1)::timestamp", sql, flags=re.I)
    sql = re.sub(
        r"julianday\(([\w.]+)\)\s*-\s*julianday\('now'\s*,\s*'localtime'\)",
        r"(EXTRACT(EPOCH FROM ((\1)::timestamp - CURRENT_TIMESTAMP)) / 86400.0)",
        sql,
        flags=re.I,
    )
    sql = re.sub(
        r"julianday\(([\w.]+)\)\s*-\s*julianday\('now'\)",
        r"(EXTRACT(EPOCH FROM ((\1)::timestamp - CURRENT_TIMESTAMP)) / 86400.0)",
        sql,
        flags=re.I,
    )
    return sql


def _translate_schema(sql: str) -> str:
    sql = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", "SERIAL PRIMARY KEY", sql, flags=re.I)
    sql = re.sub(r"\bBOOLEAN\b", "INTEGER", sql, flags=re.I)
    sql = re.sub(r"\bREAL\b", "DOUBLE PRECISION", sql, flags=re.I)
    return sql


def _quote_user_table(sql: str) -> str:
    patterns = [
        (r"\bFROM\s+user\b", 'FROM "user"'),
        (r"\bJOIN\s+user\b", 'JOIN "user"'),
        (r"\bUPDATE\s+user\b", 'UPDATE "user"'),
        (r"\bINTO\s+user\b", 'INTO "user"'),
        (r"\bON\s+user\s*\(", 'ON "user"('),
        (r"\bTABLE\s+IF\s+NOT\s+EXISTS\s+user\b", 'TABLE IF NOT EXISTS "user"'),
        (r"\bTABLE\s+user\b", 'TABLE "user"'),
        (r"\bDELETE\s+FROM\s+user\b", 'DELETE FROM "user"'),
        (r"\bREFERENCES\s+user\b", 'REFERENCES "user"'),
    ]
    for pattern, replacement in patterns:
        sql = re.sub(pattern, replacement, sql, flags=re.I)
    return sql


def _translate_insert_or_replace(sql: str) -> str:
    match = re.match(
        r"INSERT\s+OR\s+REPLACE\s+INTO\s+([^\s(]+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)",
        sql,
        flags=re.I | re.S,
    )
    if not match:
        return sql

    table, columns_sql, values_sql = match.groups()
    columns = [column.strip().strip('"') for column in columns_sql.split(",")]
    table_name = table.strip('"').lower()
    conflict_column = {
        "payments_attempts": "order_id",
        "yookassa_settings": "id",
    }.get(table_name, columns[0])

    update_columns = [column for column in columns if column != conflict_column]
    if not update_columns:
        conflict_sql = f'"{conflict_column}"' if conflict_column == "order_id" else conflict_column
        return f"INSERT INTO {table} ({columns_sql}) VALUES ({values_sql}) ON CONFLICT ({conflict_sql}) DO NOTHING"

    assignments = ", ".join(f"{column} = EXCLUDED.{column}" for column in update_columns)
    conflict_sql = f'"{conflict_column}"' if conflict_column == "order_id" else conflict_column
    return (
        f"INSERT INTO {table} ({columns_sql}) VALUES ({values_sql}) "
        f"ON CONFLICT ({conflict_sql}) DO UPDATE SET {assignments}"
    )


def _translate_like_casts(sql: str) -> str:
    return re.sub(
        r"\b((?:\w+\.)?(?:telegram_id|user_id|id))\s+LIKE\b",
        r"CAST(\1 AS TEXT) LIKE",
        sql,
        flags=re.I,
    )


def _replace_placeholders(sql: str) -> str:
    result = []
    index = 1
    in_single = False
    in_double = False
    for char in sql:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        if char == "?" and not in_single and not in_double:
            result.append(f"${index}")
            index += 1
        else:
            result.append(char)
    return "".join(result)


def _normalize_params(params=None) -> list[Any]:
    if params is None:
        return []
    if isinstance(params, list):
        return [_normalize_param(value) for value in params]
    if isinstance(params, tuple):
        return [_normalize_param(value) for value in params]
    return [_normalize_param(params)]


def _normalize_param(value):
    if not isinstance(value, str):
        return value
    if not re.match(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)?$", value):
        return value
    text = value.replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return value
