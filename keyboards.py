from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def add_start_button():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")]],
        resize_keyboard=True,
    )

def get_main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Мои заказы")],
            [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
        ],
        resize_keyboard=True,
    )

def get_main_menu_keyboard_admin():
    """Пользовательское меню для админа с кнопкой возврата в админский режим."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Мои заказы"), KeyboardButton("Перейти в режим администратора")],
            [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
        ],
        resize_keyboard=True,
    )

def get_day_keyboard():
    rows = [
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

def get_salad_choice_keyboard(options: list[str]):
    rows: list[list[KeyboardButton]] = []
    for item in options:
        label = str(item).strip()
        if label:
            rows.append([KeyboardButton(label)])
    rows.append([KeyboardButton("Без салатов")])
    rows.append([KeyboardButton("Назад")])
    rows.append([KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_salad_count_keyboard():
    rows = [
        [KeyboardButton("1 салат"), KeyboardButton("2 салата")],
        [KeyboardButton("3 салата"), KeyboardButton("4 салата")],
        [KeyboardButton("Назад")],
        [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_count_retry_keyboard():
    rows = [
        [KeyboardButton("1 обед"), KeyboardButton("2 обеда")],
        [KeyboardButton("3 обеда"), KeyboardButton("4 обеда")],
        [KeyboardButton("Выбрать другой день")],
        [KeyboardButton("Назад")],
        [KeyboardButton("🔄 В начало"), KeyboardButton("❗ Связаться с человеком")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

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
        [KeyboardButton("Посмотреть меню"), KeyboardButton("Мои заказы")],
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
        [KeyboardButton("Загрузить фото меню (AI)")],
        [KeyboardButton("Назад")],
        [KeyboardButton("🔄 В начало")],
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


BULK_COUNTER_BUTTONS = {
    "decrement_all": "➖",
    "increment_all": "➕",
    "continue": "Продолжить",
    "cancel": "Отмена",
}
BULK_DAY_SHORT_LABELS = {
    "mon": "ПН",
    "tue": "ВТ",
    "wed": "СР",
    "thu": "ЧТ",
    "fri": "ПТ",
}


def get_bulk_counter_keyboard(
    state: dict[str, dict],
    max_per_day: int | None = None,
    salad_counts: dict[int, int] | None = None,
    salad_labels: list[str] | None = None,
    salad_indices: list[int] | None = None,
) -> InlineKeyboardMarkup:
    """
    Формирует инлайн-клавиатуру с инкрементами/декрементами по дням.
    Ожидается, что state содержит ключи-дни (mon/tue/...) с полями label/count/selected.
    """
    rows: list[list[InlineKeyboardButton]] = []
    for day_code in ("mon", "tue", "wed", "thu", "fri"):
        day_info = state.get(day_code)
        if not isinstance(day_info, dict) or not day_info.get("selected"):
            continue
        full_label = str(day_info.get("label") or "").strip() or day_code
        short_label = BULK_DAY_SHORT_LABELS.get(day_code, full_label)
        try:
            count = int(str(day_info.get("count", 0)).split()[0])
        except Exception:
            count = 0
        if count < 0:
            count = 0
        day_text = f"{short_label} {count}"
        minus_cb = f"bulk:dec:{day_code}"
        plus_cb = f"bulk:inc:{day_code}"
        toggle_cb = f"bulk:viewmenu:{day_code}"
        rows.append([
            InlineKeyboardButton(text="➖", callback_data=minus_cb),
            InlineKeyboardButton(text=day_text, callback_data=toggle_cb),
            InlineKeyboardButton(text="➕", callback_data=plus_cb),
        ])

    if salad_labels:
        indices = salad_indices if salad_indices else list(range(len(salad_labels)))
        if indices:
            rows.append([InlineKeyboardButton("Новогодние салаты", callback_data="bulk:salad:noop:*")])
        for idx in indices:
            if idx < 0 or idx >= len(salad_labels):
                continue
            label = salad_labels[idx]
            try:
                count = int((salad_counts or {}).get(idx, 0))
            except Exception:
                count = 0
            if count < 0:
                count = 0
            minus_cb = f"bulk:salad:dec:{idx}"
            plus_cb = f"bulk:salad:inc:{idx}"
            rows.append([
                InlineKeyboardButton(text="➖", callback_data=minus_cb),
                InlineKeyboardButton(text=f"{label} {count}", callback_data="bulk:salad:noop:*"),
                InlineKeyboardButton(text="➕", callback_data=plus_cb),
            ])

    if not rows:
        rows.append([
            InlineKeyboardButton("Нет доступных дней", callback_data="bulk:cancel:*"),
        ])
        return InlineKeyboardMarkup(rows)

    rows.append([
        InlineKeyboardButton(
            BULK_COUNTER_BUTTONS["decrement_all"],
            callback_data="bulk:decall:*",
        ),
        InlineKeyboardButton(
            BULK_COUNTER_BUTTONS["increment_all"],
            callback_data="bulk:incall:*",
        ),
    ])
    rows.append([
        InlineKeyboardButton(
            BULK_COUNTER_BUTTONS["continue"],
            callback_data="bulk:next:*",
        ),
        InlineKeyboardButton(
            BULK_COUNTER_BUTTONS["cancel"],
            callback_data="bulk:cancel:*",
        ),
    ])
    return InlineKeyboardMarkup(rows)


def get_single_confirm_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Подтверждаю", callback_data="confirm_accept"),
            InlineKeyboardButton("Назад", callback_data="confirm_back"),
        ]]
    )


def get_weekly_confirm_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Подтверждаю", callback_data="weekly_confirm_accept"),
                InlineKeyboardButton("Назад", callback_data="weekly_confirm_back"),
            ],
            [
                InlineKeyboardButton("Изменить адрес", callback_data="weekly_confirm_edit_address"),
                InlineKeyboardButton("Изменить телефон", callback_data="weekly_confirm_edit_phone"),
            ],
        ]
    )
