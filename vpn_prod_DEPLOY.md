# VPN prod deploy notes

Рабочий проект на сервере: `/opt/vpn`.

## Перед выкладкой

```bash
cd /opt/vpn
cp instance/database.db "instance/database.$(date +%F_%H-%M-%S).backup.db"
tar -czf "/opt/vpn_code.$(date +%F_%H-%M-%S).tgz" /opt/vpn
```

## Файлы из этого патча

Скопировать в `/opt/vpn`:

- `handlers/database.py`
- `handlers/x_ui.py`
- `handlers/buy_subscribe.py`
- `handlers/expire_subscriptions.py`
- `handlers/log_parser.py`
- `handlers/ip_monitor.py`
- `handlers/tariff.py`
- `handlers/trial.py`
- `handlers/admin/admin_promo_send.py`
- `handlers/admin/admin_user_del.py`
- `handlers/user/user_pay_code.py`
- `handlers/user/user_cryptopay.py`
- `handlers/user/user_menu_handlers.py`
- `handlers/user/user_lk_sub.py`
- `handlers/user/user_lk_sub_qr.py`
- `handlers/user/user_help.py`
- `handlers/user/merge_sub.py`
- `handlers/user/user_support.py`
- `web-module/app.py`

## Subscription URL

По умолчанию новые клиенты получают `sub_id` в 3x-ui, а пользователю отдается:

```text
http(s)://SERVER_HOST:PANEL_PORT/sub/SUB_ID
```

Если подписки на 3x-ui находятся на другом домене/порту/пути, задать в `.env`:

```env
XUI_SUBSCRIPTION_SCHEME=https
XUI_SUBSCRIPTION_HOST=vpn.example.com
XUI_SUBSCRIPTION_PORT=443
XUI_SUBSCRIPTION_PATH=/sub/
```

Если WinkPay не хранится в `yookassa_settings`, задать:

```env
WINKPAY_MERCHANT_ID=...
WINKPAY_ACCESS_TOKEN=...
```

## После выкладки

Запустить инициализацию базы через обычный старт бота. Миграции безопасные: добавляют только отсутствующие колонки и индексы.

Проверки:

```bash
python -m py_compile handlers/database.py handlers/x_ui.py handlers/buy_subscribe.py handlers/expire_subscriptions.py web-module/app.py
curl -fsS http://127.0.0.1:5000/healthz
curl -fsS http://127.0.0.1:5000/readyz
```

## Новый VPN server в админке

- `Название сервера`: любое понятное имя.
- `IP адрес`: публичный IP VPN-сервера.
- `URL`: host/IP панели 3x-ui без secret path.
- `Порт`: порт панели 3x-ui.
- `Secret Path`: секретный путь панели 3x-ui без домена.
- `Имя пользователя` / `Пароль`: логин панели 3x-ui.
- `Inbound ID`: inbound для платных подписок.
- `Inbound ID Promo`: inbound для промо, если используется.
- `Активен`: включить.

В 3x-ui у inbound должны быть включены подписки, иначе `/sub/{sub_id}` не будет отдавать конфиги.
