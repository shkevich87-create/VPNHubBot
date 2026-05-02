from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from loguru import logger
import aiosqlite

from handlers.database import db
from handlers.admin.admin_kb import get_admin_keyboard, get_servers_keyboard
from handlers.admin.check_server import check_all_servers
from handlers.commands import start_command

router = Router()

@router.message(Command("admin"))
async def admin_command(message: Message):
    """Обработчик команды /admin"""
    try:
        if not await db.is_admin(message.from_user.id):
            logger.warning(f"Попытка доступа к админ-панели от неавторизованного пользователя: {message.from_user.id}")
            return
        
        admin_message = await db.get_bot_message("admin")
        if not admin_message:
            text = "Панель администратора"
        else:
            text = admin_message['text']
        
        await message.answer(
            text=text,
            reply_markup=get_admin_keyboard()
        )
        logger.info(f"Открыта админ-панель пользователем: {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке команды admin: {e}")
        await message.answer("Произошла ошибка при выполнении команды")

@router.message(F.text == "⚙️ Админ-панель")
async def admin_panel_button(message: Message):
    """Обработчик reply кнопки Админ-панель"""
    try:
        if not await db.is_admin(message.from_user.id):
            logger.warning(f"Попытка доступа к админ-панели от неавторизованного пользователя: {message.from_user.id}")
            return
        
        admin_message = await db.get_bot_message("admin")
        if not admin_message:
            text = "Панель администратора"
        else:
            text = admin_message['text']
        
        await message.answer(
            text=text,
            reply_markup=get_admin_keyboard()
        )
        logger.info(f"Открыта админ-панель через reply кнопку пользователем: {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки админ-панели: {e}")
        await message.answer("Произошла ошибка при выполнении команды")

async def format_server_list(servers: list) -> str:
    """Форматирование списка серверов для отображения"""
    result = "<b>Список серверов:</b>\n"
    
    for server in servers:
        result += "<blockquote>"
        result += f"<b>Наименование:</b> {server['name']}\n"
        result += f"<b>IP:</b> {server['ip'] if server['ip'] else 'Не указан'}\n"
        result += f"<b>Статус:</b> {'Доступен для регистрации' if server['is_enable'] else 'Временно недоступен'}\n"
        if server.get('available'):
            result += f"<b>Задержка:</b> {server['delay']}ms\n"
            result += f"<b>Код ответа:</b> {'ОК' if server.get('status_code') == 404 else server.get('status_code', 'Неизвестно')}\n"
        else:
            result += "<b>Сервер недоступен (нет ответа)</b>\n"
        result += "</blockquote>\n"
    
    return result   

@router.callback_query(F.data == "admin_show_servers")
async def process_servers_button(callback: CallbackQuery):
    """Обработчик кнопки Сервера"""
    try:
        if not await db.is_admin(callback.from_user.id):
            logger.warning(f"Попытка использования админ-кнопок от неавторизованного пользователя: {callback.from_user.id}")
            await callback.answer("У вас нет прав для выполнения этого действия")
            return
        
        servers = await db.get_all_servers()
        
        if not servers:
            await callback.message.edit_text(
                "Серверы не найдены в базе данных",
                reply_markup=get_servers_keyboard()
            )
            return
        
        servers_with_status = await check_all_servers(servers)
        
        message_text = await format_server_list(servers_with_status)
        await callback.message.edit_text(
            message_text,
            reply_markup=get_servers_keyboard(),
            parse_mode="HTML"
        )
        
        logger.info(f"Отображен список серверов пользователю: {callback.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки Сервера: {e}")
        await callback.answer("Произошла ошибка при получении списка серверов")

@router.callback_query(F.data == "servers_back_to_admin")
async def process_back_to_admin(callback: CallbackQuery):
    """Обработчик кнопки Назад в списке серверов"""
    try:
        if not await db.is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав для выполнения этого действия")
            return
            
        admin_message = await db.get_bot_message("admin")
        text = admin_message['text'] if admin_message else "Панель администратора"
        
        await callback.message.edit_text(
            text=text,
            reply_markup=get_admin_keyboard()
        )
        logger.info(f"Возврат в админ-панель пользователем: {callback.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при возврате в админ-панель: {e}")
        await callback.answer("Произошла ошибка при возврате в админ-панель")

@router.callback_query(F.data == "admin_back_to_start")
async def process_back_to_start(callback: CallbackQuery):
    """Обработчик кнопки Вернуться в главное меню"""
    try:
        await callback.message.delete()
        await start_command(callback.message)
        logger.info(f"Возврат в главное меню пользователем: {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при возврате в главное меню: {e}")
        await callback.answer("Произошла ошибка при возврате в главное меню")


@router.callback_query(F.data == "admin_show_payments")
async def process_show_payments(callback: CallbackQuery):
    """Обработчик просмотра статистики платежей"""
    try:
        await callback.message.delete()

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            async with conn.execute(
                'SELECT SUM(price) as total FROM payments'
            ) as cursor:
                total = await cursor.fetchone()
                total_amount = total['total'] if total['total'] else 0

            async with conn.execute("""
                SELECT u.username, u.telegram_id, COUNT(*) as purchase_count
                FROM payments p
                JOIN user u ON p.user_id = u.telegram_id
                GROUP BY p.user_id
                ORDER BY purchase_count DESC
                LIMIT 1
            """) as cursor:
                top_buyer = await cursor.fetchone()
                if top_buyer:
                    buyer_info = f"@{top_buyer['username']}" if top_buyer['username'] else f"ID: {top_buyer['telegram_id']}"
                    purchase_count = top_buyer['purchase_count']
                    buyer_text = f"{buyer_info}"
                else:
                    buyer_text = "Нет данных"

            async with conn.execute("""
                SELECT p.price, p.date as payment_date, u.username, u.telegram_id
                FROM payments p
                JOIN user u ON p.user_id = u.telegram_id
                ORDER BY p.date DESC
                LIMIT 1
            """) as cursor:
                last_payment = await cursor.fetchone()

            async with conn.execute("""
                SELECT t.name, COUNT(*) as count
                FROM user_subscription us
                JOIN tariff t ON us.tariff_id = t.id
                GROUP BY us.tariff_id
                ORDER BY count DESC
                LIMIT 1
            """) as cursor:
                popular_tariff = await cursor.fetchone()

            async with conn.execute("""
                SELECT COUNT(*) as total_subscriptions
                FROM user_subscription
            """) as cursor:
                total_subs = await cursor.fetchone()
                total_subscriptions = total_subs['total_subscriptions'] if total_subs else 0

            async with conn.execute("""
                SELECT COUNT(*) as total_users
                FROM user
            """) as cursor:
                total_users = await cursor.fetchone()
                total_users = total_users['total_users'] if total_users else 0

        if last_payment:
            message_text = (
                f"<blockquote>"
                f"💰 <b>Всего заработано: {total_amount:.2f} руб.</b>\n"
                f"👤 <b>Всего пользователей: {total_users}</b>\n\n"
                f"👑 Самый активный покупатель: <b>{buyer_text}</b>\n"
                f"🔄 Последний поступивший платеж: <b>{last_payment['price']:.2f} руб.</b>\n"
                f"📅 Дата: <b>{last_payment['payment_date']}</b>\n\n"
                f"💵 Всего кодов на сумму: <b>{await db.get_active_codes_sum():.2f} ₽</b>\n"
                f"📈 Оплачено кодами: <b>{await db.get_used_codes_sum():.2f} ₽</b>\n\n"
                f"🎁 Самый популярный тариф: <b>{popular_tariff['name'] if popular_tariff else 'Нет данных'}</b>\n"
                f"🛒 Всего куплено подписок: <b>{total_subscriptions}</b>\n"
                f"</blockquote>"
            )
        else:
            message_text = (
                "📊 *Статистика платежей*\n\n"
                "Платежей пока нет"
            )

        await callback.message.answer(
            text=message_text,
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )

    except Exception as e:
        logger.error(f"Ошибка при получении статистики платежей: {e}")
        await callback.message.answer(
            "Произошла ошибка при получении статистики платежей",
            reply_markup=get_admin_keyboard()
        )

@router.callback_query(F.data == "servers_update")
async def update_servers_list(callback: CallbackQuery):
    """Обработчик кнопки обновления списка серверов"""
    try:
        servers = await db.get_all_servers()
        
        if not servers:
            await callback.answer("Серверы не найдены в базе данных")
            return
        
        servers = await check_all_servers(servers)
        
        message_text = await format_server_list(servers)
        
        await callback.message.edit_text(
            text=message_text,
            reply_markup=get_servers_keyboard(),
            parse_mode="HTML"
        )
        
        await callback.answer("Список серверов обновлен!")
        logger.info(f"Список серверов обновлен пользователем: {callback.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка при обновлении списка серверов: {e}")
        await callback.answer(
            "Произошла ошибка при обновлении списка серверов",
            show_alert=True
        )