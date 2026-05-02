from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
import db_compat as aiosqlite
from loguru import logger

from handlers.database import db
from handlers.admin.admin_kb import get_admin_keyboard, get_admin_users_keyboard

router = Router()

@router.callback_query(F.data == "admin_show_users")
async def process_show_users(callback: CallbackQuery):
    """Обработчик просмотра списка пользователей"""
    try:
        await callback.message.delete()

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            async with conn.execute("SELECT COUNT(*) as count FROM user") as cursor:
                total_users = (await cursor.fetchone())['count']
            
            async with conn.execute("""
                SELECT username, date, trial_period, is_enable
                FROM user 
                ORDER BY date DESC
                LIMIT 5
            """) as cursor:
                users = await cursor.fetchall()

        if not users:
            message_text = "👥 Список пользователей\n\nПользователей пока нет"
        else:
            message_text = "👥 <b>Список зарегистрированных пользователей:</b>\n\n"
            for user in users:
                username = f"@{user['username']}" if user['username'] else "Без username"
                
                trial_status = "Да" if user['trial_period'] else "Нет"
                
                is_enable = "Активен" if user['is_enable'] else "Заблокирован"
                
                message_text += (
                    f"<blockquote>"
                    f"👤 Пользователь: {username}\n"
                    f"📅 Дата регистрации: {user['date']}\n"
                    f"🎁 Использовал триал: <code>{trial_status}</code>\n"
                    f"🔒 Статус блокировки: <code>{is_enable}</code>\n"
                    "</blockquote>"
                )
            
            message_text += f"\nВсего пользователей: {total_users}"

        keyboard = get_admin_users_keyboard()
        
        if total_users > 5:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="Далее 🔜", callback_data="users_page:1")
            ])

        await callback.message.answer(
            text=message_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}")
        await callback.message.answer(
            "Произошла ошибка при получении списка пользователей",
            reply_markup=get_admin_keyboard()
        )

@router.callback_query(F.data.startswith("users_page:"))
async def process_users_page(callback: CallbackQuery):
    try:
        page = int(callback.data.split(':')[1])
        offset = page * 5

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            async with conn.execute("SELECT COUNT(*) as count FROM user") as cursor:
                total_users = (await cursor.fetchone())['count']
            
            async with conn.execute("""
                SELECT username, date, trial_period, is_enable
                FROM user 
                ORDER BY date DESC
                LIMIT 5 OFFSET ?
            """, (offset,)) as cursor:
                users = await cursor.fetchall()

        message_text = "👥 <b>Список зарегистрированных пользователей:</b>\n\n"
        for user in users:
            username = f"@{user['username']}" if user['username'] else "Без username"
            trial_status = "Да" if user['trial_period'] else "Нет"
            is_enable = "Активен" if user['is_enable'] else "Заблокирован"
            
            message_text += (
                f"<blockquote>"
                f"👤 Пользователь: {username}\n"
                f"📅 Дата регистрации: {user['date']}\n"
                f"🎁 Использовал триал: <code>{trial_status}</code>\n"
                f"🔒 Статус блокировки: <code>{is_enable}</code>\n"
                "</blockquote>"
            )
        
        message_text += f"\nВсего пользователей: {total_users}"

        keyboard = get_admin_users_keyboard()
        nav_buttons = []

        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"users_page:{page-1}")
            )

        if (offset + 5) < total_users:
            nav_buttons.append(
                InlineKeyboardButton(text="Далее 🔜", callback_data=f"users_page:{page+1}")
            )

        if nav_buttons:
            keyboard.inline_keyboard.append(nav_buttons)

        await callback.message.edit_text(
            text=message_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Ошибка при пагинации пользователей: {e}")
        await callback.answer("Ошибка при получении списка пользователей", show_alert=True)

@router.callback_query(F.data == "users_back_to_admin")
async def process_back_to_admin(callback: CallbackQuery):
    """Обработчик кнопки возврата в админ-панель"""
    try:
        await callback.message.delete()
        admin_message = await db.get_bot_message("admin")
        text = admin_message['text'] if admin_message else "Панель администратора"
        
        await callback.message.answer(
            text=text,
            reply_markup=get_admin_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка при возврате в админ-панель: {e}")
        await callback.message.answer(
            "Произошла ошибка при возврате в админ-панель",
            reply_markup=get_admin_keyboard()
        ) 