from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger
from datetime import datetime

from handlers.database import db
from handlers.user.user_kb import get_user_instructions_keyboard, get_help_keyboard, get_lk_keyboard
from handlers.commands import start_command

router = Router()

@router.message(F.text == "📢 Инструкции")
async def process_instructions(message: Message):
    """Обработчик кнопки Инструкции"""
    try:
        text = (
            "<b>📱 Инструкции по настройке</b>\n\n"
            "Выберите вашу операционную систему для получения подробных инструкций:"
        )
        await message.answer(
            text=text,
            reply_markup=get_user_instructions_keyboard(),
            parse_mode="HTML"
        )
        logger.info(f"Показаны инструкции пользователю: {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при отображении инструкций: {e}")
        await message.answer("Произошла ошибка при отображении инструкций")

@router.message(F.text == "💬 Помощь")
async def process_help(message: Message):
    """Обработчик кнопки Помощь"""
    try:
        text = (
            "<b>💬 Помощь</b>\n\n"
            "Здесь вы можете найти помощь по использованию сервиса:\n\n"
            "• Объединить подписки - если у вас несколько подписок\n"
            "• Техподдержка - для связи с поддержкой"
        )
        await message.answer(
            text=text,
            reply_markup=get_help_keyboard(),
            parse_mode="HTML"
        )
        logger.info(f"Показана помощь пользователю: {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при отображении помощи: {e}")
        await message.answer("Произошла ошибка при отображении помощи")

@router.message(F.text.in_(["📱 Android", "📱 IOS", "💻 Windows", "💻 MacOS"]))
async def process_platform_instructions(message: Message):
    """Обработчик кнопок выбора платформы"""
    try:
        platform_map = {
            "📱 Android": "Android",
            "📱 IOS": "iOS",
            "💻 Windows": "Windows",
            "💻 MacOS": "MacOS"
        }
        platform = platform_map.get(message.text, "Unknown")
        
        # Рекомендуемые приложения для каждой платформы
        app_recommendations = {
            "Android": "📥 <b>Приложение:</b> V2Box (Google Play Store)",
            "iOS": "📥 <b>Приложение:</b> V2Box (App Store)",
            "Windows": "📥 <b>Приложение:</b> Hiddify (GitHub)",
            "MacOS": "📥 <b>Приложение:</b> V2Box (App Store)"
        }
        
        text = (
            f"<b>Инструкция для {platform}</b>\n\n"
            f"{app_recommendations.get(platform, '')}\n\n"
            "<blockquote>"
            "1️⃣ Скачайте и установите приложение\n"
            "2️⃣ Купите подписку и получите VLESS ключ\n"
            "3️⃣ Скопируйте ключ (нажмите на него)\n"
            "4️⃣ Откройте приложение\n"
            "5️⃣ Нажмите '+' → 'Импорт из буфера'\n"
            "6️⃣ Нажмите 'Подключить' ▶️\n"
            "</blockquote>\n\n"
            "💡 Подробные инструкции появятся после активации подписки"
        )
        
        await message.answer(
            text=text,
            reply_markup=get_user_instructions_keyboard(),
            parse_mode="HTML"
        )
        logger.info(f"Показаны инструкции для {platform} пользователю: {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при отображении инструкций для платформы: {e}")
        await message.answer("Произошла ошибка при отображении инструкций")

@router.message(F.text == "📞 Техподдержка")
async def process_support(message: Message):
    """Обработчик кнопки Техподдержка"""
    try:
        support_info = await db.get_support_info()
        
        if support_info:
            text = support_info['message']
            support_url = support_info.get('support_url', '')
            if support_url:
                text += f"\n\n📞 Ссылка на поддержку: {support_url}"
        else:
            text = (
                "<b>📞 Техподдержка</b>\n\n"
                "Если у вас возникли вопросы или проблемы, свяжитесь с нашей техподдержкой."
            )
        
        await message.answer(
            text=text,
            reply_markup=get_lk_keyboard(),
            parse_mode="HTML"
        )
        logger.info(f"Показана техподдержка пользователю: {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при отображении техподдержки: {e}")
        await message.answer("Произошла ошибка при отображении техподдержки")

