# SQLite to PostgreSQL migration

Рабочее приложение на сервере: `/opt/vpn`.

## Что делает патч

- `vpn_prod/db_compat.py` оставляет текущий `aiosqlite` API, но при `DB_BACKEND=postgres` или `DATABASE_URL=postgresql://...` выполняет запросы через PostgreSQL.
- `vpn_prod/postgres_schema.sql` создаёт PostgreSQL-схему под текущие таблицы приложения.
- `vpn_prod/migrate_sqlite_to_postgres.py` переносит данные из `/opt/vpn/instance/database.db` в PostgreSQL.

## Миграция на проде

```bash
cd /opt/vpn

sudo systemctl stop vpn-bot vpn-web

cp instance/database.db "instance/database.before-postgres.$(date +%F_%H-%M-%S).db"
tar -czf "/opt/vpn.before-postgres.$(date +%F_%H-%M-%S).tgz" /opt/vpn

/opt/vpn/venv/bin/pip install -r /opt/vpn/requirements.txt
/opt/vpn/venv/bin/pip install -r /opt/vpn/web-module/requirements.txt
```

Если PostgreSQL запущен из `/opt/VPNHubBot/docker-compose.yml`, обычно URL можно собрать из `.env`:

```bash
cd /opt/VPNHubBot
set -a
. ./.env
set +a

export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}"
```

Проверка подключения:

```bash
docker exec -it postgres_db_container psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select version();"
```

Перенос данных:

```bash
cd /opt/vpn

DATABASE_URL="$DATABASE_URL" /opt/vpn/venv/bin/python migrate_sqlite_to_postgres.py \
  --sqlite /opt/vpn/instance/database.db \
  --schema /opt/vpn/postgres_schema.sql \
  --truncate
```

Включение PostgreSQL для приложения:

```bash
grep -q '^DB_BACKEND=' /opt/vpn/web-module/.env && \
  sed -i 's|^DB_BACKEND=.*|DB_BACKEND=postgres|' /opt/vpn/web-module/.env || \
  echo 'DB_BACKEND=postgres' >> /opt/vpn/web-module/.env

grep -q '^DATABASE_URL=' /opt/vpn/web-module/.env && \
  sed -i "s|^DATABASE_URL=.*|DATABASE_URL=${DATABASE_URL}|" /opt/vpn/web-module/.env || \
  echo "DATABASE_URL=${DATABASE_URL}" >> /opt/vpn/web-module/.env

sudo systemctl restart vpn-bot vpn-web
sleep 5

sudo systemctl status vpn-bot vpn-web --no-pager
curl -fsS http://127.0.0.1:5000/healthz
curl -fsS http://127.0.0.1:5000/readyz
```

## Быстрая сверка данных

```bash
docker exec -it postgres_db_container psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
select 'user' as table_name, count(*) from \"user\"
union all select 'server_settings', count(*) from server_settings
union all select 'tariff', count(*) from tariff
union all select 'user_subscription', count(*) from user_subscription
union all select 'payments', count(*) from payments;
"
```

## Откат

```bash
sudo systemctl stop vpn-bot vpn-web

sed -i '/^DB_BACKEND=/d' /opt/vpn/web-module/.env
sed -i '/^DATABASE_URL=/d' /opt/vpn/web-module/.env

sudo systemctl restart vpn-bot vpn-web
```

