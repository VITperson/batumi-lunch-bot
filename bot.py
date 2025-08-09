# Основной файл Telegram-бота для заказа обедов
# Для работы требуется заполнить BOT_TOKEN и ADMIN_ID

from config_secret import BOT_TOKEN, ADMIN_ID

import logging
import json
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler, PicklePersistence

from telegram.constants import ParseMode
from logging.handlers import RotatingFileHandler
import time
import os
import html

USERS_FILE = "users.json"

# Состояния для ConversationHandler
MENU, ORDER_DAY, ORDER_COUNT, ADDRESS, CONFIRM = range(5)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
handler = RotatingFileHandler('bot.log', maxBytes=1_000_000, backupCount=3, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(handler)

# Загрузка меню

def load_menu():
    try:
        with open("menu.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            # простая валидация схемы
            if not isinstance(data, dict) or "week" not in data or "menu" not in data or not isinstance(data["menu"], dict):
                logging.error("Меню имеет неверный формат: ожидались ключи 'week' и 'menu' (dict)")
                return None
            return data
    except Exception as e:
        logging.error(f"Ошибка загрузки меню: {e}")
        return None

def log_user_action(user, action):
    username = f"@{user.username}" if user.username else "(нет username)"
    logging.info(f"User {user.id} {username}: {action}")

# Работа с постоянным хранилищем профилей (users.json)

def _load_users() -> dict:
    try:
        if not os.path.exists(USERS_FILE):
            return {}
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        logging.error(f"Не удалось загрузить {USERS_FILE}: {e}")
        return {}


def _save_users(data: dict) -> None:
    try:
        tmp = USERS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, USERS_FILE)
    except Exception as e:
        logging.error(f"Не удалось сохранить {USERS_FILE}: {e}")


def get_user_profile(uid: int) -> dict:
    data = _load_users()
    return data.get(str(uid), {})


def set_user_profile(uid: int, profile: dict) -> None:
    data = _load_users()
    data[str(uid)] = profile
    _save_users(data)

# Вспомогательные функции/клавиатуры

def add_start_button():
    return ReplyKeyboardMarkup([[KeyboardButton("/start")]], resize_keyboard=True)


def get_main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Показать меню на неделю"), KeyboardButton("Заказать обед")], [KeyboardButton("/start")]],
        resize_keyboard=True,
    )


def get_day_keyboard():
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]
    return ReplyKeyboardMarkup([[KeyboardButton(day)] for day in days] + [[KeyboardButton("/start")]], resize_keyboard=True)



def get_count_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(f"{i} обед{'' if i == 1 else 'а'}")] for i in range(1, 5)] + [[KeyboardButton("/start")]],
        resize_keyboard=True,
    )

# Новая клавиатура для выбора количества с кнопкой "Выбрать день заново"
def get_count_retry_keyboard():
    rows = [[KeyboardButton(f"{i} обед{'' if i == 1 else 'а'}")] for i in range(1, 5)]
    rows.append([KeyboardButton("Выбрать день заново")])
    rows.append([KeyboardButton("/start")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def get_confirm_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Да"), KeyboardButton("Изменить адрес или добавить телефон")], [KeyboardButton("/start")]],
        resize_keyboard=True,
    )


def get_contact_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Отправить телефон", request_contact=True)],
            [KeyboardButton("/start")],
        ],
        resize_keyboard=True,
    )



def format_menu(menu_data: dict) -> str:
    lines = [f"Неделя: {menu_data['week']}"]
    for day, items in menu_data["menu"].items():
        if isinstance(items, list):
            pretty = "\n".join(f" - {i}" for i in items)
        else:
            pretty = f" - {items}"
        lines.append(f"{day}:\n{pretty}")
    return "\n".join(lines)


def format_menu_html(menu_data: dict) -> str:
    week = html.escape(str(menu_data.get('week', '')))
    lines = [f"<b>Неделя:</b> {week}"]
    for day, items in menu_data.get('menu', {}).items():
        lines.append(f"\n<b>{html.escape(day)}:</b>")
        if isinstance(items, list):
            for it in items:
                lines.append(f"• {html.escape(str(it))}")
        else:
            lines.append(f"• {html.escape(str(items))}")
    return "\n".join(lines)


def admin_link(user) -> str:
    name = user.first_name or (user.username and f"@{user.username}") or "Пользователь"
    return f"[{name}](tg://user?id={user.id})"

