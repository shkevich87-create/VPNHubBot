from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from datetime import datetime
import db_compat as aiosqlite

from handlers.database import db
from handlers.tron_pay import tron_pay_manager
from handlers.buy_subscribe import subscription_manager
from handlers.user.user_kb import get_lk_keyboard

router = Router()

@router.callback_query(F.data.startswith("apply_crypto_payments:"))
async def process_crypto_payment(callback: CallbackQuery, state: FSMContext):
    """Обработка оплаты USDT TRC20"""
    try:
        tariff_id = int(callback.data.split(':')[1])
        
        # Получаем connection_type из state, если есть
        data = await state.get_data()
        connection_type = data.get('connection_type', 'tcp')
        
        # Сохраняем connection_type для использования при проверке оплаты
        await state.update_data(connection_type=connection_type)
        
        # Проверяем настройки криптоплатежей
        crypto_settings = await tron_pay_manager.get_crypto_settings()
        if not crypto_settings or not crypto_settings.get('usdt_wallet'):
            await callback.answer("Оплата USDT TRC20 временно недоступна", show_alert=True)
            return

        # Получаем информацию о тарифе
        async with aiosqlite.connect(db.db_path) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute('SELECT * FROM tariff WHERE id = ?', (tariff_id,)) as cursor:
                tariff = await cursor.fetchone()

        if not tariff:
            await callback.answer("Тариф не найден", show_alert=True)
            return

        # Создаем платеж с уникальной суммой
        payment = await tron_pay_manager.create_payment(
            user_id=callback.from_user.id,
            tariff_id=tariff_id,
            amount_rub=float(tariff['price'])
        )

        if not payment:
            await callback.answer("Ошибка при создании платежа", show_alert=True)
            return

        # Формируем сообщение с инструкцией
        expires_at_formatted = payment['expires_at'].strftime('%H:%M:%S')
        
        message_text = (
            f"💰 <b>Оплата тарифа {tariff['name']}</b>\n\n"
            f"💵 Сумма в рублях: {payment['amount_rub']} ₽\n"
            f"💎 Курс USDT/RUB: {payment['rate']:.2f}\n"
            f"💸 Сумма в USDT: ~{payment['amount_usdt']:.2f}\n\n"
            f"⚠️ <b>Важно! Переведите точную сумму:</b>\n"
            f"<code>{payment['unique_amount_usdt']:.6f}</code> USDT\n\n"
            f"💳 <b>Адрес кошелька TRC20:</b>\n"
            f"<code>{payment['wallet']}</code>\n\n"
            f"⏱ Платеж действителен до: {expires_at_formatted}\n\n"
            f"📋 <b>Инструкция:</b>\n"
            f"1. Скопируйте адрес кошелька (нажмите на него)\n"
            f"2. Скопируйте точную сумму: <code>{payment['unique_amount_usdt']:.6f}</code>\n"
            f"3. Переведите USDT через сеть TRC20\n"
            f"4. После отправки нажмите 'Проверить оплату'\n\n"
            f"⚠️ <b>ВНИМАНИЕ:</b> Переводите строго указанную сумму!\n"
            f"Это необходимо для автоматической проверки платежа."
        )

        keyboard = InlineKeyboardBuilder()
        keyboard.button(
            text="🔄 Проверить оплату",
            callback_data=f"check_crypto_payment:{payment['payment_id']}"
        )
        keyboard.button(text="❌ Отменить", callback_data="cancel_payment")
        keyboard.adjust(1)

        await callback.message.edit_text(
            text=message_text,
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка при создании крипто-платежа: {e}")
        await callback.answer(
            "Произошла ошибка при создании платежа",
            show_alert=True
        )

@router.callback_query(F.data.startswith("check_crypto_payment:"))
async def check_crypto_payment(callback: CallbackQuery, state: FSMContext):
    """Проверка статуса USDT TRC20 платежа"""
    try:
        payment_id = int(callback.data.split(':')[1])
        
        await callback.answer("Проверяю транзакцию... ⏳", show_alert=False)
        
        # Проверяем платеж
        result = await tron_pay_manager.check_payment(payment_id)
        
        if not result['success']:
            await callback.answer(result['message'], show_alert=True)
            if result.get('code') == 'not_found':
                payment = result.get('payment')
                if payment:
                    unique_amount = float(payment['unique_amount_usdt'])
                    expires_at = datetime.fromisoformat(payment['expires_at'])
                    remaining_seconds = max(0, int((expires_at - datetime.now()).total_seconds()))
                    minutes_left, seconds_left = divmod(remaining_seconds, 60)
                    time_hint = f"{minutes_left} мин {seconds_left:02d} сек" if remaining_seconds > 0 else "менее минуты"

                    wallet_hint = ""
                    settings = await tron_pay_manager.get_crypto_settings()
                    if settings and settings.get('usdt_wallet'):
                        wallet = settings['usdt_wallet']
                        if isinstance(wallet, str) and len(wallet) > 12:
                            wallet_hint = f"\n💳 Кошелёк: <code>{wallet[:6]}...{wallet[-6:]}</code>"
                        else:
                            wallet_hint = f"\n💳 Кошелёк: <code>{wallet}</code>"

                    notice_text = (
                        "❌ <b>Оплата не найдена.</b>\n\n"
                        f"Проверьте, что вы отправили точную сумму <code>{unique_amount:.6f}</code> USDT через сеть TRC20.{wallet_hint}\n"
                        f"⏱ Проверка доступна до {expires_at.strftime('%H:%M:%S')} (осталось {time_hint}).\n\n"
                        "Если транзакция уже отправлена, подождите 1-2 минуты и повторите проверку."
                    )

                    await callback.message.answer(notice_text, parse_mode="HTML")
            return
        
        # Платеж подтвержден!
        payment = result['payment']
        
        # Получаем connection_type из state или используем дефолт
        data = await state.get_data() if state else {}
        connection_type = data.get('connection_type', 'tcp')
        
        # Записываем платеж в базу
        async with aiosqlite.connect(db.db_path) as db_conn:
            await db_conn.execute("""
                INSERT INTO payments (user_id, tariff_id, price, date)
                VALUES (?, ?, ?, datetime('now'))
            """, (payment['user_id'], payment['tariff_id'], payment['amount_rub']))
            await db_conn.commit()
        
        # Создаем подписку
        subscription = await subscription_manager.create_subscription(
            user_id=payment['user_id'],
            tariff_id=payment['tariff_id'],
            is_trial=False,
            bot=callback.bot,
            connection_type=connection_type
        )

        if not subscription:
            logger.error("Ошибка при создании подписки в базе данных")
            await callback.message.edit_text(
                "Произошла ошибка при активации подписки. Пожалуйста, обратитесь в поддержку.",
                reply_markup=None
            )
            return

        # Получаем информацию о тарифе
        async with aiosqlite.connect(db.db_path) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute('SELECT * FROM tariff WHERE id = ?', (payment['tariff_id'],)) as cursor:
                tariff = await cursor.fetchone()
        
        # Получаем max_devices из тарифа
        max_devices = subscription.get('max_devices', 1)
        devices_text = f"{max_devices} устройств" if max_devices > 1 else "1 устройстве"
        if max_devices == 0:
            devices_text = "без ограничений"

        config_link = subscription.get('config_link') or subscription.get('subscription_url') or subscription['vless']
        
        message_text = (
            "🎉 <b>Поздравляем! Оплата получена!</b>\n\n"
            f"✅ Транзакция подтверждена\n"
            f"💰 Сумма: {payment['unique_amount_usdt']:.6f} USDT\n\n"
            f"<blockquote>"
            f"📦 <b>Тариф:</b> {tariff['name']}\n"
            f"📅 <b>Действует до:</b> {subscription['end_date'].strftime('%d.%m.%Y')}\n"
            f"</blockquote>\n\n"
            "🔑 <b>Ваш VLESS ключ:</b>\n"
            "<blockquote>"
            f"<code>{config_link}</code>\n"
            "</blockquote>\n\n"
            "📲 <b>Как подключить:</b>\n"
            "1. Скопируйте ключ выше (нажмите на него)\n"
            "2. Откройте VPN приложение:\n"
            "   • Android/iOS/Mac: V2Box\n"
            "   • Windows: Hiddify\n"
            "3. Нажмите '+' → 'Импорт из буфера'\n"
            "4. Нажмите 'Подключить' ▶️\n\n"
            "⚠️ <b>Важно:</b>\n"
            f"• Этот конфиг работает на {devices_text}\n"
            "• Подробные инструкции: 📢 Инструкции"
        )

        await callback.message.edit_text(
            text=message_text,
            parse_mode="HTML",
            reply_markup=None
        )
        
        # Отправляем обычную клавиатуру отдельным сообщением
        await callback.message.answer(
            "💡 Конфиг готов! Скопируйте ключ и добавьте в приложение",
            reply_markup=get_lk_keyboard()
        )
        
        # Очищаем state
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при проверке крипто-платежа: {e}")
        logger.debug(f"Детали ошибки: {str(e)}")
        await callback.answer(
            "Произошла ошибка при проверке платежа",
            show_alert=True
        )

@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery):
    """Отмена платежа"""
    try:
        await callback.message.edit_text(
            "❌ Оплата отменена",
            reply_markup=None
        )
    except Exception as e:
        logger.error(f"Ошибка при отмене платежа: {e}")
        await callback.answer("Произошла ошибка", show_alert=True) 
