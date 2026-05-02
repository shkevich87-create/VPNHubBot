from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import db_compat as aiosqlite
from loguru import logger
from datetime import datetime, timedelta

from handlers.database import db
from handlers.admin.admin_kb import get_admin_show_promo_tariff_keyboard
from handlers.x_ui import xui_manager

router = Router()

class PromoSendStates(StatesGroup):
    waiting_for_username = State()

def get_cancel_keyboard():
    """Создание клавиатуры с кнопкой отмены"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Отмена", callback_data="cancel_send_promo")
    return keyboard.as_markup()

async def get_promo_tariffs_keyboard():
    """Создание клавиатуры с промо-тарифами"""
    keyboard = InlineKeyboardBuilder()
    
    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("""
            SELECT tp.*, s.name as server_name 
            FROM tariff_promo tp
            JOIN server_settings s ON tp.server_id = s.id
            WHERE tp.is_enable = 1
        """) as cursor:
            tariffs = await cursor.fetchall()
            
    for tariff in tariffs:
        keyboard.button(
            text=f"{tariff['name']} ({tariff['server_name']})",
            callback_data=f"select_promo_tariff:{tariff['id']}"
        )
    
    keyboard.button(text="🔙 Отмена", callback_data="cancel_send_promo")
    keyboard.adjust(1)
    return keyboard.as_markup()

@router.callback_query(F.data == "admin_send_promo_tariff")
async def start_send_promo(callback: CallbackQuery):
    """Начало процесса отправки промо-тарифа"""
    try:
        await callback.message.delete()
        await callback.message.answer(
            "Выберите промо тариф для отправки:",
            reply_markup=await get_promo_tariffs_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка при старте отправки промо-тарифа: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=get_admin_show_promo_tariff_keyboard()
        )

@router.callback_query(F.data.startswith("select_promo_tariff:"))
async def process_tariff_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора промо-тарифа"""
    try:
        tariff_id = int(callback.data.split(":")[1])
        
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT tp.*, s.name as server_name, s.* 
                FROM tariff_promo tp
                JOIN server_settings s ON tp.server_id = s.id
                WHERE tp.id = ?
            """, (tariff_id,)) as cursor:
                tariff = await cursor.fetchone()

        if not tariff:
            await callback.message.edit_text(
                "Тариф не найден",
                reply_markup=get_admin_show_promo_tariff_keyboard()
            )
            return

        await state.update_data(tariff=dict(tariff))
        
        message_text = (
            "Вы выбрали промо тариф\n"
            "<blockquote>"
            f"Наименование: {tariff['name']}\n"
            f"Описание: {tariff['description']}\n"
            f"Промо дней: {tariff['left_day']}\n"
            f"Страна: {tariff['server_name']}\n"
            "</blockquote>\n\n"
            "Введите имя пользователя для отправки промо тарифа:"
        )
        
        await callback.message.edit_text(
            message_text,
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(PromoSendStates.waiting_for_username)
        
    except Exception as e:
        logger.error(f"Ошибка при выборе промо-тарифа: {e}")
        await callback.message.edit_text(
            "Произошла ошибка при выборе тарифа",
            reply_markup=get_admin_show_promo_tariff_keyboard()
        )

@router.message(PromoSendStates.waiting_for_username)
async def process_username(message: Message, state: FSMContext):
    """Обработка ввода имени пользователя"""
    try:
        username = message.text.lstrip('@')
        data = await state.get_data()
        tariff = data['tariff']
        
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM user WHERE username = ? AND is_enable = 1",
                (username,)
            ) as cursor:
                user = await cursor.fetchone()

            if not user:
                await message.answer(
                    "❌ Пользователь не найден",
                    reply_markup=get_admin_show_promo_tariff_keyboard()
                )
                await state.clear()
                return

            async with conn.execute(
                "SELECT * FROM server_settings WHERE id = ?",
                (tariff['server_id'],)
            ) as cursor:
                server = await cursor.fetchone()
                server = dict(server)

        end_date = datetime.now() + timedelta(days=tariff['left_day'])
        client_config = await xui_manager.create_trial_user(server, tariff, user['telegram_id'], connection_type='tcp')
        
        if not client_config:
            await message.answer(
                "❌ Ошибка при создании конфигурации",
                reply_markup=get_admin_show_promo_tariff_keyboard()
            )
            await state.clear()
            return

        if isinstance(client_config, str):
            vless_link = client_config
            subscription_url = None
            client_uuid = None
            client_email = None
            sub_id = None
        else:
            vless_link = client_config.get('vless')
            subscription_url = client_config.get('subscription_url')
            client_uuid = client_config.get('client_uuid')
            client_email = client_config.get('client_email')
            sub_id = client_config.get('sub_id')

        config_link = subscription_url or vless_link

        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute("""
                INSERT INTO user_subscription 
                (user_id, tariff_id, server_id, end_date, vless, is_active,
                 client_uuid, client_email, sub_id, subscription_url)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """, (user['telegram_id'], tariff['id'], tariff['server_id'], 
                  end_date.strftime('%Y-%m-%d %H:%M:%S'), vless_link,
                  client_uuid, client_email, sub_id, subscription_url))
            await conn.commit()

        admin_message = (
            "✅ Промо-тариф успешно отправлен!\n\n"
            f"👤 Пользователь: @{username}\n"
            f"🎁 Тариф: {tariff['name']}\n"
            f"📅 Дата окончания: {end_date.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"🔗 Конфигурация:\n<code>{config_link}</code>"
        )
        
        await message.answer(
            admin_message,
            reply_markup=get_admin_show_promo_tariff_keyboard(),
            parse_mode="HTML"
        )

        user_message = (
            f"🎁 Вам предоставлен промо-тариф!\n\n"
            f"Тариф: {tariff['name']}\n"
            f"Срок действия: {tariff['left_day']} дней\n"
            f"Дата окончания: {end_date.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Ваша конфигурация:\n<code>{config_link}</code>"
        )
        
        await message.bot.send_message(
            chat_id=user['telegram_id'],
            text=user_message,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка при отправке промо-тарифа: {e}")
        await message.answer(
            "Произошла ошибка при отправке промо-тарифа",
            reply_markup=get_admin_show_promo_tariff_keyboard()
        )
    finally:
        await state.clear()

@router.callback_query(F.data == "cancel_send_promo")
async def cancel_send_promo(callback: CallbackQuery, state: FSMContext):
    """Отмена отправки промо-тарифа"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Отправка промо-тарифа отменена",
        reply_markup=get_admin_show_promo_tariff_keyboard()
    ) 
