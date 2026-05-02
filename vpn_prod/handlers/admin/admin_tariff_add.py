from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from loguru import logger
import db_compat as aiosqlite

from handlers.database import db
from handlers.admin.admin_kb import get_admin_keyboard
from handlers.admin.admin_tariff import get_admin_show_tariff_keyboard

router = Router()

class TariffAddStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_days = State()
    waiting_for_max_devices = State()
    waiting_for_traffic_limit = State()

def get_servers_keyboard():
    """Создание клавиатуры со списком серверов"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Отмена", callback_data="cancel_add_tariff")
    return keyboard.as_markup()

@router.callback_query(F.data == "add_tariff")
async def start_add_tariff(callback: CallbackQuery):
    """Начало процесса добавления тарифа"""
    try:
        await callback.message.delete()
        
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT id, name FROM server_settings 
                WHERE is_enable = 1
                ORDER BY name
            """) as cursor:
                servers = await cursor.fetchall()

        if not servers:
            await callback.message.answer(
                "Нет доступных серверов для добавления тарифа",
                reply_markup=get_admin_show_tariff_keyboard()
            )
            return

        keyboard = InlineKeyboardBuilder()
        for server in servers:
            keyboard.button(
                text=server['name'],
                callback_data=f"select_server:{server['id']}"
            )
        keyboard.button(text="🔙 Отмена", callback_data="cancel_add_tariff")
        keyboard.adjust(1)

        await callback.message.answer(
            "Выберите сервер для добавления тарифа:",
            reply_markup=keyboard.as_markup()
        )

    except Exception as e:
        logger.error(f"Ошибка при начале добавления тарифа: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=get_admin_show_tariff_keyboard()
        )

@router.callback_query(F.data.startswith("select_server:"))
async def process_server_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора сервера"""
    try:
        server_id = int(callback.data.split(':')[1])
        
        await state.update_data(server_id=server_id)
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Отмена", callback_data="cancel_add_tariff")
        
        await callback.message.edit_text(
            "Введите наименование тарифного плана:",
            reply_markup=keyboard.as_markup()
        )
        await state.set_state(TariffAddStates.waiting_for_name)
        
    except Exception as e:
        logger.error(f"Ошибка при выборе сервера: {e}")
        await callback.message.edit_text(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=get_admin_show_tariff_keyboard()
        )

@router.message(TariffAddStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """Обработка ввода названия тарифа"""
    await state.update_data(name=message.text.strip())
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Отмена", callback_data="cancel_add_tariff")
    
    await message.answer(
        "Введите описание:",
        reply_markup=keyboard.as_markup()
    )
    await state.set_state(TariffAddStates.waiting_for_description)

@router.message(TariffAddStates.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    """Обработка ввода описания"""
    await state.update_data(description=message.text.strip())
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Отмена", callback_data="cancel_add_tariff")
    
    await message.answer(
        "Введите цену:",
        reply_markup=keyboard.as_markup()
    )
    await state.set_state(TariffAddStates.waiting_for_price)

@router.message(TariffAddStates.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    """Обработка ввода цены"""
    try:
        price = float(message.text.strip())
        await state.update_data(price=price)
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Отмена", callback_data="cancel_add_tariff")
        
        await message.answer(
            "Введите количество дней в тарифном плане:",
            reply_markup=keyboard.as_markup()
        )
        await state.set_state(TariffAddStates.waiting_for_days)
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число для цены:")

@router.message(TariffAddStates.waiting_for_days)
async def process_days(message: Message, state: FSMContext):
    """Обработка ввода количества дней"""
    try:
        days = int(message.text.strip())
        await state.update_data(left_day=days)
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Отмена", callback_data="cancel_add_tariff")
        
        await message.answer(
            "Введите максимальное количество устройств для этого тарифа:\n\n"
            "1 - только одно устройство (базовый)\n"
            "2 - два устройства\n"
            "3 - три устройства (семейный)\n"
            "5 - пять устройств (премиум)\n"
            "0 - без ограничений",
            reply_markup=keyboard.as_markup()
        )
        await state.set_state(TariffAddStates.waiting_for_max_devices)
        
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число дней:")

@router.message(TariffAddStates.waiting_for_max_devices)
async def process_max_devices(message: Message, state: FSMContext):
    """Обработка ввода количества устройств"""
    try:
        max_devices = int(message.text.strip())
        
        if max_devices < 0:
            await message.answer("Количество устройств не может быть отрицательным. Введите число от 0 (без ограничений) или больше:")
            return
        
        await state.update_data(max_devices=max_devices)
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Отмена", callback_data="cancel_add_tariff")
        
        await message.answer(
            "Введите лимит трафика в ГБ:\n\n"
            "10 - 10 гигабайт\n"
            "50 - 50 гигабайт\n"
            "100 - 100 гигабайт\n"
            "500 - 500 гигабайт\n"
            "0 - безлимитный трафик",
            reply_markup=keyboard.as_markup()
        )
        await state.set_state(TariffAddStates.waiting_for_traffic_limit)
        
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число устройств (0 или больше):")

@router.message(TariffAddStates.waiting_for_traffic_limit)
async def process_traffic_limit(message: Message, state: FSMContext):
    """Обработка ввода лимита трафика и сохранение тарифа"""
    try:
        traffic_limit_gb = int(message.text.strip())
        
        if traffic_limit_gb < 0:
            await message.answer("Лимит трафика не может быть отрицательным. Введите число от 0 (безлимит) или больше:")
            return
        
        data = await state.get_data()
        
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT name FROM server_settings WHERE id = ?",
                (data['server_id'],)
            ) as cursor:
                server = await cursor.fetchone()

            await conn.execute("""
                INSERT INTO tariff 
                (name, description, price, left_day, server_id, is_enable, max_devices, traffic_limit_gb)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """, (data['name'], data['description'], data['price'], data['left_day'], 
                  data['server_id'], data['max_devices'], traffic_limit_gb))
            await conn.commit()

        devices_text = f"{data['max_devices']} устройств" if data['max_devices'] > 0 else "без ограничений"
        traffic_text = f"{traffic_limit_gb} ГБ" if traffic_limit_gb > 0 else "безлимит"
        
        await message.answer(
            f"✅ Тарифный план успешно добавлен!\n\n"
            f"<b>Название:</b> {data['name']}\n"
            f"<b>Описание:</b> {data['description']}\n"
            f"<b>Цена:</b> {data['price']} ₽\n"
            f"<b>Срок:</b> {data['left_day']} дней\n"
            f"<b>Сервер:</b> {server['name']}\n"
            f"<b>Устройств:</b> {devices_text}\n"
            f"<b>Трафик:</b> {traffic_text}",
            reply_markup=get_admin_show_tariff_keyboard(),
            parse_mode="HTML"
        )
        logger.info(f"Добавлен тариф: {data['name']}, цена: {data['price']}, дней: {data['left_day']}, устройств: {data['max_devices']}, трафик: {traffic_limit_gb} ГБ")
        
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число для лимита трафика (0 или больше):")
    except Exception as e:
        logger.error(f"Ошибка при сохранении тарифа: {e}")
        await message.answer(
            "Произошла ошибка при сохранении тарифа. Попробуйте позже.",
            reply_markup=get_admin_show_tariff_keyboard()
        )
    finally:
        await state.clear()

@router.callback_query(F.data == "cancel_add_tariff")
async def cancel_add_tariff(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления тарифа"""
    await state.clear()
    await callback.message.edit_text(
        "Добавление тарифа отменено",
        reply_markup=get_admin_show_tariff_keyboard()
    ) 