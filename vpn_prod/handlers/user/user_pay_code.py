from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from handlers.database import db
from datetime import datetime, timedelta
from loguru import logger
from aiogram.utils.keyboard import InlineKeyboardBuilder
from handlers.buy_subscribe import subscription_manager

router = Router()

class PaymentCodeState(StatesGroup):
    waiting_for_code = State()

def get_confirm_keyboard():
    """Создание клавиатуры подтверждения"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Применить", callback_data="confirm_payment_code")
    keyboard.button(text="❌ Отмена", callback_data="cancel_payment_code")
    keyboard.adjust(2)
    return keyboard.as_markup()

def get_back_to_lk_keyboard():
    """Создание клавиатуры с кнопкой возврата в главное меню"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data="tariff_back_to_start")
    return keyboard.as_markup()

@router.callback_query(F.data.startswith("apply_payments_code:"))
async def start_payment_code(callback: CallbackQuery, state: FSMContext):
    """Начало процесса оплаты кодом"""
    try:
        tariff_id = int(callback.data.split(':')[1])
        
        tariff = await db.get_tariff(tariff_id)
        if not tariff:
            await callback.answer("❌ Тариф не найден", show_alert=True)
            return
        
        await state.update_data(tariff_id=tariff_id)
        
        await callback.message.delete()
        await callback.message.answer(
            f"Вы выбрали оплату кодом, пожалуйста введите код для оплаты тарифного плана <b>{tariff['name']}</b>",
            parse_mode="HTML"
        )
        await state.set_state(PaymentCodeState.waiting_for_code)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при начале оплаты кодом: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)

@router.message(PaymentCodeState.waiting_for_code)
async def process_payment_code(message: Message, state: FSMContext):
    """Обработка введенного кода оплаты"""
    try:
        payment_code = await db.get_payment_code(message.text)
        
        if not payment_code:
            await message.answer(
                "❌ Код оплаты не найден или уже использован",
                reply_markup=get_back_to_lk_keyboard()
            )
            await state.clear()
            return
        
        data = await state.get_data()
        tariff_id = data['tariff_id']
        tariff = await db.get_tariff(tariff_id)
        
        if not tariff:
            await message.answer("❌ Тариф не найден")
            await state.clear()
            return

        if payment_code['sum'] < tariff['price']:
            await message.answer(
                f"❌ Недостаточно средств для оплаты тарифа\n\n"
                f"Сумма кода: {payment_code['sum']} ₽\n"
                f"Стоимость тарифа: {tariff['price']} ₽",
                reply_markup=get_back_to_lk_keyboard()
            )
            await state.clear()
            return
        
        await state.update_data(payment_code=payment_code)
        
        message_text = (
        f"💳 Вы собираетесь применить код оплаты: <b>{payment_code['pay_code']}</b>\n"
        f"💰 На сумму: <b>{payment_code['sum']} ₽</b>\n"
        f"📋 Для оплаты тарифного плана: <b>{tariff['name']}</b>\n"
        f"🏷️ Стоимость тарифа: <b>{tariff['price']} ₽</b>\n\n"
        f"⚠️ Код оплаты будет <b>погашен полностью</b> и <b>не подлежит повторному применению</b>!"
        )

        
        await message.answer(
            message_text,
            parse_mode="HTML",
            reply_markup=get_confirm_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке кода оплаты: {e}")
        await message.answer("❌ Произошла ошибка при обработке кода")
        await state.clear()

@router.callback_query(F.data == "confirm_payment_code")
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    """Подтверждение оплаты кодом"""
    try:
        data = await state.get_data()
        if 'payment_code' not in data or 'tariff_id' not in data:
            await callback.answer("Сессия оплаты истекла. Введите код заново.", show_alert=True)
            await state.clear()
            return

        payment_code = data['payment_code']
        tariff_id = data['tariff_id']
        
        tariff = await db.get_tariff(tariff_id)
        if not tariff:
            await callback.answer("❌ Тариф не найден", show_alert=True)
            await state.clear()
            return
        
        if not await db.disable_payment_code(payment_code['pay_code']):
            await callback.answer("❌ Ошибка при обработке кода", show_alert=True)
            await state.clear()
            return
        
        # Получаем connection_type из state, если есть
        data = await state.get_data()
        connection_type = data.get('connection_type', 'tcp')
        
        subscription = await subscription_manager.create_subscription(
            user_id=callback.from_user.id,
            tariff_id=tariff_id,
            bot=callback.bot,
            connection_type=connection_type
        )
        
        if subscription:
            from handlers.user.user_kb import get_success_by_keyboard
            
            max_devices = subscription.get('max_devices', 1)
            devices_text = f"{max_devices} устройств" if max_devices > 1 else "1 устройстве"
            if max_devices == 0:
                devices_text = "без ограничений"
            
            config_link = subscription.get('config_link') or subscription.get('subscription_url') or subscription['vless']

            message_text = (
                "🎉 <b>Поздравляем! Ваша подписка активирована!</b>\n\n"
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
                "2. Откройте VPN приложение (V2Box/Hiddify)\n"
                "3. Нажмите '+' → 'Импорт из буфера'\n"
                "4. Нажмите 'Подключить' ▶️\n\n"
                "⚠️ <b>Важно:</b>\n"
                f"• Этот конфиг работает на {devices_text}\n"
                "• Инструкции в разделе 📢 Инструкции"
            )
            
            await callback.message.edit_text(
                text=message_text,
                parse_mode="HTML"
            )
            
            # Отправляем обычную клавиатуру отдельным сообщением
            await callback.message.answer(
                "💡 Конфиг готов! Скопируйте ключ и добавьте в приложение",
                reply_markup=get_success_by_keyboard()
            )
        else:
            await callback.answer("❌ Ошибка при создании подписки", show_alert=True)
            await db.enable_payment_code(payment_code['pay_code'])
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при подтверждении оплаты: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
        await state.clear()

@router.callback_query(F.data == "cancel_payment_code")
async def cancel_payment(callback: CallbackQuery, state: FSMContext):
    """Отмена оплаты кодом"""
    try:
        await state.clear()
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Тарифы", callback_data="start_tariffs")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="tariff_back_to_start")]
        ])
        
        await callback.message.edit_text(
            "❌ Оплата кодом отменена",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при отмене оплаты кодом: {e}")
        await callback.answer("Произошла ошибка", show_alert=True) 
