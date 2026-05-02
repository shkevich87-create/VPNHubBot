from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from loguru import logger
import db_compat as aiosqlite

from handlers.database import db
from handlers.admin.admin_kb import get_servers_keyboard

router = Router()

class ServerDeleteStates(StatesGroup):
    waiting_for_url = State()
    waiting_for_name = State()
    confirm_delete = State()

@router.callback_query(F.data == "delete_server")
async def start_server_delete(callback: CallbackQuery, state: FSMContext):
    """Начало процесса удаления сервера"""
    try:
        if not await db.is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав для выполнения этого действия")
            return

        await callback.message.delete()
        
        await callback.message.answer(
            "🗑 Введите URL сервера для удаления:\n"
            "Пример: https://3xui.example.com"
        )
        
        await state.set_state(ServerDeleteStates.waiting_for_url)
        
    except Exception as e:
        logger.error(f"Ошибка при начале удаления сервера: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=get_servers_keyboard()
        )

@router.message(ServerDeleteStates.waiting_for_url)
async def process_delete_url(message: Message, state: FSMContext):
    """Обработка введенного URL и запрос подтверждения"""
    try:
        url = message.text.strip()
        
        async with aiosqlite.connect(db.db_path) as conn:
            async with conn.execute(
                "SELECT id, url, name FROM server_settings WHERE url = ?",
                (url,)
            ) as cursor:
                server = await cursor.fetchone()
                
                if not server:
                    await message.answer(
                        "❌ Сервер с таким URL не найден в системе.",
                        reply_markup=get_servers_keyboard()
                    )
                    await state.clear()
                    return

            server_id = server[0]
            server_name = server[2]

            # Подсчитываем связанные записи
            async with conn.execute(
                "SELECT COUNT(*) FROM user_subscription WHERE server_id = ?",
                (server_id,)
            ) as cursor:
                subs_count = (await cursor.fetchone())[0]

            async with conn.execute(
                "SELECT COUNT(*) FROM tariff WHERE server_id = ?",
                (server_id,)
            ) as cursor:
                tariff_count = (await cursor.fetchone())[0]
        
        # Сохраняем данные в состояние
        await state.update_data(
            server_id=server_id,
            server_url=url,
            server_name=server_name,
            subs_count=subs_count,
            tariff_count=tariff_count
        )
        
        # Формируем предупреждение
        warning_msg = f"⚠️ <b>ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ</b>\n\n"
        warning_msg += f"Вы действительно хотите удалить сервер?\n\n"
        warning_msg += f"<b>Сервер:</b> {server_name}\n"
        warning_msg += f"<b>URL:</b> {url}\n\n"
        
        if subs_count > 0 or tariff_count > 0:
            warning_msg += f"⚠️ <b>Будет удалено:</b>\n"
            if tariff_count > 0:
                warning_msg += f"• Тарифов: {tariff_count}\n"
            if subs_count > 0:
                warning_msg += f"• Активных подписок: {subs_count}\n"
            warning_msg += f"\n❗️ <b>Это действие необратимо!</b>"
        
        # Создаем кнопки подтверждения
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete_yes"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="confirm_delete_no")
            ]
        ])
        
        await message.answer(
            warning_msg,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(ServerDeleteStates.confirm_delete)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке удаления сервера: {e}")
        await message.answer(
            f"Произошла ошибка: {str(e)}",
            reply_markup=get_servers_keyboard()
        )
        await state.clear()

@router.message(ServerDeleteStates.waiting_for_name)
async def process_delete_server(message: Message, state: FSMContext):
    """Обработка введенного названия сервера и запрос подтверждения"""
    try:
        server_name = message.text.strip()
        
        async with aiosqlite.connect(db.db_path) as conn:
            async with conn.execute(
                "SELECT id, name, url FROM server_settings WHERE name = ?",
                (server_name,)
            ) as cursor:
                server = await cursor.fetchone()
                
            if not server:
                await message.answer(
                    "❌ Сервер с таким названием не найден.",
                    reply_markup=get_servers_keyboard()
                )
                await state.clear()
                return

            server_id = server[0]
            server_url = server[2]
            
            # Подсчитываем связанные записи
            async with conn.execute(
                "SELECT COUNT(*) FROM user_subscription WHERE server_id = ?",
                (server_id,)
            ) as cursor:
                subs_count = (await cursor.fetchone())[0]

            async with conn.execute(
                "SELECT COUNT(*) FROM tariff WHERE server_id = ?",
                (server_id,)
            ) as cursor:
                tariff_count = (await cursor.fetchone())[0]
        
        # Сохраняем данные в состояние
        await state.update_data(
            server_id=server_id,
            server_url=server_url,
            server_name=server_name,
            subs_count=subs_count,
            tariff_count=tariff_count
        )
        
        # Формируем предупреждение
        warning_msg = f"⚠️ <b>ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ</b>\n\n"
        warning_msg += f"Вы действительно хотите удалить сервер?\n\n"
        warning_msg += f"<b>Сервер:</b> {server_name}\n"
        warning_msg += f"<b>URL:</b> {server_url}\n\n"
        
        if subs_count > 0 or tariff_count > 0:
            warning_msg += f"⚠️ <b>Будет удалено:</b>\n"
            if tariff_count > 0:
                warning_msg += f"• Тарифов: {tariff_count}\n"
            if subs_count > 0:
                warning_msg += f"• Активных подписок: {subs_count}\n"
            warning_msg += f"\n❗️ <b>Это действие необратимо!</b>"
        
        # Создаем кнопки подтверждения
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete_yes"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="confirm_delete_no")
            ]
        ])
        
        await message.answer(
            warning_msg,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(ServerDeleteStates.confirm_delete)
        
    except Exception as e:
        logger.error(f"Ошибка при удалении сервера: {e}")
        await message.answer(
            f"Произошла ошибка при удалении сервера: {str(e)}",
            reply_markup=get_servers_keyboard()
        )
        await state.clear()

@router.callback_query(F.data == "confirm_delete_yes", ServerDeleteStates.confirm_delete)
async def confirm_delete_yes(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления сервера"""
    try:
        await callback.message.delete()
        
        # Получаем сохраненные данные
        data = await state.get_data()
        server_id = data['server_id']
        server_name = data['server_name']
        server_url = data['server_url']
        subs_count = data['subs_count']
        tariff_count = data['tariff_count']
        
        # Удаляем сервер и связанные данные
        async with aiosqlite.connect(db.db_path) as conn:
            # Отключаем проверку внешних ключей
            await conn.execute("PRAGMA foreign_keys = OFF")
            
            # Удаляем связанные записи
            await conn.execute(
                "DELETE FROM user_subscription WHERE server_id = ?",
                (server_id,)
            )
            
            await conn.execute(
                "DELETE FROM trial_settings WHERE server_id = ?",
                (server_id,)
            )
            
            await conn.execute(
                "DELETE FROM tariff WHERE server_id = ?",
                (server_id,)
            )
            
            # Удаляем сам сервер
            await conn.execute(
                "DELETE FROM server_settings WHERE id = ?",
                (server_id,)
            )
            
            await conn.commit()
            await conn.execute("PRAGMA foreign_keys = ON")
        
        success_message = f"✅ Сервер '{server_name}' успешно удален из системы"
        if subs_count > 0 or tariff_count > 0:
            success_message += f"\n\n🗑 Также удалено:\n"
            if tariff_count > 0:
                success_message += f"• Тарифов: {tariff_count}\n"
            if subs_count > 0:
                success_message += f"• Подписок пользователей: {subs_count}"
        
        await callback.message.answer(
            success_message,
            reply_markup=get_servers_keyboard()
        )
        logger.info(f"Удален сервер: {server_name} (URL: {server_url}), тарифов: {tariff_count}, подписок: {subs_count}")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении сервера: {e}")
        await callback.message.answer(
            f"Произошла ошибка при удалении сервера: {str(e)}",
            reply_markup=get_servers_keyboard()
        )
    finally:
        await state.clear()

@router.callback_query(F.data == "confirm_delete_no", ServerDeleteStates.confirm_delete)
async def confirm_delete_no(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления сервера"""
    try:
        await callback.message.delete()
        await callback.message.answer(
            "❌ Удаление сервера отменено.",
            reply_markup=get_servers_keyboard()
        )
        logger.info(f"Удаление сервера отменено пользователем: {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при отмене удаления: {e}")
    finally:
        await state.clear() 