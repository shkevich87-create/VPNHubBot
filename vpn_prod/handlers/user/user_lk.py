from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from loguru import logger
import os

from handlers.database import db
from handlers.user.user_kb import get_lk_keyboard

router = Router()


async def show_lk(message: Message):
    """Показать личный кабинет."""
    try:
        lk_message = await db.get_bot_message("user_lk")
        text = lk_message['text'] if lk_message else "Личный кабинет"

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
    """Обработчик кнопки Личный кабинет."""
    try:
        await show_lk(message)
    except Exception as e:
        logger.error(f"Ошибка при переходе в личный кабинет: {e}")
        await message.answer("Произошла ошибка при открытии личного кабинета")


@router.message(Command("ref"))
@router.message(F.text == "🤝 Реферальная ссылка")
async def show_referral_link(message: Message):
    """Показать реферальную ссылку пользователя."""
    try:
        await db.register_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            bot=message.bot
        )
        stats = await db.get_referral_stats(message.from_user.id)
        bot_info = await message.bot.get_me()
        referral_link = f"https://t.me/{bot_info.username}?start=ref_{stats['referral_code']}"

        await message.answer(
            "🤝 <b>Ваша реферальная ссылка</b>\n\n"
            f"<code>{referral_link}</code>\n\n"
            "Когда приглашённый пользователь впервые оплатит подписку, "
            "мы добавим 14 дней к вашей активной подписке.\n\n"
            f"Переходов по ссылке: {stats['referral_count']}\n"
            f"Начисленных бонусов: {stats['reward_count']}",
            parse_mode="HTML",
            reply_markup=get_lk_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка при показе реферальной ссылки: {e}")
        await message.answer("Не удалось показать реферальную ссылку. Попробуйте позже.")
