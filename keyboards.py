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
            [KeyboardButton("Заказать на всю неделю"), KeyboardButton("Мои заказы")],
            [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
        ],
        resize_keyboard=True,
    )

def get_main_menu_keyboard_admin():
    """Пользовательское меню для админа с кнопкой возврата в админский режим."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Показать меню на неделю"), KeyboardButton("Заказать обед")],
            [KeyboardButton("Заказать на всю неделю"), KeyboardButton("Мои заказы")],
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
        [KeyboardButton("Заказать на всю неделю"), KeyboardButton("Мои заказы")],
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

def get_weekly_duplicate_keyboard():
    rows = [
        [KeyboardButton("Заменить предыдущие заказы")],
        [KeyboardButton("Добавить к существующим")],
        [KeyboardButton("Отменить оформление")],
        [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_admin_main_keyboard():
    rows = [
        [KeyboardButton("Показать заказы на эту неделю"), KeyboardButton("Перейти в режим пользователя")],
        [KeyboardButton("Управление меню")],
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

def get_admin_manage_menu_keyboard():
    rows = [
        [KeyboardButton("Изменить название недели"), KeyboardButton("Редактировать блюда дня")],
        [KeyboardButton("Обновить фото меню"), KeyboardButton("Открыть заказы на следующую неделю")],
        [KeyboardButton("Назад"), KeyboardButton("🔄 В начало")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_admin_day_select_keyboard(days: list[str]):
    rows = []
    chunk: list[KeyboardButton] = []
    for day in days:
        chunk.append(KeyboardButton(day))
        if len(chunk) == 2:
            rows.append(chunk)
            chunk = []
    if chunk:
        rows.append(chunk)
    rows.append([KeyboardButton("Назад"), KeyboardButton("🔄 В начало")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_admin_day_actions_keyboard():
    rows = [
        [KeyboardButton("Добавить блюдо"), KeyboardButton("Изменить блюдо")],
        [KeyboardButton("Удалить блюдо"), KeyboardButton("Заменить список блюд")],
        [KeyboardButton("Назад"), KeyboardButton("🔄 В начало")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_admin_confirm_keyboard():
    rows = [
        [KeyboardButton("Да"), KeyboardButton("Нет")],
        [KeyboardButton("Назад"), KeyboardButton("🔄 В начало")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_admin_back_keyboard():
    rows = [
        [KeyboardButton("Назад"), KeyboardButton("🔄 В начало")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)