@router.message(F.text == "💰 Мои платежи")
async def process_payments(message: Message):
    """Обработчик кнопки Мои платежи"""
    try:
        import aiosqlite
        
        logger.info(f"Запрос истории платежей от пользователя: {message.from_user.id}")
        
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            # Проверяем путь к БД
            logger.info(f"Путь к БД: {db.db_path}")
            
            # Получаем общую сумму платежей
            async with conn.execute(
                "SELECT SUM(price) as total, COUNT(*) as count FROM payments WHERE user_id = ?",
                (message.from_user.id,)
            ) as cursor:
                total_payments = await cursor.fetchone()
                total_amount = total_payments['total'] if total_payments and total_payments['total'] else 0
                payments_count = total_payments['count'] if total_payments else 0
            
            logger.info(f"Найдено платежей для пользователя {message.from_user.id}: {payments_count}, сумма: {total_amount}")
            
            # Получаем список всех платежей (LEFT JOIN чтобы показать даже если тариф удален)
            async with conn.execute("""
                SELECT p.*, COALESCE(t.name, 'Тариф удален') as tariff_name 
                FROM payments p
                LEFT JOIN tariff t ON p.tariff_id = t.id
                WHERE p.user_id = ?
                ORDER BY p.date DESC
            """, (message.from_user.id,)) as cursor:
                payments = await cursor.fetchall()
        
        logger.info(f"Получено записей платежей из запроса: {len(payments) if payments else 0}")
        
        if payments:
            for idx, payment in enumerate(payments):
                logger.info(f"Платеж {idx+1}: tariff_id={payment['tariff_id']}, price={payment['price']}, date={payment['date']}, tariff_name={payment['tariff_name']}")
        
        if not payments or len(payments) == 0:
            text = (
                "<b>💰 История платежей</b>\n\n"
                "У вас пока нет платежей.\n"
                "Оформите подписку, чтобы начать пользоваться нашим сервисом!"
            )
        else:
            text = (
                f"<b>💰 История платежей</b>\n\n"
                f"<b>Всего потрачено:</b> {total_amount:.2f} ₽\n"
                f"<b>Количество платежей:</b> {len(payments)}\n\n"
                "<b>Последние платежи:</b>\n"
            )
            
            # Показываем последние 10 платежей
            for payment in payments[:10]:
                text += (
                    f"\n<blockquote>"
                    f"<b>Тариф:</b> {payment['tariff_name']}\n"
                    f"<b>Сумма:</b> {payment['price']:.2f} ₽\n"
                    f"<b>Дата:</b> {payment['date']}\n"
                    f"</blockquote>"
                )
            
            if len(payments) > 10:
                text += f"\n<i>Показано 10 из {len(payments)} платежей</i>"
        
        await message.answer(
            text=text,
            reply_markup=get_lk_keyboard(),
            parse_mode="HTML"
        )
        logger.info(f"Показана история платежей пользователю: {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при отображении истории платежей: {e}")
        await message.answer("Произошла ошибка при отображении истории платежей")

