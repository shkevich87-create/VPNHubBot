from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from loguru import logger
import os

from handlers.database import db
from handlers.user.user_kb import get_trial_keyboard, get_trial_vless_keyboard, get_no_subscriptions_keyboard
from handlers.commands import start_command
from handlers.x_ui import xui_manager
from handlers.buy_subscribe import subscription_manager

router = Router()

async def get_active_trial_settings():
    """Получение активных настроек пробного периода"""
    async with db.connect() as conn:
        async with conn.execute(
            'SELECT * FROM trial_settings WHERE is_enable = 1 LIMIT 1'
        ) as cursor:
            trial = await cursor.fetchone()
            return dict(trial) if trial else None

@router.message(F.text == "🎁 Пробный период")
async def process_trial_button(message: Message):
    """Обработчик кнопки Пробный период"""
    try:
        user = await db.get_user(message.from_user.id)
        if not user:
            logger.error(f"Пользователь не найден: {message.from_user.id}")
            await message.answer("Произошла ошибка. Попробуйте позже.")
            return

        if user.get('trial_period'):
            text = "Вы уже пользовались пробным периодом, пожалуйста купите подписку на сервис"
            await message.answer(
                text=text,
                reply_markup=get_trial_keyboard(show_connect=False)
            )
            logger.info(f"Пользователь уже использовал пробный период: {message.from_user.id}")
            return

        trial_settings = await db.get_active_trial_settings()
        if not trial_settings:
            text = "К сожалению сейчас пробный период недоступен"
            await message.answer(
                text=text,
                reply_markup=get_trial_keyboard(show_connect=False)
            )
            logger.info("Пробный период недоступен")
            return

        base_text = (
            "<b>Пробный период!</b>\n\n"
            "<blockquote>"
            f"<b>Наименование:</b> {trial_settings.get('name', 'Не указано')}\n"
            f"<b>Пробных дней:</b> {trial_settings.get('left_day', 0)}\n"
            f"<b>Сервер:</b> {trial_settings.get('server_name', 'Не указан')}\n"
            "</blockquote>\n"
        )

        message_data = await db.get_bot_message('trial_success')
        
        if message_data and message_data['image_path'] and os.path.exists(message_data['image_path']):
            full_text = base_text + message_data['text']
            await message.answer_photo(
                photo=FSInputFile(message_data['image_path']),
                caption=full_text,
                reply_markup=get_trial_keyboard(show_connect=True),
                parse_mode="HTML"
            )
        else:
            text = base_text + "Хотите попробовать самый лучший сервис в мире? Жми кнопку подключить"
            await message.answer(
                text=text,
                reply_markup=get_trial_keyboard(show_connect=True),
                parse_mode="HTML"
            )

        logger.info(f"Показано предложение пробного периода пользователю: {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки пробного периода: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(F.text == "🔗 Подключить")
async def process_trial_connect(message: Message):
    """Обработчик кнопки Подключить пробный период"""
    try:
        user = await db.get_user(message.from_user.id)
        if not user:
            logger.error(f"Пользователь не найден: {message.from_user.id}")
            await message.answer("Произошла ошибка. Попробуйте позже.")
            return

        if user.get('trial_period'):
            text = "Вы уже пользовались пробным периодом, пожалуйста купите подписку на сервис"
            await message.answer(
                text=text,
                reply_markup=get_trial_keyboard(show_connect=False)
            )
            return

        trial_settings = await db.get_active_trial_settings()
        if not trial_settings:
            await message.answer(
                "К сожалению сейчас пробный период недоступен",
                reply_markup=get_trial_keyboard(show_connect=False)
            )
            return

        server_settings = await db.get_server_settings(trial_settings['server_id'])
        if not server_settings:
            await message.answer(
                "Ошибка при получении настроек сервера",
                reply_markup=get_trial_keyboard(show_connect=False)
            )
            return

        subscription = await subscription_manager.create_subscription(
            user_id=message.from_user.id,
            tariff_id=trial_settings['id'],
            is_trial=True,
            connection_type='tcp'  # Для пробного периода используем TCP по умолчанию
        )

        if not subscription:
            logger.error("Ошибка при создании подписки в базе данных")
            await message.answer(
                "Произошла ошибка при активации пробного периода. Попробуйте позже.",
                reply_markup=get_trial_keyboard(show_connect=False)
            )
            return

        vless_link = subscription.get('config_link') or subscription.get('subscription_url') or subscription['vless']

        await db.update_user_trial_status(message.from_user.id, True)

        text = (
            "🎉 <b>Поздравляем! Пробный период активирован!</b>\n\n"
            f"<blockquote>"
            f"⏱ <b>Срок действия:</b> {trial_settings['left_day']} дней\n"
            f"</blockquote>\n\n"
            "🔑 <b>Ваш VLESS ключ:</b>\n"
            f"<blockquote>"
            f"<code>{vless_link}</code>\n"
            f"</blockquote>\n\n"
            "📲 <b>Как подключить:</b>\n"
            "1. Скопируйте ключ выше (нажмите на него)\n"
            "2. Откройте VPN приложение:\n"
            "   • Android/iOS/Mac: V2Box\n"
            "   • Windows: Hiddify\n"
            "3. Нажмите '+' → 'Импорт из буфера'\n"
            "4. Нажмите 'Подключить' ▶️\n\n"
            "⚠️ <b>Важно:</b>\n"
            "• Конфиг работает только на 1 устройстве\n"
            "• Подробные инструкции: 📢 Инструкции"
        )
        
        await message.answer(
            text=text,
            reply_markup=get_no_subscriptions_keyboard(),
            parse_mode="HTML"
        )
        logger.info(f"Активирован пробный период для пользователя: {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка при активации пробного периода: {e}")
        await message.answer(
            "Произошла ошибка при активации пробного периода. Попробуйте позже.",
            reply_markup=get_trial_keyboard(show_connect=False)
        )
