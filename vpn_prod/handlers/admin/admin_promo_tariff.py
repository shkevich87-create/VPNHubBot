from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
import db_compat as aiosqlite
from loguru import logger
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from handlers.database import db
from handlers.admin.admin_kb import get_admin_show_promo_tariff_keyboard

router = Router()

class PromoStates(StatesGroup):
    waiting_for_limit = State()
    waiting_for_percentage = State()

class PromoTariffStates(StatesGroup):
    waiting_for_delete = State()

@router.callback_query(F.data == "admin_show_promo_tariff")
async def show_promo_tariffs(callback: CallbackQuery):
    """Отображение списка промо-тарифов"""
    try:
        await callback.message.delete()
        
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT tp.*, s.name as server_name
                FROM tariff_promo tp
                JOIN server_settings s ON tp.server_id = s.id
                WHERE tp.is_enable = 1
                ORDER BY tp.id
            """) as cursor:
                promo_tariffs = await cursor.fetchall()

        if not promo_tariffs:
            await callback.message.answer(
                "🔍 Промо-тарифы не найдены",
                reply_markup=get_admin_show_promo_tariff_keyboard()
            )
            return

        message_text = "🎁 Доступные промо-тарифы 🎁\nВыберите промо-тариф для отправки пользователям. 🚀\n\n"
        
        for tariff in promo_tariffs:
            message_text += (
                "<blockquote>"
                f"ID: {tariff['id']}\n"
                f"Наименование: {tariff['name']}\n"
                f"Описание: {tariff['description']}\n"
                f"Промо дней: {tariff['left_day']}\n"
                f"Страна: {tariff['server_name']}\n"
                "</blockquote>\n"
            )

        await callback.message.answer(
            text=message_text,
            reply_markup=get_admin_show_promo_tariff_keyboard(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка при отображении промо-тарифов: {e}")
        await callback.message.answer(
            "Произошла ошибка при загрузке промо-тарифов",
            reply_markup=get_admin_show_promo_tariff_keyboard()
        ) 

@router.callback_query(F.data == "admin_delete_promo_tariff")
async def start_delete_promo_tariff(callback: CallbackQuery, state: FSMContext):
    """Начало процесса удаления промо-тарифа"""
    try:
        await callback.message.delete()
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Отмена", callback_data="cancel_delete_promo")
        
        await callback.message.answer(
            "Введите ID для удаления промо тарифа:",
            reply_markup=keyboard.as_markup()
        )
        
        await state.set_state(PromoTariffStates.waiting_for_delete)
        
    except Exception as e:
        logger.error(f"Ошибка при начале удаления промо-тарифа: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=get_admin_show_promo_tariff_keyboard()
        )

@router.message(PromoTariffStates.waiting_for_delete)
async def process_delete_promo_tariff(message: Message, state: FSMContext):
    """Обработка введенного ID и удаление промо-тарифа"""
    try:
        tariff_id = int(message.text.strip())
        
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            async with conn.execute("""
                SELECT tp.*, s.name as server_name 
                FROM tariff_promo tp
                JOIN server_settings s ON tp.server_id = s.id
                WHERE tp.id = ? AND tp.is_enable = 1
            """, (tariff_id,)) as cursor:
                tariff = await cursor.fetchone()
                
            if not tariff:
                await message.answer(
                    "❌ Промо-тариф с таким ID не найден или уже удален.",
                    reply_markup=get_admin_show_promo_tariff_keyboard()
                )
                await state.clear()
                return
                
            await conn.execute(
                "UPDATE tariff_promo SET is_enable = 0 WHERE id = ?",
                (tariff_id,)
            )
            await conn.commit()
            
        await message.answer(
            f"✅ Промо-тариф '{tariff['name']}' успешно удален.",
            reply_markup=get_admin_show_promo_tariff_keyboard()
        )
        logger.info(f"Удален промо-тариф: {tariff['name']} (ID: {tariff_id})")
        
    except ValueError:
        await message.answer(
            "Пожалуйста, введите корректный ID (целое число)"
        )
        return
    except Exception as e:
        logger.error(f"Ошибка при удалении промо-тарифа: {e}")
        await message.answer(
            "Произошла ошибка при удалении промо-тарифа. Попробуйте позже.",
            reply_markup=get_admin_show_promo_tariff_keyboard()
        )
    finally:
        await state.clear()

@router.callback_query(F.data == "cancel_delete_promo")
async def cancel_delete_promo(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления промо-тарифа"""
    await state.clear()
    await callback.message.edit_text(
        "Удаление промо-тарифа отменено",
        reply_markup=get_admin_show_promo_tariff_keyboard()
    ) 