from aiogram import Router, F, types
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asyncio import Lock
from handlers.database import db
from loguru import logger
import db_compat as aiosqlite
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from handlers.promocode import promo_manager
from handlers.winkpay import winkpay_manager
from handlers.buy_subscribe import subscription_manager
from handlers.user.user_kb import get_trial_vless_keyboard, get_success_by_keyboard, get_start_keyboard
import os
from aiogram.types import FSInputFile

router = Router()

class PromoCodeStates(StatesGroup):
    waiting_for_promo = State()

class TariffStates(StatesGroup):
    selecting_connection_type = State()

# защищаемся от двойных нажатий "Проверить платеж"
payment_locks: dict[str, Lock] = {}


# =========================
# СТАРТОВЫЙ ЭКРАН ТАРИФОВ
# =========================
async def show_tariffs_message(message: Message):
    """Общая функция для показа тарифов"""
    try:
        tariffs = await db.get_active_tariffs()
        if not tariffs:
            await message.answer("В данный момент нет доступных тарифов.")
            return

        tariffs_text = "🚀 Выберите сервер, чтобы посмотреть доступные тарифы"
        '''for tariff in tariffs:
            tariffs_text += (
                f"<blockquote>"
                f"<b>Тарифный план:</b> {tariff['name']}\n"
                f"<b>Описание:</b> {tariff['description']}\n"
                f"<b>Стоимость:</b> {tariff['price']} руб.\n"
                f"<b>Страна:</b> {tariff['server_name']}\n"
                f"<b>Срок действия:</b> {tariff['left_day']} дней\n"
                f"</blockquote>\n"
            )'''

        # вывести список серверов для выбора
        keyboard = InlineKeyboardBuilder()
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT DISTINCT s.id, s.name 
                FROM server_settings s
                JOIN tariff t ON s.id = t.server_id
                WHERE t.is_enable = 1
            """) as cursor:
                servers = await cursor.fetchall()

        for server in servers:
            keyboard.button(
                text=f"{server['name']}",
                callback_data=f"user_select_server:{server['id']}"
            )
        keyboard.button(text="🔙 Назад", callback_data="tariff_back_to_start")
        keyboard.adjust(2, 1)

        message_data = await db.get_bot_message('tariff_message')
        if message_data and message_data['image_path'] and os.path.exists(message_data['image_path']):
            full_text = (message_data['text'] or "") + "\n\n" + tariffs_text
            await message.answer_photo(
                photo=FSInputFile(message_data['image_path']),
                caption=full_text,
                reply_markup=keyboard.as_markup(),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                text=tariffs_text,
                reply_markup=keyboard.as_markup(),
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Ошибка при отображении тарифов: {e}")
        await message.answer("Произошла ошибка при загрузке тарифов. Попробуйте позже.")

@router.message(F.text == "💳 Тарифы")
async def start_tariffs_message(message: Message):
    """Обработчик reply кнопки Тарифы"""
    await show_tariffs_message(message)

@router.callback_query(F.data == "start_tariffs")
async def start_tariffs(callback: CallbackQuery):
    try:
        await callback.message.delete()
        await show_tariffs_message(callback.message)
    except Exception as e:
        logger.error(f"Ошибка при обработке callback тарифов: {e}")
    finally:
        await callback.answer()

# =========================
# ВЫБОР ТАРИФА
# =========================
@router.callback_query(F.data.startswith("select_tariff:"))
async def process_tariff_selection(callback: CallbackQuery):
    """Обработчик выбора тарифа"""
    try:
        await callback.message.delete()

        tariff_id = int(callback.data.split(":")[1])

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT t.*, s.name as server_name 
                FROM tariff t 
                INNER JOIN server_settings s ON t.server_id = s.id 
                WHERE t.id = ? AND t.is_enable = 1
            """, (tariff_id,)) as cursor:
                tariff = await cursor.fetchone()

        if not tariff:
            await callback.message.answer("Выбранный тариф недоступен.")
            return

        message_text = (
            f"Выберите, как хотите оплатить:\n"
            f"<blockquote>"
            f"<b>Тарифный план:</b> {tariff['name']}\n"
            f"<b>Описание:</b> {tariff['description']}\n"
            f"<b>Стоимость:</b> {tariff['price']} руб.\n"
            f"<b>Страна:</b> {tariff['server_name']}\n"
            f"<b>Сроком на:</b> {tariff['left_day']} дней.\n"
            f"💡 Можно применить промокод, чтобы сэкономить.\n"
            f"</blockquote>\n"
        )

        keyboard = InlineKeyboardBuilder()

        # WinkPay — создаем счет с реквизитами по нажатию кнопки
        keyboard.button(text="Оплата СБП/Карта", callback_data=f"create_invoice:{tariff_id}")

        # Оплата USDT TRC20
        is_crypto_active = await db.is_crypto_enabled()
        if is_crypto_active:
            keyboard.button(text="Оплата Криптой", callback_data=f"apply_crypto_payments:{tariff_id}")

        keyboard.button(text="Промокод", callback_data=f"apply_promo_code:{tariff_id}")
        keyboard.button(text="Код оплаты", callback_data=f"apply_payments_code:{tariff_id}")
        keyboard.button(text="🔙 Отмена", callback_data="tariff_back_to_start")
        keyboard.adjust(2, 1)

        await callback.message.answer(
            text=message_text,
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка при выборе тарифа: {e}")
        await callback.message.answer("Произошла ошибка при выборе тарифа. Попробуйте позже.")
    finally:
        await callback.answer()

# =========================
# СОЗДАНИЕ СЧЁТА (WINKPAY)
# =========================
# =========================
# СОЗДАНИЕ СЧЁТА (WINKPAY)
# =========================
@router.callback_query(F.data.startswith("create_invoice:"))
async def process_create_invoice(callback: CallbackQuery, state: FSMContext):
    """Создание сделки WinkPay и вывод реквизитов (с ретраем)"""
    try:
        parts = callback.data.split(":")
        tariff_id = int(parts[1])
        promo_code = parts[2] if len(parts) > 2 and parts[2] else None

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT t.*, s.name as server_name 
                FROM tariff t 
                INNER JOIN server_settings s ON t.server_id = s.id 
                WHERE t.id = ? AND t.is_enable = 1
            """, (tariff_id,)) as cursor:
                tariff = await cursor.fetchone()

        if not tariff:
            await callback.answer("Тариф недоступен")
            return

        price = float(tariff['price'])
        if promo_code:
            async with aiosqlite.connect(db.db_path) as conn:
                async with conn.execute("""
                    SELECT percentage 
                    FROM promocodes 
                    WHERE promocod = ? AND is_enable = 1 
                    AND activation_total < activation_limit
                """, (promo_code,)) as cursor:
                    promo = await cursor.fetchone()
                    if promo:
                        percentage = float(promo[0])
                        discount = price * (percentage / 100.0)
                        price = price - discount

        payment_id, payment_info = await winkpay_manager.create_payment(
            amount=price,
            description=f"Оплата тарифа {tariff['name']}",
            user_id=str(callback.from_user.id),
            tariff_name=tariff['name']
        )

        # ---- РЕТРАЙ: если WinkPay не выдал реквизиты ----
        if not payment_id or not payment_info:
            human_msg = None
            if isinstance(payment_info, dict):
                human_msg = payment_info.get("message")

            keyboard = InlineKeyboardBuilder()
            # повтор: создаём новый счёт для того же тарифа (+ промокод, если был)
            retry_cb = f"create_invoice:{tariff_id}"
            if promo_code:
                retry_cb += f":{promo_code}"
            keyboard.button(text="🔁 Создать новый счёт", callback_data=retry_cb)

            # можно добавить альтернативу (если используешь CryptoBot и т.п.)
            # keyboard.button(text="🪙 Оплатить через CryptoBot", callback_data=f"apply_crypto_payments:{tariff_id}")

            keyboard.button(text="🔙 Назад", callback_data="tariff_back_to_start")
            keyboard.adjust(1, 1)

            await callback.message.answer(
                human_msg or "Временная недоступность реквизитов. Нажми «Создать новый счёт», чтобы попробовать ещё раз.",
                reply_markup=keyboard.as_markup()
            )
            return
        # -----------------------------------------------

        await state.update_data(payment_id=payment_id, tariff_id=tariff_id)

        # Текст с реквизитами
        rec = (
            "\n\n<b>Реквизиты для оплаты</b>\n"
            f"Метод: {payment_info.get('gateway_name','')}\n"
            f"Тип: {payment_info.get('detail_type','')}\n"
            f"Получатель: {payment_info.get('initials','')}\n"
            f"Деталь: <code>{payment_info.get('detail','')}</code>\n"
            f"Сумма к оплате: {payment_info.get('amount','')} {payment_info.get('currency','').upper()}"
        )

        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🕵️‍♂️ Проверить платеж", callback_data=f"check_payment:{payment_id}")
        keyboard.button(text="🔙 Отмена", callback_data="tariff_back_to_start")
        keyboard.adjust(2, 1)

        await callback.message.delete()
        await callback.message.answer(
            "💡 <b>Счёт создан</b> — оплатите по реквизитам ниже и нажмите «Проверить платеж»."
            + rec,
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка при создании счета: {e}")
        await callback.message.answer("Произошла ошибка при создании счета. Попробуйте позже.")


# =========================
# ПРОВЕРКА ПЛАТЕЖА
# =========================
@router.callback_query(F.data.startswith("check_payment:"))
async def check_payment(callback: CallbackQuery, state: FSMContext):
    """Проверка статуса сделки WinkPay"""
    payment_id = callback.data.split(":")[1]
    try:
        if payment_id not in payment_locks:
            payment_locks[payment_id] = Lock()

        if not payment_locks[payment_id].locked():
            async with payment_locks[payment_id]:
                # защита от повторной активации
                async with aiosqlite.connect(db.db_path) as conn:
                    async with conn.execute(
                        'SELECT id FROM user_subscription WHERE payment_id = ? AND user_id = ?',
                        (payment_id, callback.from_user.id)
                    ) as cursor:
                        if await cursor.fetchone():
                            await callback.answer("Платеж уже был обработан и подписка активирована!", show_alert=True)
                            return

                is_paid = await winkpay_manager.check_payment(payment_id, bot=callback.bot)
                if not is_paid:
                    await callback.answer("Платеж еще не оплачен. Попробуйте проверить позже.")
                    return

                data = await state.get_data()
                tariff_id = data.get('tariff_id')
                connection_type = data.get('connection_type', 'tcp')

                # если применяли промокод — прогоняем пост-применение (не критично, но сохраним поведение)
                if 'promo_code' in data:
                    success, _, _ = await promo_manager.apply_promo_code(
                        data['promo_code'],
                        data['original_price']
                    )
                    if not success:
                        logger.warning("Промокод не применился постфактум (не критично).")

                # создаём подписку + выдаём конфиг/ссылку
                subscription = await subscription_manager.create_subscription(
                    user_id=callback.from_user.id,
                    tariff_id=tariff_id,
                    payment_id=payment_id,
                    bot=callback.bot,
                    connection_type=connection_type
                )

                if not subscription:
                    await callback.message.answer("Ошибка при активации подписки. Обратитесь в поддержку.")
                    return

                # логируем платёж
                async with aiosqlite.connect(db.db_path) as conn:
                    async with conn.execute(
                        'SELECT price FROM tariff WHERE id = ?',
                        (tariff_id,)
                    ) as cursor:
                        tariff = await cursor.fetchone()
                        if tariff:
                            await conn.execute("""
                                INSERT INTO payments (user_id, tariff_id, price)
                                VALUES (?, ?, ?)
                            """, (
                                callback.from_user.id,
                                tariff_id,
                                tariff[0]
                            ))
                            await conn.commit()

                await db.apply_referral_reward(
                    referred_user_id=callback.from_user.id,
                    payment_id=payment_id,
                    bot=callback.bot
                )

                # Получаем информацию о max_devices из тарифа
                async with aiosqlite.connect(db.db_path) as conn:
                    conn.row_factory = aiosqlite.Row
                    async with conn.execute(
                        'SELECT max_devices FROM tariff WHERE id = ?',
                        (tariff_id,)
                    ) as cursor:
                        tariff_info = await cursor.fetchone()
                        max_devices = tariff_info['max_devices'] if tariff_info else 1
                
                devices_text = f"{max_devices} устройств" if max_devices > 1 else "1 устройстве"
                if max_devices == 0:
                    devices_text = "без ограничений"

                config_link = subscription.get('config_link') or subscription.get('subscription_url') or subscription['vless']
                
                message_text = (
                    "🎉 <b>Поздравляем! Ваша подписка активирована!</b>\n\n"
                    f"<blockquote>"
                    f"📦 <b>Тариф:</b> {subscription['tariff']['name']}\n"
                    f"📅 <b>Действует до:</b> {subscription['end_date'].strftime('%d.%m.%Y')}\n"
                    f"</blockquote>\n\n"
                    "🔑 <b>Ваш VLESS ключ:</b>\n"
                    "<blockquote>"
                    f"<code>{config_link}</code>\n"
                    "</blockquote>\n\n"
                    "📲 <b>Как подключить:</b>\n"
                    "1. Скопируйте ключ выше (нажмите на него)\n"
                    "2. Откройте VPN приложение:\n"
                    "   • Android/iOS/Mac: V2Box\n"
                    "   • Windows: Hiddify\n"
                    "3. Нажмите '+' → 'Импорт из буфера'\n"
                    "4. Нажмите 'Подключить' ▶️\n\n"
                    "⚠️ <b>Важно:</b>\n"
                    f"• Этот конфиг работает на {devices_text}\n"
                    "• Подробные инструкции: 📢 Инструкции"
                )

                await callback.message.delete()
                await callback.message.answer(
                    text=message_text,
                    reply_markup=get_success_by_keyboard(),
                    parse_mode="HTML"
                )

                await state.clear()
        else:
            await callback.answer("Платеж обрабатывается, пожалуйста подождите...", show_alert=True)
            return
    except Exception as e:
        logger.error(f"Ошибка при проверке платежа: {e}")
        await callback.answer("Произошла ошибка при проверке платежа", show_alert=True)
    finally:
        if payment_id in payment_locks and not payment_locks[payment_id].locked():
            del payment_locks[payment_id]

# =========================
# НАЗАД В МЕНЮ
# =========================
@router.callback_query(F.data == "tariff_back_to_start")
async def process_back_to_start(callback: CallbackQuery, state: FSMContext):
    """Кнопка Назад"""
    try:
        # Очищаем состояние FSM
        await state.clear()
        
        from handlers.commands import start_command
        await callback.message.delete()
        await start_command(callback.message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при возврате в главное меню: {e}")
        await callback.answer("Произошла ошибка при возврате в главное меню")

# =========================
# ПРОМОКОД (кнопка)
# =========================
@router.callback_query(F.data.startswith("apply_promo_code:"))
async def process_promo_code_button(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия 'Применить промокод'"""
    try:
        tariff_id = int(callback.data.split(":")[1])
        await state.update_data(tariff_id=tariff_id)

        await callback.message.delete()

        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Отмена", callback_data=f"select_tariff:{tariff_id}")

        await callback.message.answer(
            "Отправь мне промокод и я пересчитаю тарифный план с учетом скидки:",
            reply_markup=keyboard.as_markup()
        )

        await state.set_state(PromoCodeStates.waiting_for_promo)

    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки промокода: {e}")
        await callback.message.answer("Произошла ошибка. Попробуйте позже.")

# =========================
# ПРОМОКОД (ввод кода)
# =========================
@router.message(PromoCodeStates.waiting_for_promo)
async def process_promo_code(message: types.Message, state: FSMContext):
    """Обработка ввода промокода и создание счета WinkPay со скидкой"""
    try:
        is_valid, info_text, percentage = await promo_manager.check_promo_code(message.text)

        if not is_valid:
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="🔙 Назад", callback_data="start_tariffs")
            await message.answer(
                info_text,
                reply_markup=keyboard.as_markup()
            )
            await state.clear()
            return

        data = await state.get_data()

        # получаем тариф
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT t.*, s.name as server_name 
                FROM tariff t
                JOIN server_settings s ON t.server_id = s.id
                WHERE t.id = ?
            """, (data['tariff_id'],)) as cursor:
                tariff = await cursor.fetchone()
                tariff = dict(tariff) if tariff else None

        if not tariff:
            await message.answer("Тариф не найден")
            await state.clear()
            return

        discount = float(tariff['price']) * (percentage / 100.0)
        new_price = float(tariff['price']) - discount

        await state.update_data(
            promo_code=message.text,
            original_price=float(tariff['price']),
            discount_price=new_price
        )

        payment_id, payment_info = await winkpay_manager.create_payment(
            amount=float(new_price),
            description=f"Оплата тарифа {tariff['name']} со скидкой {percentage}%",
            user_id=str(message.from_user.id),
            tariff_name=tariff['name']
        )

        if not payment_id or not payment_info:
            await message.answer("Ошибка при создании платежа. Попробуйте позже.")
            return

        # текст счета + реквизиты
        text = (
            f"Вы выбрали:\n"
            f"<blockquote>"
            f"<b>Тарифный план:</b> {tariff['name']}\n"
            f"<b>Описание:</b> {tariff['description']}\n"
            f"<b>Страна:</b> {tariff['server_name']}\n"
            f"<b>Сроком на:</b> {tariff['left_day']} дней.\n"
            f"<b>Базовая стоимость:</b> {tariff['price']} руб.\n"
            f"<b>Стоимость со скидкой:</b> {new_price:.2f} руб.\n"
            f"</blockquote>\n"
            f"Промокод успешно применен! Скидка: {percentage}%"
        )
        rec = (
            "\n\n<b>Реквизиты для оплаты</b>\n"
            f"Метод: {payment_info.get('gateway_name','')}\n"
            f"Тип: {payment_info.get('detail_type','')}\n"
            f"Получатель: {payment_info.get('initials','')}\n"
            f"Деталь: <code>{payment_info.get('detail','')}</code>\n"
            f"Сумма к оплате: {payment_info.get('amount','')} {payment_info.get('currency','').upper()}"
        )
        text = text + rec

        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🕵️‍♂️ Проверить платеж", callback_data=f"check_payment:{payment_id}")
        keyboard.button(text="🔙 Отмена", callback_data="tariff_back_to_start")
        keyboard.adjust(2, 1)

        await message.answer(
            text=text,
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка при обработке промокода: {e}")
        await message.answer("Произошла ошибка при обработке промокода. Попробуйте позже.")
        await state.clear()

# =========================
# БЫСТРАЯ ПОКУПКА (если вызывается напрямую)
# =========================
@router.callback_query(F.data.startswith("buy_tariff:"))
async def buy_tariff(callback: CallbackQuery, state: FSMContext):
    try:
        tariff_id = int(callback.data.split(":")[1])

        tariff = await db.get_tariff(tariff_id)
        if not tariff:
            await callback.answer("Тариф не найден")
            return

        payment_id, payment_info = await winkpay_manager.create_payment(
            amount=float(tariff['price']),
            description=f"Оплата тарифа {tariff['name']}",
            user_id=str(callback.from_user.id),
            tariff_name=tariff['name']
        )

        if not payment_id or not payment_info:
            await callback.message.answer("Ошибка при создании платежа. Попробуйте позже.")
            return

        await state.update_data(payment_id=payment_id, tariff_id=tariff_id)

        rec = (
            "\n\n<b>Реквизиты для оплаты</b>\n"
            f"Метод: {payment_info.get('gateway_name','')}\n"
            f"Тип: {payment_info.get('detail_type','')}\n"
            f"Получатель: {payment_info.get('initials','')}\n"
            f"Деталь: <code>{payment_info.get('detail','')}</code>\n"
            f"Сумма к оплате: {payment_info.get('amount','')} {payment_info.get('currency','').upper()}"
        )

        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🕵️‍♂️ Проверить платеж", callback_data=f"check_payment:{payment_id}")
        keyboard.button(text="🔙 Отмена", callback_data="tariff_back_to_start")
        keyboard.adjust(2, 1)

        await callback.message.delete()
        await callback.message.answer(
            "💡 <b>Счёт создан</b> — оплатите по реквизитам ниже и нажмите «Проверить платеж»."
            + rec,
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка при создании платежа: {e}")
        await callback.message.answer("Произошла ошибка при создании платежа. Попробуйте позже.")

# =========================
# СПИСОК СЕРВЕРОВ/ТАРИФОВ
# =========================
@router.callback_query(F.data == "show_tariffs")
async def show_tariffs(callback: CallbackQuery):
    """Отображение списка серверов с тарифами"""
    try:
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT DISTINCT s.id, s.name 
                FROM server_settings s
                JOIN tariff t ON s.id = t.server_id
                WHERE t.is_enable = 1
            """) as cursor:
                servers = await cursor.fetchall()

        if not servers:
            await callback.answer("В данный момент нет доступных тарифов")
            return

        keyboard = InlineKeyboardBuilder()
        for server in servers:
            keyboard.button(
                text=f"{server['name']}",
                callback_data=f"user_select_server:{server['id']}"
            )
        keyboard.button(text="🔙 Назад", callback_data="tariff_back_to_start")
        keyboard.adjust(2, 1)

        tariff_message = await db.get_bot_message("tariff")
        text = tariff_message['text'] if tariff_message else (
            "🚀 Выберите сервер, чтобы посмотреть доступные тарифы"
        )

        await callback.message.edit_text(
            text=text,
            reply_markup=keyboard.as_markup()
        )

    except Exception as e:
        logger.error(f"Ошибка при отображении серверов: {e}")
        await callback.message.edit_text(
            "Произошла ошибка при загрузке списка серверов",
            reply_markup=get_start_keyboard()
        )

