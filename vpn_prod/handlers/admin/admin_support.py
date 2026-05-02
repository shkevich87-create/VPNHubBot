from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
import aiosqlite

from handlers.database import db
from handlers.admin.admin_kb import get_admin_keyboard

router = Router()

class SupportStates(StatesGroup):
    waiting_for_support_url = State()

def get_support_keyboard() -> InlineKeyboardBuilder:
    """Создание клавиатуры для управления поддержкой"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔗 Изменить ссылку на поддержку", callback_data="admin_edit_support_url")
    keyboard.button(text="🔙 Назад", callback_data="servers_back_to_admin")
    keyboard.adjust(1)
    return keyboard.as_markup()

@router.callback_query(F.data == "admin_show_support")
async def show_support_info(callback: CallbackQuery):
    """Отображение информации о технической поддержке"""
    try:
        await callback.message.delete()
        
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT message, bot_version, support_url
                FROM support_info
                LIMIT 1
            """) as cursor:
                support_info = await cursor.fetchone()

        if not support_info:
            await callback.message.answer(
                "❌ Информация о поддержке не найдена",
                reply_markup=get_admin_keyboard()
            )
            return

        message_text = (
            "Служба технической поддержки!\n"
            "<blockquote>"
            f"Версия бота: {support_info['bot_version']}\n"
            f"Описание: {support_info['message']}\n"
            f"Ссылка: {support_info['support_url']}\n"
            "</blockquote>"
        )

        await callback.message.answer(
            text=message_text,
            reply_markup=get_support_keyboard(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка при отображении информации о поддержке: {e}")
        await callback.message.answer(
            "Произошла ошибка при получении информации о поддержке",
            reply_markup=get_admin_keyboard()
        )

@router.callback_query(F.data == "admin_edit_support_url")
async def edit_support_url(callback: CallbackQuery, state: FSMContext):
    """Начало процесса изменения ссылки на поддержку"""
    try:
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Отмена", callback_data="admin_show_support")
        
        await callback.message.answer(
            "🔗 Отправьте новую ссылку на поддержку (например, https://t.me/support_username):",
            reply_markup=keyboard.as_markup()
        )
        
        await state.set_state(SupportStates.waiting_for_support_url)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при начале изменения ссылки на поддержку: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)

@router.message(SupportStates.waiting_for_support_url)
async def process_support_url(message: Message, state: FSMContext):
    """Обработка новой ссылки на поддержку"""
    try:
        new_support_url = message.text.strip()
        
        # Простая валидация URL
        if not (new_support_url.startswith('http://') or new_support_url.startswith('https://') or new_support_url.startswith('@')):
            await message.answer(
                "❌ Неверный формат ссылки. Ссылка должна начинаться с http://, https:// или @username"
            )
            return
        
        async with aiosqlite.connect(db.db_path) as conn:
            # Проверяем, есть ли уже запись
            async with conn.execute("SELECT id FROM support_info LIMIT 1") as cursor:
                existing = await cursor.fetchone()
            
            if existing:
                # Обновляем существующую запись
                await conn.execute("""
                    UPDATE support_info 
                    SET support_url = ?
                    WHERE id = (SELECT id FROM support_info LIMIT 1)
                """, (new_support_url,))
            else:
                # Создаем новую запись с дефолтными значениями
                await conn.execute("""
                    INSERT INTO support_info (message, bot_version, support_url)
                    VALUES (?, ?, ?)
                """, ("Обратитесь в поддержку", "1.0", new_support_url))
            
            await conn.commit()
        
        await message.answer(
            f"✅ Ссылка на поддержку успешно обновлена!\n\n"
            f"Новая ссылка: {new_support_url}",
            reply_markup=get_admin_keyboard()
        )
        
        await state.clear()
        logger.info(f"Ссылка на поддержку обновлена администратором {message.from_user.id}: {new_support_url}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке новой ссылки на поддержку: {e}")
        await message.answer(
            "❌ Произошла ошибка при обновлении ссылки на поддержку",
            reply_markup=get_admin_keyboard()
        )
        await state.clear() 