# Стартовая команда
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_action(update.message.from_user, "start")
    # Сброс состояния и user_data
    context.user_data.clear()
    # Подтягиваем сохраненный профиль из users.json, если есть
    saved_profile = get_user_profile(update.effective_user.id)
    if saved_profile:
        context.user_data["profile"] = saved_profile
    caption = (
        "*Добро пожаловать!*\n\n{Тут должна быть краткая информация о компании с полезными фактами, возможно со стоимостью обедов}\n\n"
        "Вы можете:\n• _Посмотреть меню на неделю_\n• _Сразу оформить заказ_\n\nВыберите одну из опций ниже:"
    )
    try:
        with open("Logo.png", "rb") as logo:
            await update.message.reply_photo(
                photo=logo,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_menu_keyboard(),
            )
    except FileNotFoundError:
        await update.message.reply_text(
            caption,
            reply_markup=get_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
    return MENU


# Обработка кнопки "Показать меню на неделю"
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_action(update.message.from_user, "show_menu")
    menu_data = load_menu()
    if not menu_data:
        await update.message.reply_text("Техническая ошибка: меню недоступно. Попробуйте позже.", reply_markup=add_start_button())
        return MENU
    text_html = format_menu_html(menu_data)
    try:
        with open("Menu4-8.jpg", "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=text_html,
                parse_mode=ParseMode.HTML,
                reply_markup=add_start_button()
            )
    except FileNotFoundError:
        await update.message.reply_text(text_html, parse_mode=ParseMode.HTML, reply_markup=add_start_button())
    keyboard = [[KeyboardButton("Да"), KeyboardButton("Выбрать день недели")], [KeyboardButton("/start")]]
    await update.message.reply_text(
        "*Заказать обед сейчас?*", parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ORDER_DAY

# Обработка кнопки "Заказать обед" или "Да"
async def order_lunch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_action(update.message.from_user, "order_lunch")
    await update.message.reply_text("*Выберите день недели:*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_day_keyboard())
    return ORDER_DAY

# Обработка выбора дня недели
async def select_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_action(update.message.from_user, f"select_day: {update.message.text}")
    day = update.message.text
    menu_data = load_menu()
    if not menu_data or day not in menu_data['menu']:
        await update.message.reply_text("*Ошибка:* выберите день недели из списка.", parse_mode=ParseMode.MARKDOWN, reply_markup=add_start_button())
        return ORDER_DAY
    # Сохраняем выбранный день в context.user_data
    context.user_data['selected_day'] = day
    await update.message.reply_text("*Сколько обедов заказать?*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_count_keyboard())
    return ORDER_COUNT

async def select_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_action(update.message.from_user, f"select_count: {update.message.text}")
    count_text = update.message.text
    valid_counts = ["1 обед", "2 обеда", "3 обеда", "4 обеда"]
    if count_text not in valid_counts:
        await update.message.reply_text(
            "*Пожалуйста, используйте кнопки* для выбора количества.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_count_retry_keyboard(),
        )
        return ORDER_COUNT

    # анти-спам: не чаще 1 заказа раз в 10 секунд
    now = time.time()
    last_ts = context.user_data.get("last_order_ts")
    if last_ts and now - last_ts < 10:
        await update.message.reply_text(
            "*Слишком часто.* Подождите немного и попробуйте снова или выберите другой день.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_count_retry_keyboard(),
        )
        return ORDER_COUNT

    count = count_text.split()[0]
    day = context.user_data.get('selected_day', '(не выбран)')
    menu_data = load_menu()
    menu_for_day = menu_data['menu'].get(day, '') if menu_data else ''
    if isinstance(menu_for_day, list):
        menu_for_day_text = ", ".join(menu_for_day)
    else:
        menu_for_day_text = str(menu_for_day)

    context.user_data['selected_count'] = count
    context.user_data['menu_for_day'] = menu_for_day_text

    # проверяем профиль пользователя
    profile = context.user_data.get('profile')
    if not profile:
        profile = get_user_profile(update.effective_user.id)
        if profile:
            context.user_data['profile'] = profile
    has_address = bool((profile or {}).get('address'))

    if has_address:
        # запрашиваем подтверждение доставки на сохраненный адрес
        context.user_data['pending_order'] = {
            'day': day,
            'count': count,
            'menu': menu_for_day_text,
        }
        addr = profile.get('address')
        confirm_text = (
            f"*Подтвердите заказ:*\n\n"
            f"Доставить *{count}* обед(а) (_{menu_for_day_text}_)\n"
            f"В *{day}*\n"
            f"*Адрес доставки:* {addr}\n\n"
            f"Все верно?"
        )
        await update.message.reply_text(
            confirm_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_confirm_keyboard(),
        )
        return CONFIRM

    # иначе просим отправить контакт или ввести адрес текстом
    reply_text = (
        f"В *{day}* вам будет доставлено *{count}* _{menu_for_day_text}_.\n\n"
        f"*Важно:* введите *точный адрес доставки* _текстом_.\n"
        f"Телефон можно отправить кнопкой ниже (по желанию)."
    )
    await update.message.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_contact_keyboard())
    return ADDRESS


#
# Отправка гифки-"стикера" успеха
async def send_success_gif(update: Update):
    try:
        with open("cat-driving.mp4", "rb") as anim:
            # Используем анимацию (mp4 поддерживается как анимация в Telegram)
            await update.message.reply_animation(animation=anim)
    except FileNotFoundError:
        logging.warning("Файл cat-driving.mp4 не найден. Пропускаем анимацию.")
    except Exception as e:
        logging.error(f"Не удалось отправить анимацию: {e}")

# Выбор предлога перед днем недели
def _prep_for_day(day: str) -> str:
    d = (day or "").strip().lower()
    return "во" if d.startswith("вторник") else "в"

# --- Подтверждение заказа ---
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip().lower()
    profile = context.user_data.get('profile') or {}

    if choice == 'изменить адрес или добавить телефон':
        await update.message.reply_text(
            "Введите новый адрес доставки текстом (улица, дом, подъезд/этаж, ориентир).",
            reply_markup=get_contact_keyboard(),
        )
        return ADDRESS

    if choice != 'да':
        # непредвиденный ввод - повторим вопрос
        await update.message.reply_text(
            "Пожалуйста, выберите: *Да* или *Изменить адрес или добавить телефон*.", parse_mode=ParseMode.MARKDOWN, reply_markup=get_confirm_keyboard()
        )
        return CONFIRM

    # 'Да' - отправляем заказ админу
    pend = context.user_data.get('pending_order') or {}
    day = pend.get('day', context.user_data.get('selected_day', '(не выбран)'))
    count = pend.get('count', context.user_data.get('selected_count', '(не выбрано)'))
    menu_for_day = pend.get('menu', context.user_data.get('menu_for_day', ''))

    try:
        count_int = int(str(count))
    except Exception:
        count_int = 1
    cost_lari = count_int * 15
    prep = _prep_for_day(day)

    user = update.message.from_user
    username = f"@{user.username}" if user.username else "(нет username)"
    order_id = f"{user.id}-{int(time.time())}"
    admin_text = (
        f"Новый заказ!\n"
        f"ID заказа: {order_id}\n"
        f"День недели: {day}\n"
        f"Количество обедов: {count}\n"
        f"Меню: {menu_for_day}\n"
        f"Клиент: {admin_link(user)} ({username})\n"
        f"Адрес: {profile.get('address')}\n"
        f"Телефон: {profile.get('phone', 'не указан')}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logging.error(f"Ошибка отправки админу: {e}")

    # Гифка об успешном оформлении
    await send_success_gif(update)

    context.user_data['last_order_ts'] = time.time()
    context.user_data.pop('pending_order', None)

    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("Посмотреть меню")], [KeyboardButton("Выбрать еще один день")], [KeyboardButton("/start")]],
        resize_keyboard=True,
    )
    await update.message.reply_text(
        f"Спасибо! Ваш заказ принят.\n"
        f"Доставка {prep} {day}.\n"
        f"Стоимость заказа {cost_lari} лари.\n\n"
        f"Вы можете сделать новый заказ или посмотреть меню.",
        reply_markup=keyboard,
    )
    return MENU

async def address_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # не логируем PII содержимое
    log_user_action(update.message.from_user, "address/phone step")

    user = update.message.from_user
    profile = context.user_data.get('profile') or {}

    # Если пришел контакт - сохраняем телефон, но без адреса не продолжаем
    if update.message.contact:
        phone = update.message.contact.phone_number
        profile['phone'] = phone
        context.user_data['profile'] = profile
        set_user_profile(user.id, profile)

        if not profile.get('address'):
            await update.message.reply_text(
                "Телефон получили. Теперь *введите точный адрес доставки* _текстом_ (улица, дом, подъезд/этаж, ориентир).",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_contact_keyboard(),
            )
            return ADDRESS
        # если адрес уже есть - продолжаем оформлять заказ ниже

    # Если пришел текст - считаем это адресом
    if update.message.text and not update.message.contact:
        address_text = update.message.text.strip()
        if address_text:
            profile['address'] = address_text
            context.user_data['profile'] = profile
            set_user_profile(user.id, profile)
        else:
            await update.message.reply_text(
                "Адрес пустой. *Введите адрес доставки текстом*.", parse_mode=ParseMode.MARKDOWN, reply_markup=get_contact_keyboard()
            )
            return ADDRESS

    # Проверяем, что адрес есть. Телефон может быть не указан.
    if not profile.get('address'):
        await update.message.reply_text(
            "Нам нужен точный адрес. *Пожалуйста, введите адрес доставки текстом*.", parse_mode=ParseMode.MARKDOWN, reply_markup=get_contact_keyboard()
        )
        return ADDRESS

    # Собираем данные заказа и отправляем админу
    day = context.user_data.get('selected_day', '(не выбран)')
    count = context.user_data.get('selected_count', '(не выбрано)')
    menu_for_day = context.user_data.get('menu_for_day', '')

    try:
        count_int = int(str(count))
    except Exception:
        count_int = 1
    cost_lari = count_int * 15
    prep = _prep_for_day(day)

    username = f"@{user.username}" if user.username else "(нет username)"
    order_id = f"{user.id}-{int(time.time())}"
    admin_text = (
        f"Новый заказ!\n"
        f"ID заказа: {order_id}\n"
        f"День недели: {day}\n"
        f"Количество обедов: {count}\n"
        f"Меню: {menu_for_day}\n"
        f"Клиент: {admin_link(user)} ({username})\n"
        f"Адрес: {profile.get('address')}\n"
        f"Телефон: {profile.get('phone', 'не указан')}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logging.error(f"Ошибка отправки админу: {e}")

    # Гифка об успешном оформлении
    await send_success_gif(update)

    context.user_data['last_order_ts'] = time.time()

    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("Посмотреть меню")], [KeyboardButton("Выбрать еще один день")], [KeyboardButton("/start")]],
        resize_keyboard=True,
    )
    await update.message.reply_text(
        f"Спасибо! Ваш заказ принят.\n"
        f"Доставка {prep} {day}.\n"
        f"Стоимость заказа {cost_lari} лари.\n\n"
        f"Вы можете сделать новый заказ или посмотреть меню.",
        reply_markup=keyboard,
    )
    return MENU

