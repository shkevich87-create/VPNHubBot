CREATE TABLE bot_settings (
                    bot_token TEXT NOT NULL,
                    admin_id TEXT NOT NULL,
                    chat_id TEXT,
                    chanel_id TEXT,
                    is_enable BOOLEAN NOT NULL DEFAULT 1
                , reg_notify INTEGER DEFAULT 0, pay_notify INTEGER DEFAULT 0);
CREATE TABLE server_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    ip TEXT,
                    url TEXT NOT NULL,
                    port TEXT NOT NULL,
                    secret_path TEXT NOT NULL,
                    username TEXT NOT NULL,
                    password TEXT NOT NULL,
                    secretkey TEXT,
                    inbound_id INTEGER,
                    is_enable BOOLEAN NOT NULL DEFAULT 1
                , inbound_id_promo INTEGER DEFAULT 2, connection_method BOOLEAN NOT NULL DEFAULT 0);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE bot_message (
                    command TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    image_path TEXT,
                    is_enable BOOLEAN NOT NULL DEFAULT 1
                );
CREATE TABLE user (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    trial_period BOOLEAN DEFAULT 0,
                    is_enable BOOLEAN NOT NULL DEFAULT 1,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    referral_code TEXT UNIQUE,
                    referral_count INTEGER DEFAULT 0,
                    referred_by TEXT
                );
CREATE TABLE tariff (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    price DECIMAL(10,2) NOT NULL,
                    left_day INTEGER NOT NULL,
                    server_id INTEGER NOT NULL,
                    is_enable BOOLEAN NOT NULL DEFAULT 1, max_devices INTEGER DEFAULT 1, traffic_limit_gb INTEGER DEFAULT 0,
                    FOREIGN KEY (server_id) REFERENCES server_settings(id)
                );
CREATE TABLE trial_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    left_day INTEGER NOT NULL,
                    server_id INTEGER NOT NULL,
                    is_enable BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (server_id) REFERENCES server_settings(id)
                );
CREATE TABLE user_subscription (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    tariff_id INTEGER NOT NULL,
                    server_id INTEGER NOT NULL,
                    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_date TIMESTAMP NOT NULL,
                    vless TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT 1, payment_id TEXT, connection_type TEXT, first_ip TEXT,
                    FOREIGN KEY (user_id) REFERENCES user(id),
                    FOREIGN KEY (tariff_id) REFERENCES tariff(id),
                    FOREIGN KEY (server_id) REFERENCES server_settings(id)
                );
CREATE TABLE yookassa_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    shop_id TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    description TEXT,
                    is_enable INTEGER DEFAULT 0
                );
CREATE TABLE promocodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    promocod TEXT NOT NULL,
                    activation_limit INTEGER DEFAULT 1,
                    activation_total INTEGER DEFAULT 0,
                    percentage DECIMAL(5,2) NOT NULL,
                    is_enable BOOLEAN NOT NULL DEFAULT 1,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
CREATE TABLE payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    tariff_id INTEGER NOT NULL,
                    price REAL NOT NULL,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user (id),
                    FOREIGN KEY (tariff_id) REFERENCES tariff (id)
                );
CREATE TABLE support_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    bot_version TEXT NOT NULL,
                    support_url TEXT NOT NULL
                );
CREATE TABLE notify_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    interval INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    is_enable BOOLEAN NOT NULL DEFAULT 1
                );
CREATE TABLE tariff_promo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    left_day INTEGER NOT NULL,
                    server_id INTEGER,
                    is_enable BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (server_id) REFERENCES server_settings(id)
                );
CREATE TABLE Reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    message TEXT NOT NULL,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
CREATE TABLE payments_code (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pay_code TEXT UNIQUE NOT NULL,
                    sum DECIMAL(10,2) NOT NULL,
                    is_enable BOOLEAN NOT NULL DEFAULT 1,
                    create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
CREATE TABLE payments_attempts (order_id TEXT PRIMARY KEY, user_id INTEGER, amount INTEGER, created_at INTEGER);
CREATE TABLE crypto_pending_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    tariff_id INTEGER NOT NULL,
                    amount_rub DECIMAL(10,2) NOT NULL,
                    amount_usdt DECIMAL(10,6) NOT NULL,
                    unique_amount_usdt DECIMAL(10,6) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (user_id) REFERENCES user(telegram_id),
                    FOREIGN KEY (tariff_id) REFERENCES tariff(id)
                );
CREATE TABLE crypto_settings_backup(
  api_token TEXT,
  is_enable NUM,
  min_amount NUM,
  supported_assets TEXT,
  webhook_url TEXT,
  webhook_secret TEXT
);
CREATE TABLE crypto_settings (
                    usdt_wallet TEXT,
                    is_enable BOOLEAN DEFAULT 0,
                    min_amount DECIMAL(10,2) DEFAULT 1.00
                );