@router.callback_query(F.data.startswith("user_select_server:"))
async def show_server_tariffs(callback: CallbackQuery, state: FSMContext):
    """Отображение тарифов сервера - пропускаем выбор типа подключения, используем TCP по умолчанию"""
    try:
        server_id = int(callback.data.split(":")[1])
        
        # Сохраняем выбранный сервер и типа подключения в state
        await state.update_data(selected_server_id=server_id, connection_type='tcp')
        
        # Сразу переходим к отображению тарифов (пропускаем выбор типа подключения)
        await show_server_tariffs_list(callback, state, server_id, 'tcp')

    except Exception as e:
        logger.error(f"Ошибка при отображении тарифов сервера: {e}")
        await callback.message.edit_text(
            "Произошла ошибка при загрузке",
            reply_markup=get_start_keyboard()
        )

async def show_server_tariffs_list(callback: CallbackQuery, state: FSMContext, server_id: int, connection_type: str):
    """Отображение списка тарифов для выбранного сервера"""
    try:
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT t.*, s.name as server_name
                FROM tariff t
                JOIN server_settings s ON t.server_id = s.id
                WHERE t.server_id = ? AND t.is_enable = 1
                ORDER BY t.price
            """, (server_id,)) as cursor:
                tariffs = await cursor.fetchall()

        if not tariffs:
            await callback.answer("Для данного сервера нет доступных тарифов")
            return

        server_name = tariffs[0]['server_name']
        
        text = (
            f"🌍 Сервер: {server_name}\n"
            f"📡 Тип подключения: <b>TCP (Reality)</b>\n\n"
            "Доступные тарифные планы:\n\n"
        )

        for tariff in tariffs:
            text += (
                f"<blockquote>"
                f"<b>Тарифный план:</b> {tariff['name']}\n"
                f"<b>Описание:</b> {tariff['description']}\n"
                f"<b>Стоимость:</b> {tariff['price']} руб.\n"
                f"<b>Срок действия:</b> {tariff['left_day']} дней\n"
                f"</blockquote>\n"
            )

        text += "\nВыберите подходящий тарифный план:"

        keyboard = InlineKeyboardBuilder()
        for tariff in tariffs:
            keyboard.button(
                text=f"{tariff['name']} - {tariff['price']}₽",
                callback_data=f"select_tariff:{tariff['id']}"
            )
        keyboard.button(text="🔙 К серверам", callback_data="show_tariffs")
        keyboard.button(text="🔙 В меню", callback_data="tariff_back_to_start")
        keyboard.adjust(2)

        await callback.message.edit_text(
            text=text,
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка при отображении тарифов сервера: {e}")
        await callback.message.edit_text(
            "Произошла ошибка при загрузке тарифов",
            reply_markup=get_start_keyboard()
        )
