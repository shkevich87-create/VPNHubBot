
# WinkPay интеграция (Merchant API)
## Шаги
1. В `.env` заполните:
   ```
   WINKPAY_BASE_URL=https://panel.winkpay.digital
   WINKPAY_API_TOKEN=keedsohrrkuk1ymhdbmev2b2zabh251p
   WINKPAY_MERCHANT_ID=ec82968d-0fa5-4b9a-86f1-e51d1a3a5fc5
   WINKPAY_CALLBACK_URL=https://<ваш-домен>/winkpay/callback
   WINKPAY_SUCCESS_URL=https://<ваш-домен>/pay/success
   WINKPAY_FAIL_URL=https://<ваш-домен>/pay/fail
   WINKPAY_MAX_WAIT_MS=30000
   ```

2. В меню оплаты у пользователя появится пункт **WinkPay**.

3. По нажатии — бот создаст сделку через Merchant API и выдаст ссылку на оплату. Параллельно бот мягко опросит статус и при *success* зачислит средства.

4. (Опционально) добавьте обработчик POST ` /winkpay/callback ` на вашем веб-сервере и пропишите URL в `.env` — WinkPay будет уведомлять о смене статуса.

## Файлы
- `bot/misc/Payment/WinkPay.py` — новый провайдер
- `bot/handlers/user/payment_user.py` — добавлен импорт + маппинг
- `bot/keyboards/inline/user_inline.py` — добавлена кнопка WinkPay
- `.env.example` — добавлены переменные

## Примечания
- `currency` и `payment_gateway` взаимоисключаемы (мы используем `currency=rub`).
- Сумма к оплате в системе может отличаться из-за комиссии клиента — это нормально для Merchant API.
