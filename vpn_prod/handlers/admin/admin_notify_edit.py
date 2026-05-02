from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import db_compat as aiosqlite
from loguru import logger

from handlers.database import db
from handlers.admin.admin_kb import get_admin_notifications_keyboard

router = Router()

class NotifyEditStates(StatesGroup):
    waiting_for_reg_notify = State()
    waiting_for_pay_notify = State()

def get_cancel_keyboard():
    """Создание клавиатуры с кнопкой отмены"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Отмена", callback_data="cancel_add_notification")
    return keyboard.as_markup()

@router.callback_query(F.data == "admin_add_notification")
async def start_add_notification(callback: CallbackQuery, state: FSMContext):
    """Начало процесса добавления уведомлений"""
    try:
        await callback.message.delete()
        
        await callback.message.answer(
            "📢 Отправь мне Telegram ID для оповещений о регистрации новых пользователей, 0 для пропуска",
            reply_markup=get_cancel_keyboard()
        )
        
        await state.set_state(NotifyEditStates.waiting_for_reg_notify)
        
    except Exception as e:
        logger.error(f"Ошибка при начале добавления уведомлений: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=get_admin_notifications_keyboard()
        )

@router.message(NotifyEditStates.waiting_for_reg_notify)
async def process_reg_notify(message: Message, state: FSMContext):
    """Обработка ID для уведомлений о регистрации"""
    try:
        reg_notify = int(message.text.strip())
        
        await state.update_data(reg_notify=reg_notify)
        
        await message.answer(
            "📢 Отправь мне Telegram ID для оповещений об успешной оплате, 0 для пропуска",
            reply_markup=get_cancel_keyboard()
        )
        
        await state.set_state(NotifyEditStates.waiting_for_pay_notify)
        
    except ValueError:
        await message.answer(
            "Пожалуйста, введите корректный ID (целое число) или 0 для пропуска"
        )
        return
    except Exception as e:
        logger.error(f"Ошибка при обработке ID для регистраций: {e}")
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=get_admin_notifications_keyboard()
        )
        await state.clear()

@router.message(NotifyEditStates.waiting_for_pay_notify)
async def process_pay_notify(message: Message, state: FSMContext):
    """Обработка ID для уведомлений об оплате"""
    try:
        pay_notify = int(message.text.strip())
        
        data = await state.get_data()
        reg_notify = data.get('reg_notify')
        
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute("""
                UPDATE bot_settings 
                SET reg_notify = ?, pay_notify = ?
            """, (reg_notify, pay_notify))
            await conn.commit()
        
        message_text = (
            "✅ Настройки уведомлений успешно обновлены!\n\n"
            "<b>Новые настройки:</b>\n"
            "<blockquote>"
            f"🔔 <b>Оповещение о регистрации:</b> {reg_notify if reg_notify != 0 else 'Выключено'}\n"
            f"💰 <b>Оповещение об оплате:</b> {pay_notify if pay_notify != 0 else 'Выключено'}\n"
            "</blockquote>"
        )
        
        await message.answer(
            text=message_text,
            reply_markup=get_admin_notifications_keyboard(),
            parse_mode="HTML"
        )
        logger.info(f"Обновлены настройки уведомлений: reg_notify={reg_notify}, pay_notify={pay_notify}")
        
    except ValueError:
        await message.answer(
            "Пожалуйста, введите корректный ID (целое число) или 0 для пропуска"
        )
        return
    except Exception as e:
        logger.error(f"Ошибка при обновлении настроек уведомлений: {e}")
        await message.answer(
            "Произошла ошибка при обновлении настроек. Попробуйте позже.",
            reply_markup=get_admin_notifications_keyboard()
        )
    finally:
        await state.clear()

@router.callback_query(F.data == "cancel_add_notification")
async def cancel_add_notification(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления уведомлений"""
    await state.clear()
    await callback.message.edit_text(
        "Добавление уведомлений отменено",
        reply_markup=get_admin_notifications_keyboard()
    )

@router.callback_query(F.data == "admin_off_notification")
async def turn_off_notifications(callback: CallbackQuery):
    """Выключение всех уведомлений"""
    try:
        await callback.message.delete()
        
        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute("""
                UPDATE bot_settings 
                SET reg_notify = 0, pay_notify = 0
            """)
            await conn.commit()
        
        message_text = (
            "✅ Все уведомления успешно отключены!\n\n"
            "<b>Текущие настройки:</b>\n"
            "<blockquote>"
            "🔔 <b>Оповещение о регистрации:</b> Выключено\n"
            "💰 <b>Оповещение об оплате:</b> Выключено\n"
            "</blockquote>"
        )
        
        await callback.message.answer(
            text=message_text,
            reply_markup=get_admin_notifications_keyboard(),
            parse_mode="HTML"
        )
        logger.info("Все уведомления отключены")
        
    except Exception as e:
        logger.error(f"Ошибка при отключении уведомлений: {e}")
        await callback.message.answer(
            "Произошла ошибка при отключении уведомлений. Попробуйте позже.",
            reply_markup=get_admin_notifications_keyboard()
        ) 