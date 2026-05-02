from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
import aiosqlite
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from handlers.database import db
from handlers.admin.admin_kb import get_admin_keyboard

router = Router()

class TariffDeleteStates(StatesGroup):
    waiting_for_name = State()

def get_admin_show_tariff_keyboard():
    """Создание клавиатуры для управления тарифами"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="➕ Добавить тариф", callback_data="add_tariff")
    keyboard.button(text="❌ Удалить тариф", callback_data="delete_tariff")
    keyboard.button(text="🔙 Назад", callback_data="tariff_back_to_admin")
    keyboard.adjust(2, 1)
    return keyboard.as_markup()

@router.callback_query(F.data == "admin_show_tariff")
async def show_tariffs(callback: CallbackQuery):
    """Отображение списка тарифов"""
    try:
        await callback.message.delete()
        
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT t.*, s.name as server_name 
                FROM tariff t 
                JOIN server_settings s ON t.server_id = s.id 
                WHERE t.is_enable = 1
                ORDER BY t.id
            """) as cursor:
                tariffs = await cursor.fetchall()

        if not tariffs:
            await callback.message.answer(
                "Активные тарифные планы отсутствуют",
                reply_markup=get_admin_show_tariff_keyboard()
            )
            return

        message_text = "📋 <b>Список активных тарифных планов:</b>\n\n"
        
        for tariff in tariffs:
            message_text += (
                f"<blockquote>"
                f"<b>Наименование:</b> {tariff['name']}\n"
                f"<b>Описание:</b> {tariff['description']}\n"
                f"<b>Срок:</b> {tariff['left_day']} дней\n"
                f"<b>Стоимость:</b> {tariff['price']} руб.\n"
                f"<b>Страна:</b> {tariff['server_name']}\n"
                f"</blockquote>\n"
            )

        await callback.message.answer(
            text=message_text,
            reply_markup=get_admin_show_tariff_keyboard(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка при отображении тарифов: {e}")
        await callback.message.answer(
            "Произошла ошибка при получении списка тарифов",
            reply_markup=get_admin_keyboard()
        )

@router.callback_query(F.data == "tariff_back_to_admin")
async def process_back_to_admin(callback: CallbackQuery):
    """Обработчик кнопки возврата в админ-панель"""
    try:
        await callback.message.delete()
        admin_message = await db.get_bot_message("admin")
        text = admin_message['text'] if admin_message else "Панель администратора"
        
        await callback.message.answer(
            text=text,
            reply_markup=get_admin_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка при возврате в админ-панель: {e}")
        await callback.message.answer(
            "Произошла ошибка при возврате в админ-панель",
            reply_markup=get_admin_keyboard()
        )

@router.callback_query(F.data == "delete_tariff")
async def start_delete_tariff(callback: CallbackQuery, state: FSMContext):
    """Начало процесса удаления тарифа"""
    try:
        await callback.message.delete()
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Отмена", callback_data="cancel_delete_tariff")
        
        await callback.message.answer(
            "Введите наименование тарифного плана для удаления:",
            reply_markup=keyboard.as_markup()
        )
        
        await state.set_state(TariffDeleteStates.waiting_for_name)
        
    except Exception as e:
        logger.error(f"Ошибка при начале удаления тарифа: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=get_admin_show_tariff_keyboard()
        )

@router.message(TariffDeleteStates.waiting_for_name)
async def process_delete_tariff(message: Message, state: FSMContext):
    """Обработка введенного названия тарифа и его удаление"""
    try:
        tariff_name = message.text.strip()
        

        async with aiosqlite.connect(db.db_path) as conn:
            async with conn.execute(
                "SELECT name FROM tariff WHERE name = ? AND is_enable = 1",
                (tariff_name,)
            ) as cursor:
                tariff = await cursor.fetchone()
                
            if not tariff:
                await message.answer(
                    "❌ Тарифный план с таким названием не найден.",
                    reply_markup=get_admin_show_tariff_keyboard()
                )
                await state.clear()
                return
                
            await conn.execute(
                "UPDATE tariff SET is_enable = 0 WHERE name = ?",
                (tariff_name,)
            )
            await conn.commit()
            
        await message.answer(
            f"✅ Тарифный план '{tariff_name}' успешно удален",
            reply_markup=get_admin_show_tariff_keyboard()
        )
        logger.info(f"Удален тарифный план: {tariff_name}")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении тарифа: {e}")
        await message.answer(
            "Произошла ошибка при удалении тарифного плана. Попробуйте позже.",
            reply_markup=get_admin_show_tariff_keyboard()
        )
    finally:
        await state.clear()

@router.callback_query(F.data == "cancel_delete_tariff")
async def cancel_delete_tariff(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления тарифа"""
    await state.clear()
    await callback.message.edit_text(
        "Удаление тарифа отменено",
        reply_markup=get_admin_show_tariff_keyboard()
    ) 