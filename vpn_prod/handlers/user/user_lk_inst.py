from aiogram import Router, F
from aiogram.types import CallbackQuery
from loguru import logger

from handlers.user.user_kb import get_user_instructions_keyboard, get_back_keyboard

router = Router()

@router.callback_query(F.data == "lk_instructions")
async def show_instructions_menu(callback: CallbackQuery):
    """Отображение меню инструкций"""
    logger.info(f"Получен callback: {callback.data}")
    try:
        await callback.message.delete()
        
        await callback.message.answer(
            "📖 Выберите интересующий вас раздел чтобы получить руководство по подключению 📡",
            reply_markup=get_user_instructions_keyboard()
        )

    except Exception as e:
        logger.error(f"Ошибка при отображении меню инструкций: {e}")
        await callback.message.answer(
            "Произошла ошибка при загрузке инструкций. Попробуйте позже."
        ) 

@router.callback_query(F.data == "instructions_android")
async def show_android_instructions(callback: CallbackQuery):
    """Отображение инструкций для Android"""

    logger.info(f"Получен callback: {callback.data}")
    try:
        await callback.message.delete()
        
        text = (
            "📱 <b>Инструкция для Android</b>\n\n"
            "<b>📥 Рекомендуемое приложение: V2Box</b>\n\n"
            "<blockquote>"
            "1️⃣ Скачайте V2Box из Google Play:\n"
            "   <a href='https://play.google.com/store/apps/details?id=dev.hexasoftware.v2box'>V2Box в Play Market</a>\n\n"
            "2️⃣ Установите и откройте приложение\n\n"
            "3️⃣ Когда получите VLESS ключ от бота:\n"
            "   • Просто нажмите на ключ чтобы скопировать\n"
            "   • Или нажмите кнопку 'Открыть в V2Box' (если доступна)\n\n"
            "4️⃣ В приложении V2Box:\n"
            "   • Нажмите '+' (добавить)\n"
            "   • Выберите 'Импорт из буфера обмена'\n"
            "   • Конфиг добавится автоматически\n\n"
            "5️⃣ Нажмите 'Подключить' ▶️\n\n"
            "✅ Готово! Интернет без границ!\n"
            "</blockquote>\n\n"
            "💡 <b>Альтернативы:</b> Hiddify, v2rayNG, NekoBox"
        )
        
        await callback.message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_back_keyboard(),
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Ошибка при отображении инструкций для Android: {e}")
        await callback.message.answer(
            "Произошла ошибка при загрузке инструкций. Попробуйте позже."
        )

@router.callback_query(F.data == "instructions_ios")
async def show_ios_instructions(callback: CallbackQuery):
    """Отображение инструкций для iOS"""

    logger.info(f"Получен callback: {callback.data}")
    try:
        await callback.message.delete()
        
        await callback.message.answer(
        f"📱 <b>Инструкции для IOS</b>\n\n"
        f"<blockquote>"
        f"1. Заходим в App Store\n"
        f"2. Устанавливаем v2raytun\n"
        f"3. Заходим в приложение\n"
        f"4. Нажимаем '+'  \n"
        f"5. Выбираем 'Добавить из буфера' (перед этим, надо скопировать ключ который выдал бот 'можно просто нажатием на ключ')\n"
        f"6. Готово!\n"
        f"</blockquote>",
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )

    except Exception as e:
        logger.error(f"Ошибка при отображении инструкций для IOS: {e}")
        await callback.message.answer(
            "Произошла ошибка при загрузке инструкций. Попробуйте позже."
        )

@router.callback_query(F.data == "instructions_windows")
async def show_windows_instructions(callback: CallbackQuery):
    """Отображение инструкций для Windows"""
    logger.info(f"Получен callback: {callback.data}")
    try:
        await callback.message.delete()
        
        text = (
            "💻 <b>Инструкция для Windows</b>\n\n"
            "<b>📥 Рекомендуемое приложение: Hiddify</b>\n\n"
            "<blockquote>"
            "1️⃣ Скачайте Hiddify для Windows:\n"
            "   <a href='https://github.com/hiddify/hiddify-next/releases'>Скачать с GitHub</a>\n"
            "   Выберите файл Hiddify-Windows-x64.exe\n\n"
            "2️⃣ Установите приложение:\n"
            "   • Запустите установочный файл\n"
            "   • Следуйте инструкциям установщика\n\n"
            "3️⃣ Первый запуск:\n"
            "   • Откройте Hiddify\n"
            "   • Нажмите 'Новый профиль'\n\n"
            "4️⃣ Добавление конфига:\n"
            "   • Скопируйте VLESS ключ от бота (нажмите на ключ)\n"
            "   • Или нажмите 'Открыть в Hiddify' (если доступно)\n"
            "   • Выберите 'Добавить из буфера обмена'\n\n"
            "5️⃣ Настройка:\n"
            "   • Параметры конфигурации → Регион: 'Другой'\n"
            "   • Режим работы: 'VPN'\n\n"
            "6️⃣ ⚠️ Важно для Windows:\n"
            "   • Запускайте Hiddify от имени администратора\n"
            "   • ПКМ на ярлык → Свойства → Совместимость\n"
            "   • ✓ Запускать от имени администратора\n\n"
            "7️⃣ Подключение:\n"
            "   • Нажмите кнопку подключения ▶️\n"
            "   • Подтвердите запрос от Windows Firewall\n\n"
            "✅ Готово! VPN работает!\n"
            "</blockquote>\n\n"
            "💡 <b>Альтернативы:</b> v2rayN, Nekoray"
        )
        
        await callback.message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_back_keyboard(),
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Ошибка при отображении инструкций для Windows: {e}")
        await callback.message.answer(
            "Произошла ошибка при загрузке инструкций. Попробуйте позже."
        )

@router.callback_query(F.data == "instructions_macos")
async def show_macos_instructions(callback: CallbackQuery):
    """Отображение инструкций для MacOS"""
    logger.info(f"Получен callback: {callback.data}")

    try:
        await callback.message.delete()
        
        text = (
            "💻 <b>Инструкция для MacOS</b>\n\n"
            "<b>📥 Рекомендуемое приложение: V2Box</b>\n\n"
            "<blockquote>"
            "1️⃣ Скачайте V2Box из App Store:\n"
            "   <a href='https://apps.apple.com/app/v2box-v2ray-client/id6446814690'>V2Box в App Store</a>\n\n"
            "2️⃣ Установите и откройте приложение\n\n"
            "3️⃣ Когда получите VLESS ключ от бота:\n"
            "   • Нажмите на ключ чтобы скопировать\n"
            "   • Или нажмите 'Открыть в V2Box' (если доступна)\n\n"
            "4️⃣ В приложении V2Box:\n"
            "   • Нажмите '+' (Add)\n"
            "   • Выберите 'Import from Clipboard'\n"
            "   • Конфиг добавится автоматически\n\n"
            "5️⃣ Нажмите на конфиг и кнопку Connect ▶️\n\n"
            "✅ Готово! VPN активирован!\n"
            "</blockquote>\n\n"
            "💡 <b>Альтернативы:</b> Hiddify, V2rayU, Qv2ray"
        )
        
        await callback.message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_back_keyboard(),
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Ошибка при отображении инструкций для MacOS: {e}")
        await callback.message.answer(
            "Произошла ошибка при загрузке инструкций. Попробуйте позже."
        )
