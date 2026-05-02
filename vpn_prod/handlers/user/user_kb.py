from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_start_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Создание стартовой клавиатуры"""
    keyboard_buttons = [
        [KeyboardButton(text="👤 Личный кабинет"), KeyboardButton(text="🎁 Пробный период")],
        [KeyboardButton(text="💳 Тарифы"), KeyboardButton(text="📞 Техподдержка")],
    ]
    
    # Добавляем кнопку админ-панели для администраторов
    if is_admin:
        keyboard_buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_buttons,
        resize_keyboard=True,
        persistent=True
    )
    return keyboard

def get_lk_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры личного кабинета"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Мои подписки"), KeyboardButton(text="💰 Мои платежи")],
            [KeyboardButton(text="📢 Инструкции"), KeyboardButton(text="💬 Помощь")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard

def get_trial_keyboard(show_connect: bool = True) -> ReplyKeyboardMarkup:
    """Создание клавиатуры для пробного периода"""
    if show_connect:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔗 Подключить")],
                [KeyboardButton(text="🏠 Главное меню")],
            ],
            resize_keyboard=True,
            persistent=True
        )
    else:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💳 Тарифы")],
                [KeyboardButton(text="🏠 Главное меню")],
            ],
            resize_keyboard=True,
            persistent=True
        )
    return keyboard

def get_trial_vless_keyboard(show_connect: bool = True) -> ReplyKeyboardMarkup:
    """Создание клавиатуры для сообщения с ключом vless"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Тарифы"), KeyboardButton(text="📋 Мои подписки")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard

def get_subscriptions_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры для отображения подписок"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Личный кабинет")],#, KeyboardButton(text="🤝 Объеденить подписки")],
            [KeyboardButton(text="💳 Тарифы"), KeyboardButton(text="💬 Помощь")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard

def get_continue_merge_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры для продолжения объединения подписок"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Продолжить"), KeyboardButton(text="👤 Личный кабинет")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard

def get_back_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры для кнопки назад"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Личный кабинет")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard

def get_success_by_keyboard(show_connect: bool = True) -> ReplyKeyboardMarkup:
    """Создание клавиатуры для сообщения с ключом vless"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Личный кабинет"), KeyboardButton(text="📋 Мои подписки")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard

def get_help_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры для раздела помощи"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            #[KeyboardButton(text="🤝 Объеденить подписки"), KeyboardButton(text="📞 Техподдержка")],
            [KeyboardButton(text="👤 Личный кабинет"), KeyboardButton(text="📞 Техподдержка")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard

def get_no_subscriptions_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры для сообщения о том что нет активных подписок"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Личный кабинет"), KeyboardButton(text="💳 Тарифы")],
            [KeyboardButton(text="📞 Техподдержка")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard

def get_user_instructions_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры для раздела инструкций"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Android"), KeyboardButton(text="📱 IOS")],
            [KeyboardButton(text="💻 Windows"), KeyboardButton(text="💻 MacOS")],
            [KeyboardButton(text="👤 Личный кабинет")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard

def get_unknown_command_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры для неизвестной команды"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Техподдержка")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard