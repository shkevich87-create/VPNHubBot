from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
import db_compat as aiosqlite
import re

from handlers.database import db
from handlers.admin.admin_kb import get_admin_keyboard
from handlers.tron_pay import tron_pay_manager

router = Router()

class CryptoPayState(StatesGroup):
    waiting_for_wallet = State()

def get_crypto_pay_keyboard():
    """Клавиатура управления USDT TRC20"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="➕ Установить кошелек", callback_data="crypto_pay_add")
    keyboard.button(text="✏️ Изменить кошелек", callback_data="crypto_pay_add")
    keyboard.button(text="❌ Удалить настройки", callback_data="crypto_pay_delete")
    keyboard.button(text="🔙 Назад", callback_data="servers_back_to_admin")
    keyboard.adjust(2, 1)
    return keyboard.as_markup()

@router.callback_query(F.data == "admin_show_crypto_pay")
async def show_crypto_settings(callback: CallbackQuery):
    """Отображение текущих настроек USDT TRC20"""
    try:
        if not await db.is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав для выполнения этого действия")
            return

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute('SELECT * FROM crypto_settings LIMIT 1') as cursor:
                settings = await cursor.fetchone()

        if settings and settings['usdt_wallet']:
            wallet = settings['usdt_wallet']
            # Скрываем часть адреса для безопасности
            hidden_wallet = f"{wallet[:6]}...{wallet[-6:]}" if len(wallet) > 12 else wallet

            message_text = (
                "📊 <b>Текущие настройки оплаты USDT TRC20:</b>\n\n"
                f"💳 Кошелек: <code>{hidden_wallet}</code>\n"
                f"💰 Минимальная сумма: {settings['min_amount']} USDT\n"
                f"📡 Статус: {'✅ Активен' if settings['is_enable'] else '❌ Отключен'}\n\n"
                "ℹ️ При оплате пользователи получают уникальную сумму для отслеживания транзакций"
            )
        else:
            message_text = (
                "⚠️ <b>Оплата USDT TRC20 не настроена</b>\n\n"
                "Для настройки оплаты криптовалютой необходимо:\n"
                "1. Установить адрес кошелька USDT TRC20\n"
                "2. Убедиться, что кошелек активен\n\n"
                "Нажмите '➕ Установить кошелек' для начала"
            )

        await callback.message.edit_text(
            text=message_text,
            reply_markup=get_crypto_pay_keyboard(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка при отображении настроек USDT TRC20: {e}")
        await callback.answer("Произошла ошибка при получении настроек", show_alert=True)

@router.callback_query(F.data == "crypto_pay_add")
async def start_add_settings(callback: CallbackQuery, state: FSMContext):
    """Начало процесса добавления/изменения кошелька"""
    try:
        if not await db.is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав для выполнения этого действия")
            return
            
        await callback.message.edit_text(
            "💳 <b>Настройка USDT TRC20 кошелька</b>\n\n"
            "Введите адрес кошелька USDT TRC20:\n",
            reply_markup=None,
            parse_mode="HTML"
        )
        await state.set_state(CryptoPayState.waiting_for_wallet)
    except Exception as e:
        logger.error(f"Ошибка при старте добавления настроек: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)

@router.message(CryptoPayState.waiting_for_wallet)
async def process_wallet(message: Message, state: FSMContext):
    """Обработка введенного адреса кошелька"""
    try:
        if not await db.is_admin(message.from_user.id):
            await message.answer("У вас нет прав для выполнения этого действия")
            await state.clear()
            return

        wallet_address = message.text.strip()
        
        # Валидация адреса TRON (TRC20)
        # Адрес TRON начинается с 'T' и имеет длину 34 символа
        if not re.match(r'^T[A-Za-z1-9]{33}$', wallet_address):
            await message.answer(
                "❌ <b>Неверный формат адреса!</b>\n\n"
                "Адрес TRON (TRC20) должен:\n"
                "• Начинаться с буквы 'T'\n"
                "• Содержать 34 символа\n"
                "• Содержать только латинские буквы и цифры\n\n"
                "Попробуйте еще раз:",
                parse_mode="HTML"
            )
            return

        # Сохраняем настройки
        async with aiosqlite.connect(db.db_path) as conn:
            # Проверяем, есть ли уже записи
            async with conn.execute('SELECT COUNT(*) FROM crypto_settings') as cursor:
                count = await cursor.fetchone()
            
            if count[0] > 0:
                # Обновляем существующую запись
                await conn.execute("""
                    UPDATE crypto_settings 
                    SET usdt_wallet = ?, is_enable = 1
                """, (wallet_address,))
            else:
                # Создаем новую запись
                await conn.execute("""
                    INSERT INTO crypto_settings (usdt_wallet, is_enable, min_amount)
                    VALUES (?, 1, 1.00)
                """, (wallet_address,))
            
            await conn.commit()

        logger.info(f"USDT TRC20 кошелек установлен: {wallet_address[:6]}...{wallet_address[-6:]}")

        await message.answer(
            "✅ <b>Кошелек успешно сохранен!</b>\n\n"
            f"💳 Адрес: <code>{wallet_address}</code>\n\n",
            reply_markup=get_crypto_pay_keyboard(),
            parse_mode="HTML"
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при сохранении кошелька: {e}")
        await message.answer(
            "Произошла ошибка при сохранении настроек",
            reply_markup=get_crypto_pay_keyboard()
        )
        await state.clear()

@router.callback_query(F.data == "crypto_pay_delete")
async def delete_settings(callback: CallbackQuery):
    """Удаление настроек USDT TRC20"""
    try:
        if not await db.is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав для выполнения этого действия")
            return
            
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute('UPDATE crypto_settings SET is_enable = 0, usdt_wallet = NULL')
            await conn.commit()

        await callback.message.edit_text(
            "✅ Настройки USDT TRC20 удалены. Оплата криптовалютой отключена.",
            reply_markup=get_crypto_pay_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка при удалении настроек: {e}")
        await callback.answer("Произошла ошибка при удалении настроек", show_alert=True) 