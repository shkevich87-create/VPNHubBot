from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import db_compat as aiosqlite
from loguru import logger

from handlers.database import db
from handlers.admin.admin_kb import get_admin_show_trial_keyboard

router = Router()

class TrialDeleteStates(StatesGroup):
    waiting_for_id = State()

def get_cancel_keyboard():
    """Создание клавиатуры с кнопкой отмены"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Отмена", callback_data="cancel_delete_trial")
    return keyboard.as_markup()

@router.callback_query(F.data == "admin_delete_trial")
async def start_delete_trial(callback: CallbackQuery, state: FSMContext):
    """Начало процесса удаления пробного тарифа"""
    try:
        await callback.message.delete()
        
        await callback.message.answer(
            "⚠️ <b>Внимание!</b> Вы собираетесь удалить пробный тарифный план.\n"
            "🚫 Пользователи больше не смогут получать доступ к пробной подписке.\n\n"
            "🔢 Если вы уверены, введите ID:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(TrialDeleteStates.waiting_for_id)
        
    except Exception as e:
        logger.error(f"Ошибка при начале удаления пробного тарифа: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=get_admin_show_trial_keyboard()
        )

@router.message(TrialDeleteStates.waiting_for_id)
async def process_delete_trial(message: Message, state: FSMContext):
    """Обработка введенного ID и удаление тарифа"""
    try:
        trial_id = int(message.text.strip())
        
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            async with conn.execute(
                "SELECT name FROM trial_settings WHERE id = ? AND is_enable = 1",
                (trial_id,)
            ) as cursor:
                trial = await cursor.fetchone()
                
            if not trial:
                await message.answer(
                    "❌ Активный пробный тариф с таким ID не найден.",
                    reply_markup=get_admin_show_trial_keyboard()
                )
                await state.clear()
                return
                
            await conn.execute(
                "UPDATE trial_settings SET is_enable = 0 WHERE id = ?",
                (trial_id,)
            )
            await conn.commit()
            
        await message.answer(
            f"✅ Пробный тариф '{trial['name']}' успешно удален.",
            reply_markup=get_admin_show_trial_keyboard()
        )
        logger.info(f"Удален пробный тариф: {trial['name']} (ID: {trial_id})")
        
    except ValueError:
        await message.answer(
            "Пожалуйста, введите корректный ID (целое число)"
        )
        return
    except Exception as e:
        logger.error(f"Ошибка при удалении пробного тарифа: {e}")
        await message.answer(
            "Произошла ошибка при удалении тарифа. Попробуйте позже.",
            reply_markup=get_admin_show_trial_keyboard()
        )
    finally:
        await state.clear()

@router.callback_query(F.data == "cancel_delete_trial")
async def cancel_delete_trial(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления пробного тарифа"""
    await state.clear()
    await callback.message.edit_text(
        "Удаление пробного тарифа отменено",
        reply_markup=get_admin_show_trial_keyboard()
    ) 