# Обработка некорректных действий
async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state', 'unknown')
    log_user_action(update.message.from_user, f"fallback state={state}")
    await update.message.reply_text(
        "Пожалуйста, используйте *кнопки* для навигации.", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu_keyboard()
    )
    return MENU

# Вспомогательная команда для админа: показать сохраненный профиль пользователя
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    prof = get_user_profile(uid)
    if not prof:
        await update.message.reply_text("Профиль не найден. Введите адрес и телефон при заказе.")
        return
    pretty = json.dumps(prof, ensure_ascii=False, indent=2)
    await update.message.reply_text(f"*Ваш сохраненный профиль:*\n```\n{pretty}\n```", parse_mode=ParseMode.MARKDOWN)

# Основная функция запуска
if __name__ == "__main__":
    persistence = PicklePersistence(filepath="bot_state.pickle")
    application = Application.builder().token(BOT_TOKEN).persistence(persistence).build()

    application.add_handler(CommandHandler("my_profile", my_profile))


    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU: [
                MessageHandler(filters.Regex("^Показать меню на неделю$"), show_menu),
                MessageHandler(filters.Regex("^Заказать обед$"), order_lunch),
                MessageHandler(filters.Regex("^Посмотреть меню$"), show_menu),
                MessageHandler(filters.Regex("^Выбрать еще один день$"), order_lunch),
            ],
            ORDER_DAY: [
                MessageHandler(filters.Regex("^(Понедельник|Вторник|Среда|Четверг|Пятница)$"), select_day),
                MessageHandler(filters.Regex("^Да$"), order_lunch),
                MessageHandler(filters.Regex("^Выбрать день недели$"), order_lunch),
            ],
            ORDER_COUNT: [
                MessageHandler(filters.Regex("^Выбрать день заново$"), order_lunch),
                MessageHandler(filters.Regex("^(1 обед|2 обеда|3 обеда|4 обеда)$"), select_count),
            ],
            ADDRESS: [
                MessageHandler((filters.TEXT | filters.CONTACT) & ~filters.COMMAND, address_phone),
            ],
            CONFIRM: [
                MessageHandler(filters.Regex("^(Да|Изменить адрес или добавить телефон)$"), confirm_order),
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order),
            ],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(filters.ALL, fallback)]
    )
    application.add_handler(conv_handler)
    logging.info("Бот запущен.")
    application.run_polling(drop_pending_updates=True)
