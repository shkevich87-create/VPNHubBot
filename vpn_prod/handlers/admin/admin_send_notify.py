from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import db_compat as aiosqlite
from loguru import logger

from handlers.database import db
from handlers.admin.admin_kb import get_admin_keyboard

router = Router()

class NotifyStates(StatesGroup):
    waiting_for_message = State()

def get_cancel_keyboard():
    """Создание клавиатуры с кнопкой отмены"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Отмена", callback_data="cancel_send_notification")
    return keyboard.as_markup()

@router.callback_query(F.data == "admin_send_notification")
async def start_notification(callback: CallbackQuery, state: FSMContext):
    """Начало процесса рассылки"""
    try:
        await callback.message.delete()
        
        async with aiosqlite.connect(db.db_path) as conn:
            async with conn.execute("""
                SELECT COUNT(*) as count 
                FROM user 
                WHERE is_enable = 1
            """) as cursor:
                result = await cursor.fetchone()
                users_count = result[0] if result else 0

        await callback.message.answer(
            f"📢 <b>Меню массовой рассылки 📢</b>\n"
            f"Вы находитесь в разделе отправки сообщений.\n"
            f"<blockquote>"
            f"🔹 Ваше сообщение будет отправлено <b>{users_count}</b> пользователям.\n"
            f"✍️ Введите текст рассылки ниже и отправьте.\n"
            f"</blockquote>"
            f"🚀 Готовы? Начинаем!",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(NotifyStates.waiting_for_message)
        
    except Exception as e:
        logger.error(f"Ошибка при начале рассылки: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=get_admin_keyboard()
        )

@router.message(NotifyStates.waiting_for_message)
async def process_notification(message: Message, state: FSMContext):
    """Обработка сообщения для рассылки"""
    try:
        notification_text = message.text
        success_count = 0
        error_count = 0
        
        async with aiosqlite.connect(db.db_path) as conn:
            async with conn.execute("""
                SELECT telegram_id 
                FROM user 
                WHERE is_enable = 1
            """) as cursor:
                users = await cursor.fetchall()

        for user in users:
            try:
                await message.bot.send_message(
                    chat_id=user[0],
                    text=notification_text
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения пользователю {user[0]}: {e}")
                error_count += 1

        await message.answer(
            f"✅ Рассылка завершена!\n\n"
            f"📊 Статистика:\n"
            f"✓ Успешно отправлено: {success_count}\n"
            f"✗ Ошибок: {error_count}",
            reply_markup=get_admin_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении рассылки: {e}")
        await message.answer(
            "Произошла ошибка при выполнении рассылки.",
            reply_markup=get_admin_keyboard()
        )
    finally:
        await state.clear()

@router.callback_query(F.data == "cancel_send_notification")
async def cancel_notification(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки"""
    await state.clear()
    await callback.message.edit_text(
        "Рассылка отменена",
        reply_markup=get_admin_keyboard()
    ) 