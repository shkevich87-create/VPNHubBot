from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from loguru import logger
import os

from handlers.database import db
from handlers.user.user_kb import get_lk_keyboard
from handlers.commands import start_command

router = Router()

async def show_lk(message: Message):
    """Показать личный кабинет"""
    try:
        lk_message = await db.get_bot_message("user_lk")
        if not lk_message:
            text = "Личный кабинет"
        else:
            text = lk_message['text']

        keyboard = get_lk_keyboard()

        if lk_message and lk_message['image_path'] and os.path.exists(lk_message['image_path']):
            photo = FSInputFile(lk_message['image_path'])
            await message.answer_photo(
                photo=photo,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await message.answer(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        logger.info(f"Открыт личный кабинет пользователем: {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка при отображении личного кабинета: {e}")
        await message.answer("Произошла ошибка при открытии личного кабинета")

@router.message(F.text == "👤 Личный кабинет")
async def process_lk_button(message: Message):
    """Обработчик кнопки Личный кабинет"""
    try:
        await show_lk(message)
    except Exception as e:
        logger.error(f"Ошибка при переходе в личный кабинет: {e}")
        await message.answer("Произошла ошибка при открытии личного кабинета")
