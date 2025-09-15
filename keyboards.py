from telegram import ReplyKeyboardMarkup, KeyboardButton

def add_start_button():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")]],
        resize_keyboard=True,
    )

def get_main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Показать меню на неделю"), KeyboardButton("Заказать обед")],
            [KeyboardButton("Мои заказы")],
            [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
        ],
        resize_keyboard=True,
    )

def get_main_menu_keyboard_admin():
    """Пользовательское меню для админа с кнопкой возврата в админский режим."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Показать меню на неделю"), KeyboardButton("Заказать обед")],
            [KeyboardButton("Мои заказы")],
            [KeyboardButton("Перейти в режим администратора")],
            [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
        ],
        resize_keyboard=True,
    )

def get_day_keyboard():
    rows = [
        [KeyboardButton("Понедельник"), KeyboardButton("Вторник")],
        [KeyboardButton("Среда"), KeyboardButton("Четверг")],
        [KeyboardButton("Пятница")],
        [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_count_keyboard():
    rows = [
        [KeyboardButton("1 обед"), KeyboardButton("2 обеда")],
        [KeyboardButton("3 обеда"), KeyboardButton("4 обеда")],
        [KeyboardButton("Назад")],
        [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_count_retry_keyboard():
    rows = [
        [KeyboardButton("1 обед"), KeyboardButton("2 обеда")],
        [KeyboardButton("3 обеда"), KeyboardButton("4 обеда")],
        [KeyboardButton("Выбрать день заново")],
        [KeyboardButton("Назад")],
        [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_confirm_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Подтверждаю"), KeyboardButton("Изменить адрес")],
            [KeyboardButton("Отправить телефон", request_contact=True)],
            [KeyboardButton("Назад")],
            [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
        ],
        resize_keyboard=True,
    )

def get_contact_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Отправить телефон", request_contact=True)],
            [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
        ],
        resize_keyboard=True,
    )

def get_address_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Назад")],
            [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
        ],
        resize_keyboard=True,
    )


def get_order_prompt_keyboard():
    rows = [
        [KeyboardButton("Да"), KeyboardButton("Выбрать день недели")],
        [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def get_after_confirm_keyboard():
    rows = [
        [KeyboardButton("Посмотреть меню"), KeyboardButton("Выбрать еще один день")],
        [KeyboardButton("Мои заказы")],
        [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_duplicate_resolution_keyboard():
    rows = [
        [KeyboardButton("Удалить предыдущий заказ")],
        [KeyboardButton("Добавить к существующему")],
        [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_admin_main_keyboard():
    rows = [
        [KeyboardButton("Показать заказы на эту неделю")],
        [KeyboardButton("Перейти в режим пользователя")],
        [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_admin_report_keyboard():
    rows = [
        [KeyboardButton("Неделя целиком")],
        [KeyboardButton("Понедельник"), KeyboardButton("Вторник")],
        [KeyboardButton("Среда"), KeyboardButton("Четверг")],
        [KeyboardButton("Пятница")],
        [KeyboardButton("🔄 В начало")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)
