from telegram import ReplyKeyboardMarkup, KeyboardButton

def add_start_button():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🔄 Restart bot"), KeyboardButton("❗ Связаться с человеком")]],
        resize_keyboard=True,
    )

def get_main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Показать меню на неделю"), KeyboardButton("Заказать обед")],
            [KeyboardButton("🔄 Restart bot"), KeyboardButton("❗ Связаться с человеком")],
        ],
        resize_keyboard=True,
    )

def get_day_keyboard():
    rows = [
        [KeyboardButton("Понедельник"), KeyboardButton("Вторник")],
        [KeyboardButton("Среда"), KeyboardButton("Четверг")],
        [KeyboardButton("Пятница")],
        [KeyboardButton("🔄 Restart bot"), KeyboardButton("❗ Связаться с человеком")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_count_keyboard():
    rows = [
        [KeyboardButton("1 обед"), KeyboardButton("2 обеда")],
        [KeyboardButton("3 обеда"), KeyboardButton("4 обеда")],
        [KeyboardButton("Назад")],
        [KeyboardButton("🔄 Restart bot"), KeyboardButton("❗ Связаться с человеком")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_count_retry_keyboard():
    rows = [
        [KeyboardButton("1 обед"), KeyboardButton("2 обеда")],
        [KeyboardButton("3 обеда"), KeyboardButton("4 обеда")],
        [KeyboardButton("Выбрать день заново")],
        [KeyboardButton("Назад")],
        [KeyboardButton("🔄 Restart bot"), KeyboardButton("❗ Связаться с человеком")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_confirm_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Да"), KeyboardButton("Изменить адрес")],
            [KeyboardButton("Отправить телефон", request_contact=True)],
            [KeyboardButton("Назад")],
            [KeyboardButton("🔄 Restart bot"), KeyboardButton("❗ Связаться с человеком")],
        ],
        resize_keyboard=True,
    )

def get_contact_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Отправить телефон", request_contact=True)],
            [KeyboardButton("🔄 Restart bot"), KeyboardButton("❗ Связаться с человеком")],
        ],
        resize_keyboard=True,
    )

def get_address_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Назад")],
            [KeyboardButton("🔄 Restart bot"), KeyboardButton("❗ Связаться с человеком")],
        ],
        resize_keyboard=True,
    )