@router.message(F.text == "🤝 Объеденить подписки")
async def process_merge_subscriptions(message: Message):
    """Обработчик кнопки Объединить подписки - показывает сумму продления всех подписок"""
    try:
        import aiosqlite
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        # Получаем все активные подписки пользователя с информацией о тарифах
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT 
                    us.id as sub_id,
                    us.end_date,
                    t.id as tariff_id,
                    t.name as tariff_name,
                    t.price as tariff_price,
                    t.left_day,
                    s.name as server_name
                FROM user_subscription us
                JOIN tariff t ON us.tariff_id = t.id
                JOIN server_settings s ON us.server_id = s.id
                WHERE us.user_id = ? AND us.is_active = 1
                ORDER BY us.end_date ASC
            """, (message.from_user.id,)) as cursor:
                subscriptions = await cursor.fetchall()
        
        if not subscriptions or len(subscriptions) == 0:
            text = (
                "<b>🤝 Продление подписок</b>\n\n"
                "❌ У вас нет активных подписок.\n\n"
                "Оформите подписки в разделе <b>💳 Тарифы</b>"
            )
            await message.answer(
                text=text,
                reply_markup=get_lk_keyboard(),
                parse_mode="HTML"
            )
            return
        
        # Подсчитываем общую сумму
        total_price = sum(float(sub['tariff_price']) for sub in subscriptions)
        
        # Формируем сообщение
        text = (
            "🤝 <b>Продление всех подписок</b>\n\n"
            "💡 Здесь вы можете продлить все свои активные подписки разом!\n\n"
        )
        
        # Добавляем информацию по каждой подписке
        for idx, sub in enumerate(subscriptions, 1):
            # Вычисляем оставшееся время
            try:
                end_datetime = datetime.fromisoformat(sub['end_date'].replace('Z', '+00:00'))
                now = datetime.now()
                if end_datetime.tzinfo is None:
                    end_datetime = end_datetime.replace(tzinfo=None)
                    now = datetime.now()
                else:
                    from datetime import timezone
                    now = datetime.now(timezone.utc)
                
                remaining = end_datetime - now
                days = remaining.days
                hours = remaining.seconds // 3600
                
                if days > 0:
                    remaining_str = f"{days}д. {hours}ч."
                else:
                    remaining_str = f"{hours}ч."
            except:
                remaining_str = "неизвестно"
            
            text += (
                f"<blockquote>"
                f"<b>{idx}. {sub['tariff_name']}</b>\n"
                f"🌍 Страна: {sub['server_name']}\n"
                f"⏱ Осталось: {remaining_str}\n"
                f"💰 Цена продления: {sub['tariff_price']} ₽\n"
                f"📅 Срок: {sub['left_day']} дней\n"
                f"</blockquote>\n"
            )
        
        text += (
            f"\n💵 <b>ИТОГО к оплате:</b> {total_price:.2f} ₽\n\n"
            f"📊 Всего подписок: {len(subscriptions)}\n"
            f"📅 Продление на: {subscriptions[0]['left_day']} дней каждой\n\n"
            f"⚡️ Нажмите кнопку ниже для продления всех подписок одним платежом!"
        )
        
        # Создаем кнопку для оплаты всех подписок
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"💳 Оплатить {total_price:.2f} ₽",
                    callback_data=f"pay_all_subs:{total_price}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Продлить по отдельности",
                    callback_data="renew_individual"
                )
            ]
        ])
        
        await message.answer(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        logger.info(f"Показано продление подписок пользователю: {message.from_user.id}, подписок: {len(subscriptions)}, сумма: {total_price}")
        
    except Exception as e:
        logger.error(f"Ошибка при отображении продления подписок: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await message.answer("Произошла ошибка при отображении информации о подписках")

@router.callback_query(F.data.startswith("pay_all_subs:"))
async def pay_all_subscriptions(callback: CallbackQuery, state: FSMContext):
    """Обработчик оплаты всех подписок разом"""
    try:
        import aiosqlite
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from handlers.winkpay import winkpay_manager
        
        # Получаем все активные подписки пользователя
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT 
                    us.id as sub_id,
                    t.id as tariff_id,
                    t.name as tariff_name,
                    t.price as tariff_price,
                    t.left_day,
                    s.name as server_name,
                    s.id as server_id
                FROM user_subscription us
                JOIN tariff t ON us.tariff_id = t.id
                JOIN server_settings s ON us.server_id = s.id
                WHERE us.user_id = ? AND us.is_active = 1
                ORDER BY us.end_date ASC
            """, (callback.from_user.id,)) as cursor:
                subscriptions = await cursor.fetchall()
        
        if not subscriptions or len(subscriptions) == 0:
            await callback.answer("У вас нет активных подписок", show_alert=True)
            return
        
        # Подсчитываем общую сумму
        total_price = sum(float(sub['tariff_price']) for sub in subscriptions)
        
        # Сохраняем информацию о подписках в state
        subscriptions_data = []
        for sub in subscriptions:
            subscriptions_data.append({
                'tariff_id': sub['tariff_id'],
                'tariff_name': sub['tariff_name'],
                'price': float(sub['tariff_price']),
                'server_id': sub['server_id']
            })
        
        # Сохраняем в state для последующего создания подписок
        await state.update_data(
            bulk_renewal=True,
            subscriptions_to_renew=subscriptions_data,
            total_price=total_price,
            connection_type='tcp'  # По умолчанию TCP для массового продления
        )
        
        await callback.message.delete()
        
        # Создаем платеж через WinkPay
        description = f"Продление {len(subscriptions)} подписок"
        tariff_names = ", ".join([sub['tariff_name'] for sub in subscriptions[:3]])
        if len(subscriptions) > 3:
            tariff_names += f" и еще {len(subscriptions) - 3}"
        
        payment_id, payment_info = await winkpay_manager.create_payment(
            amount=total_price,
            description=description,
            user_id=str(callback.from_user.id),
            tariff_name=tariff_names
        )
        
        if not payment_id or not payment_info:
            # Проверяем альтернативные способы оплаты
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            error_text = (
                "❌ <b>WinkPay временно недоступен</b>\n\n"
                "К сожалению, не удалось создать платеж через WinkPay.\n"
                "Возможно, нет доступных платежных реквизитов.\n\n"
                "💡 <b>Варианты решения:</b>\n"
                "1. Свяжитесь с поддержкой\n"
                "2. Продлите подписки по отдельности (другие способы оплаты могут быть доступны)\n"
                "3. Попробуйте позже"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📋 Продлить по отдельности",
                    callback_data="renew_individual"
                )],
                [InlineKeyboardButton(
                    text="📞 Техподдержка",
                    url="https://t.me/your_support"  # Замените на вашу ссылку
                )],
                [InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="start_tariffs"
                )]
            ])
            
            await callback.message.answer(
                error_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.error(f"Не удалось создать групповой платеж для пользователя {callback.from_user.id} - WinkPay недоступен")
            return
        
        # Сохраняем payment_id в state
        await state.update_data(payment_id=payment_id)
        
        # Формируем сообщение с реквизитами
        rec = (
            f"\n\n💳 <b>Реквизиты для оплаты:</b>\n"
            f"<blockquote>"
        )
        
        if payment_info.get('payment_detail_type') == 'card':
            rec += f"💳 <b>Карта:</b> <code>{payment_info.get('account_number', 'Не указано')}</code>\n"
        elif payment_info.get('payment_detail_type') == 'phone':
            rec += f"📱 <b>Телефон:</b> <code>{payment_info.get('account_number', 'Не указано')}</code>\n"
        else:
            rec += f"💰 <b>Счёт:</b> <code>{payment_info.get('account_number', 'Не указано')}</code>\n"
        
        rec += (
            f"👤 <b>Имя получателя:</b> {payment_info.get('holder_name', 'Не указано')}\n"
            f"🏦 <b>Банк:</b> {payment_info.get('bank_name', 'Не указано')}\n"
            f"💵 <b>Сумма:</b> <code>{int(total_price)}</code> ₽\n"
            f"</blockquote>\n\n"
            f"⚠️ <b>Важно:</b> Переведите точную сумму <code>{int(total_price)}</code> ₽\n"
            f"После оплаты нажмите кнопку «Проверить платеж»"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Проверить платеж",
                callback_data=f"check_bulk_payment:{payment_id}"
            )],
            [InlineKeyboardButton(
                text="🔄 Создать новый платеж",
                callback_data="recreate_bulk_payment"
            )],
            [InlineKeyboardButton(
                text="🔙 Отмена",
                callback_data="start_tariffs"
            )]
        ])
        
        message_text = (
            f"💳 <b>Оплата {len(subscriptions)} подписок</b>\n\n"
            f"<blockquote>"
            f"💵 <b>Сумма:</b> {total_price:.2f} ₽\n"
            f"📦 <b>Подписок:</b> {len(subscriptions)}\n"
            f"</blockquote>"
            + rec
        )
        
        await callback.message.answer(
            text=message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        logger.info(f"Создан групповой платеж {payment_id} для пользователя {callback.from_user.id}, подписок: {len(subscriptions)}, сумма: {total_price}")
        
    except Exception as e:
        logger.error(f"Ошибка при создании группового платежа: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await callback.answer("Произошла ошибка при создании платежа", show_alert=True)

@router.callback_query(F.data.startswith("check_bulk_payment:"))
async def check_bulk_payment(callback: CallbackQuery, state: FSMContext):
    """Проверка группового платежа и создание всех подписок"""
    try:
        import aiosqlite
        from asyncio import Lock
        from handlers.winkpay import winkpay_manager
        from handlers.buy_subscribe import subscription_manager
        
        payment_id = callback.data.split(":")[1]
        
        # Защита от повторных нажатий
        if not hasattr(check_bulk_payment, 'locks'):
            check_bulk_payment.locks = {}
        
        if payment_id not in check_bulk_payment.locks:
            check_bulk_payment.locks[payment_id] = Lock()
        
        if check_bulk_payment.locks[payment_id].locked():
            await callback.answer("Платеж уже обрабатывается, подождите...", show_alert=True)
            return
        
        async with check_bulk_payment.locks[payment_id]:
            # Проверяем что платеж еще не обработан
            async with aiosqlite.connect(db.db_path) as conn:
                async with conn.execute(
                    'SELECT id FROM user_subscription WHERE payment_id = ? AND user_id = ? LIMIT 1',
                    (payment_id, callback.from_user.id)
                ) as cursor:
                    if await cursor.fetchone():
                        await callback.answer("Этот платеж уже был обработан!", show_alert=True)
                        return
            
            # Проверяем статус платежа в WinkPay
            is_paid = await winkpay_manager.check_payment(payment_id, bot=callback.bot)
            
            if not is_paid:
                await callback.answer(
                    "Платеж еще не оплачен. Проверьте еще раз через минуту.",
                    show_alert=True
                )
                return
            
            # Получаем данные о подписках из state
            data = await state.get_data()
            subscriptions_data = data.get('subscriptions_to_renew', [])
            connection_type = data.get('connection_type', 'tcp')
            
            if not subscriptions_data:
                await callback.answer("Ошибка: данные о подписках не найдены", show_alert=True)
                logger.error(f"Нет данных о подписках для группового платежа {payment_id}")
                return
            
            await callback.message.delete()
            await callback.message.answer("⏳ Создаем подписки, пожалуйста подождите...")
            
            # Создаем все подписки
            created_count = 0
            failed_count = 0
            created_subscriptions = []
            
            for sub_data in subscriptions_data:
                try:
                    subscription = await subscription_manager.create_subscription(
                        user_id=callback.from_user.id,
                        tariff_id=sub_data['tariff_id'],
                        payment_id=payment_id,
                        bot=callback.bot,
                        connection_type=connection_type
                    )
                    
                    if subscription:
                        created_count += 1
                        created_subscriptions.append({
                            'name': sub_data['tariff_name'],
                            'vless': subscription.get('config_link') or subscription.get('subscription_url') or subscription['vless'],
                            'end_date': subscription['end_date']
                        })
                        logger.info(f"Создана подписка {sub_data['tariff_name']} для платежа {payment_id}")
                    else:
                        failed_count += 1
                        logger.error(f"Не удалось создать подписку {sub_data['tariff_name']} для платежа {payment_id}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Ошибка при создании подписки {sub_data['tariff_name']}: {e}")
            
            # Записываем платежи в историю
            async with aiosqlite.connect(db.db_path) as conn:
                for sub_data in subscriptions_data:
                    await conn.execute("""
                        INSERT INTO payments (user_id, tariff_id, price)
                        VALUES (?, ?, ?)
                    """, (
                        callback.from_user.id,
                        sub_data['tariff_id'],
                        sub_data['price']
                    ))
                await conn.commit()
            
            # Формируем сообщение о результате
            if created_count > 0:
                success_message = (
                    f"✅ <b>Подписки успешно созданы!</b>\n\n"
                    f"📦 <b>Создано подписок:</b> {created_count}"
                )
                
                if failed_count > 0:
                    success_message += f"\n⚠️ <b>Не удалось создать:</b> {failed_count}"
                
                success_message += "\n\n<b>Ваши новые подписки:</b>\n"
                
                for idx, sub in enumerate(created_subscriptions, 1):
                    success_message += (
                        f"\n<blockquote>"
                        f"<b>{idx}. {sub['name']}</b>\n"
                        f"🔑 <code>{sub['vless']}</code>\n"
                        f"📅 Действует до: {sub['end_date'][:10]}\n"
                        f"</blockquote>"
                    )
                
                success_message += "\n\n💡 Скопируйте ключи и добавьте их в ваше VPN приложение"
                
                from handlers.user.user_kb import get_success_by_keyboard
                await callback.message.answer(
                    text=success_message,
                    reply_markup=get_success_by_keyboard(),
                    parse_mode="HTML"
                )
                
                logger.info(f"Групповой платеж {payment_id} обработан: создано {created_count}, ошибок {failed_count}")
            else:
                await callback.message.answer(
                    "❌ Не удалось создать подписки. Обратитесь в поддержку, ваш платеж был получен."
                )
                logger.error(f"Групповой платеж {payment_id} оплачен, но не удалось создать ни одной подписки")
            
            await state.clear()
            
    except Exception as e:
        logger.error(f"Ошибка при проверке группового платежа: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await callback.answer("Произошла ошибка при обработке платежа", show_alert=True)

@router.callback_query(F.data == "recreate_bulk_payment")
async def recreate_bulk_payment(callback: CallbackQuery, state: FSMContext):
    """Пересоздание группового платежа с новыми реквизитами"""
    try:
        import aiosqlite
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from handlers.winkpay import winkpay_manager
        
        # Получаем данные из state
        data = await state.get_data()
        subscriptions_data = data.get('subscriptions_to_renew', [])
        
        if not subscriptions_data:
            # Если данных нет в state, получаем заново из БД
            async with aiosqlite.connect(db.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("""
                    SELECT 
                        us.id as sub_id,
                        t.id as tariff_id,
                        t.name as tariff_name,
                        t.price as tariff_price,
                        t.left_day,
                        s.name as server_name,
                        s.id as server_id
                    FROM user_subscription us
                    JOIN tariff t ON us.tariff_id = t.id
                    JOIN server_settings s ON us.server_id = s.id
                    WHERE us.user_id = ? AND us.is_active = 1
                    ORDER BY us.end_date ASC
                """, (callback.from_user.id,)) as cursor:
                    subscriptions = await cursor.fetchall()
            
            if not subscriptions:
                await callback.answer("У вас нет активных подписок", show_alert=True)
                return
            
            # Пересоздаем subscriptions_data
            subscriptions_data = []
            for sub in subscriptions:
                subscriptions_data.append({
                    'tariff_id': sub['tariff_id'],
                    'tariff_name': sub['tariff_name'],
                    'price': float(sub['tariff_price']),
                    'server_id': sub['server_id']
                })
        
        # Подсчитываем общую сумму
        total_price = sum(sub['price'] for sub in subscriptions_data)
        
        await callback.message.delete()
        await callback.message.answer("⏳ Создаем новый платеж...")
        
        # Создаем новый платеж
        description = f"Продление {len(subscriptions_data)} подписок"
        tariff_names = ", ".join([sub['tariff_name'] for sub in subscriptions_data[:3]])
        if len(subscriptions_data) > 3:
            tariff_names += f" и еще {len(subscriptions_data) - 3}"
        
        payment_id, payment_info = await winkpay_manager.create_payment(
            amount=total_price,
            description=description,
            user_id=str(callback.from_user.id),
            tariff_name=tariff_names
        )
        
        if not payment_id or not payment_info:
            # WinkPay недоступен
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            error_text = (
                "❌ <b>WinkPay временно недоступен</b>\n\n"
                "Не удалось пересоздать платеж.\n\n"
                "💡 Попробуйте:\n"
                "1. Продлить подписки по отдельности\n"
                "2. Связаться с поддержкой\n"
                "3. Попробовать позже"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📋 Продлить по отдельности",
                    callback_data="renew_individual"
                )],
                [InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="start_tariffs"
                )]
            ])
            
            await callback.message.answer(
                error_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.error(f"Не удалось пересоздать групповой платеж для пользователя {callback.from_user.id} - WinkPay недоступен")
            return
        
        # Обновляем state с новым payment_id
        await state.update_data(
            bulk_renewal=True,
            subscriptions_to_renew=subscriptions_data,
            total_price=total_price,
            connection_type='tcp',
            payment_id=payment_id
        )
        
        # Формируем сообщение с новыми реквизитами
        rec = (
            f"\n\n💳 <b>Новые реквизиты для оплаты:</b>\n"
            f"<blockquote>"
        )
        
        if payment_info.get('payment_detail_type') == 'card':
            rec += f"💳 <b>Карта:</b> <code>{payment_info.get('account_number', 'Не указано')}</code>\n"
        elif payment_info.get('payment_detail_type') == 'phone':
            rec += f"📱 <b>Телефон:</b> <code>{payment_info.get('account_number', 'Не указано')}</code>\n"
        else:
            rec += f"💰 <b>Счёт:</b> <code>{payment_info.get('account_number', 'Не указано')}</code>\n"
        
        rec += (
            f"👤 <b>Имя получателя:</b> {payment_info.get('holder_name', 'Не указано')}\n"
            f"🏦 <b>Банк:</b> {payment_info.get('bank_name', 'Не указано')}\n"
            f"💵 <b>Сумма:</b> <code>{int(total_price)}</code> ₽\n"
            f"</blockquote>\n\n"
            f"⚠️ <b>Важно:</b> Переведите точную сумму <code>{int(total_price)}</code> ₽\n"
            f"После оплаты нажмите кнопку «Проверить платеж»"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Проверить платеж",
                callback_data=f"check_bulk_payment:{payment_id}"
            )],
            [InlineKeyboardButton(
                text="🔄 Создать новый платеж",
                callback_data="recreate_bulk_payment"
            )],
            [InlineKeyboardButton(
                text="🔙 Отмена",
                callback_data="start_tariffs"
            )]
        ])
        
        message_text = (
            f"🔄 <b>Новый платеж создан!</b>\n\n"
            f"💳 <b>Оплата {len(subscriptions_data)} подписок</b>\n\n"
            f"<blockquote>"
            f"💵 <b>Сумма:</b> {total_price:.2f} ₽\n"
            f"📦 <b>Подписок:</b> {len(subscriptions_data)}\n"
            f"</blockquote>"
            + rec
        )
        
        await callback.message.answer(
            text=message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        logger.info(f"Пересоздан групповой платеж {payment_id} для пользователя {callback.from_user.id}, подписок: {len(subscriptions_data)}, сумма: {total_price}")
        
    except Exception as e:
        logger.error(f"Ошибка при пересоздании группового платежа: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await callback.answer("Произошла ошибка при создании нового платежа", show_alert=True)

@router.callback_query(F.data == "renew_individual")
async def renew_individual_subscriptions(callback: CallbackQuery):
    """Показать список подписок для индивидуального продления"""
    try:
        import aiosqlite
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        # Получаем все активные подписки
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT 
                    us.id as sub_id,
                    us.end_date,
                    t.id as tariff_id,
                    t.name as tariff_name,
                    t.price as tariff_price,
                    s.name as server_name
                FROM user_subscription us
                JOIN tariff t ON us.tariff_id = t.id
                JOIN server_settings s ON us.server_id = s.id
                WHERE us.user_id = ? AND us.is_active = 1
                ORDER BY us.end_date ASC
            """, (callback.from_user.id,)) as cursor:
                subscriptions = await cursor.fetchall()
        
        if not subscriptions:
            await callback.answer("У вас нет активных подписок", show_alert=True)
            return
        
        await callback.message.delete()
        
        text = (
            "📋 <b>Выберите подписку для продления:</b>\n\n"
            "Нажмите на кнопку с нужной подпиской"
        )
        
        # Создаем кнопки для каждой подписки
        keyboard_buttons = []
        for sub in subscriptions:
            button_text = f"{sub['tariff_name']} ({sub['server_name']}) - {sub['tariff_price']} ₽"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"select_tariff:{sub['tariff_id']}"
                )
            ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.answer(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        logger.info(f"Показан список подписок для индивидуального продления пользователю {callback.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при показе подписок для продления: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)
