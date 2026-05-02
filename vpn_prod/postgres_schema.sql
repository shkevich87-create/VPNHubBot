CREATE TABLE IF NOT EXISTS bot_settings (
    bot_token TEXT NOT NULL,
    admin_id TEXT NOT NULL,
    chat_id TEXT,
    chanel_id TEXT,
    is_enable INTEGER NOT NULL DEFAULT 1,
    reg_notify TEXT,
    pay_notify TEXT
);

CREATE TABLE IF NOT EXISTS server_settings (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    ip TEXT,
    url TEXT NOT NULL,
    port TEXT NOT NULL,
    secret_path TEXT NOT NULL,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    secretkey TEXT,
    inbound_id INTEGER,
    connection_method INTEGER NOT NULL DEFAULT 0,
    is_enable INTEGER NOT NULL DEFAULT 1,
    inbound_id_promo INTEGER DEFAULT 2
);

CREATE TABLE IF NOT EXISTS bot_message (
    command TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    image_path TEXT,
    is_enable INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS "user" (
    id SERIAL PRIMARY KEY,
    username TEXT,
    telegram_id BIGINT UNIQUE NOT NULL,
    trial_period INTEGER DEFAULT 0,
    is_enable INTEGER NOT NULL DEFAULT 1,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    referral_code TEXT UNIQUE,
    referral_count INTEGER DEFAULT 0,
    referred_by TEXT
);

CREATE TABLE IF NOT EXISTS tariff (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) NOT NULL,
    left_day INTEGER NOT NULL,
    server_id INTEGER REFERENCES server_settings(id),
    is_enable INTEGER NOT NULL DEFAULT 1,
    max_devices INTEGER DEFAULT 1,
    traffic_limit_gb INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS trial_settings (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    left_day INTEGER NOT NULL,
    server_id INTEGER REFERENCES server_settings(id),
    is_enable INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS user_subscription (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    tariff_id INTEGER NOT NULL,
    server_id INTEGER NOT NULL REFERENCES server_settings(id),
    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_date TIMESTAMP NOT NULL,
    vless TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    first_ip TEXT,
    payment_id TEXT,
    connection_type TEXT DEFAULT 'tcp',
    client_uuid TEXT,
    client_email TEXT,
    sub_id TEXT,
    subscription_url TEXT
);

CREATE TABLE IF NOT EXISTS yookassa_settings (
    id SERIAL PRIMARY KEY,
    name TEXT,
    shop_id TEXT NOT NULL,
    api_key TEXT NOT NULL,
    description TEXT,
    is_enable INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS promocodes (
    id SERIAL PRIMARY KEY,
    promocod TEXT NOT NULL,
    activation_limit INTEGER DEFAULT 1,
    activation_total INTEGER DEFAULT 0,
    percentage NUMERIC(5, 2) NOT NULL,
    is_enable INTEGER NOT NULL DEFAULT 1,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    tariff_id INTEGER NOT NULL REFERENCES tariff(id),
    price DOUBLE PRECISION NOT NULL,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS support_info (
    id SERIAL PRIMARY KEY,
    message TEXT NOT NULL,
    bot_version TEXT NOT NULL,
    support_url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notify_settings (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    interval INTEGER NOT NULL,
    type TEXT NOT NULL,
    is_enable INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS payments_code (
    id SERIAL PRIMARY KEY,
    pay_code TEXT UNIQUE NOT NULL,
    sum NUMERIC(10, 2) NOT NULL,
    is_enable INTEGER NOT NULL DEFAULT 1,
    create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tariff_promo (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    left_day INTEGER NOT NULL,
    server_id INTEGER REFERENCES server_settings(id),
    is_enable INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    message TEXT NOT NULL,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments_attempts (
    order_id TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    created_at INTEGER NOT NULL,
    tariff_id INTEGER,
    status TEXT DEFAULT 'pending',
    processed_at INTEGER,
    external_id TEXT
);

CREATE TABLE IF NOT EXISTS crypto_pending_payments (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    tariff_id INTEGER NOT NULL REFERENCES tariff(id),
    amount_rub NUMERIC(10, 2) NOT NULL,
    amount_usdt NUMERIC(10, 6) NOT NULL,
    unique_amount_usdt NUMERIC(10, 6) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS crypto_settings (
    usdt_wallet TEXT,
    is_enable INTEGER DEFAULT 0,
    min_amount NUMERIC(10, 2) DEFAULT 1.00
);

CREATE INDEX IF NOT EXISTS idx_user_telegram_id ON "user"(telegram_id);
CREATE INDEX IF NOT EXISTS idx_user_referral_code ON "user"(referral_code);
CREATE INDEX IF NOT EXISTS idx_tariff_server_active ON tariff(server_id, is_enable);
CREATE INDEX IF NOT EXISTS idx_trial_server_active ON trial_settings(server_id, is_enable);
CREATE INDEX IF NOT EXISTS idx_server_active ON server_settings(is_enable);
CREATE INDEX IF NOT EXISTS idx_user_subscription_user_active ON user_subscription(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_user_subscription_end_active ON user_subscription(is_active, end_date);
CREATE INDEX IF NOT EXISTS idx_user_subscription_payment_user ON user_subscription(payment_id, user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscription_server_active ON user_subscription(server_id, is_active);
CREATE INDEX IF NOT EXISTS idx_user_subscription_client_uuid ON user_subscription(client_uuid);
CREATE INDEX IF NOT EXISTS idx_user_subscription_client_email ON user_subscription(client_email);
CREATE INDEX IF NOT EXISTS idx_payments_user_date ON payments(user_id, date);
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(date);
CREATE INDEX IF NOT EXISTS idx_payments_attempts_user ON payments_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_crypto_pending_status_expires ON crypto_pending_payments(status, expires_at);
