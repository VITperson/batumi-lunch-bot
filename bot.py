# Основной файл Telegram-бота для заказа обедов
# Для работы требуется заполнить BOT_TOKEN и ADMIN_ID


from config_secret import BOT_TOKEN, ADMIN_ID

# Дополнительные контакты оператора (опционально из config_secret)
try:
    from config_secret import OPERATOR_HANDLE, OPERATOR_PHONE
except Exception:
    OPERATOR_HANDLE = "@vitperson"
    OPERATOR_PHONE = "+995 000 000 000"

import logging
import json
import re
import secrets
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler, PicklePersistence
from keyboards import (
    add_start_button,
    get_main_menu_keyboard,
    get_day_keyboard,
    get_count_keyboard,
    get_count_retry_keyboard,
    get_confirm_keyboard,
    get_contact_keyboard,
    get_address_keyboard,
)

from telegram.constants import ParseMode
from logging.handlers import TimedRotatingFileHandler
import time
import os
import html

USERS_FILE = "users.json"
ORDERS_FILE = "orders.json"

# Состояния для ConversationHandler
MENU, ORDER_DAY, ORDER_COUNT, ADDRESS, CONFIRM = range(5)

# Настройка логирования с TimedRotatingFileHandler
logger = logging.getLogger()
logger.setLevel(logging.INFO)
log_handler = TimedRotatingFileHandler(
    'bot.log',
    when="midnight",
    interval=1,
    backupCount=30,
    encoding='utf-8'
)
log_handler.suffix = "%Y-%m-%d"
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Логи в терминал (только важные события)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(message)s'))
console_handler.setLevel(logging.INFO)

# Перенастройка логгера
logger.handlers.clear()
# Подавляем шумные логи httpx (например, запросы Telegram API)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

# Функция для явного логирования в консоль
def log_console(message):
    console_handler.stream.write(message + "\n")
    console_handler.flush()

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


# Работа с заказами и человекочитаемым ID

def _load_orders() -> dict:
    try:
        if not os.path.exists(ORDERS_FILE):
            return {}
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        logging.error(f"Не удалось загрузить {ORDERS_FILE}: {e}")
        return {}


def _save_orders(data: dict) -> None:
    try:
        tmp = ORDERS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, ORDERS_FILE)
    except Exception as e:
        logging.error(f"Не удалось сохранить {ORDERS_FILE}: {e}")


def _base36(n: int) -> str:
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if n == 0:
        return "0"
    sign = "-" if n < 0 else ""
    n = abs(n)
    out = []
    while n:
        n, r = divmod(n, 36)
        out.append(chars[r])
    return sign + "".join(reversed(out))


def make_order_id(user_id: int) -> str:
    # Формат: BLB-<ts36>-<uid36>-<rnd>
    ts36 = _base36(int(time.time()))
    uid36 = _base36(abs(int(user_id)))[-4:].rjust(4, "0")
    rnd = _base36(secrets.randbits(20)).rjust(4, "0")[:4]
    return f"BLB-{ts36}-{uid36}-{rnd}"


def save_order(order_id: str, payload: dict) -> None:
    data = _load_orders()
    data[order_id] = payload
    _save_orders(data)


def get_order(order_id: str) -> dict | None:
    return _load_orders().get(order_id)


def get_user_profile(uid: int) -> dict:
    data = _load_users()
    return data.get(str(uid), {})


def set_user_profile(uid: int, profile: dict) -> None:
    data = _load_users()
    data[str(uid)] = profile
    _save_users(data)

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

# HTML-safe variant for admin link
def admin_link_html(user) -> str:
    name = user.first_name or (user.username and f"@{user.username}") or "Пользователь"
    return f'<a href="tg://user?id={user.id}">{html.escape(name)}</a>'

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
        "<b>Добро пожаловать!</b>\n\n"
        "🥗 Предлагаем доставку вкусных домашних обедов.\n"
        "В обед входит:\n"
        " - мясное блюдо (курица или свинина) 110 гр;\n"
        " - гарнир 300 гр;\n"
        " - салаты 250 гр.\n"
        "Каждую неделю новое меню.\n"
        "Бесплатная доставка в одноразовых порционных контейнерах.\n"
        "🫰 <b>Стоимость: 15 лари</b>\n\n"
        "За подробностями/заказами обращайтесь по телефону: "
        "<a href=\"tel:+995599526391\">+995599526391</a>\n"
        "Telegram: <a href=\"https://t.me/obedy_dostavka\">@obedy_dostavka</a>\n\n"
        "С помощью бота Вы можете:\n• Посмотреть меню на эту неделю\n• Сразу оформить заказ\n\nВыберите одну из опций ниже:"
    )
    log_console("Пользователь начал работу с ботом")
    try:
        with open("Logo.png", "rb") as logo:
            await update.message.reply_photo(
                photo=logo,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=get_main_menu_keyboard(),
            )
    except FileNotFoundError:
        await update.message.reply_text(
            caption,
            reply_markup=get_main_menu_keyboard(),
            parse_mode=ParseMode.HTML,
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
        with open("Menu.jpeg", "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                reply_markup=add_start_button()
            )
    except FileNotFoundError:
        pass
    await update.message.reply_text(text_html, parse_mode=ParseMode.HTML, reply_markup=add_start_button())
    keyboard = [
        [KeyboardButton("Да"), KeyboardButton("Выбрать день недели")],
        [KeyboardButton("🔄 Restart bot"), KeyboardButton("❗ Связаться с человеком")]
    ]
    await update.message.reply_text(
        "<b>Заказать обед сейчас?</b>", parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ORDER_DAY

# Обработка кнопки "Заказать обед" или "Да"
async def order_lunch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_action(update.message.from_user, "order_lunch")
    await update.message.reply_text("<b>Выберите день недели:</b>", parse_mode=ParseMode.HTML, reply_markup=get_day_keyboard())
    return ORDER_DAY
# Обработка выбора дня недели
async def select_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_action(update.message.from_user, f"select_day: {update.message.text}")
    day = update.message.text
    menu_data = load_menu()
    if not menu_data or day not in menu_data['menu']:
        await update.message.reply_text("<b>Ошибка:</b> выберите день недели из списка.", parse_mode=ParseMode.HTML, reply_markup=get_day_keyboard())
        return ORDER_DAY
    # Сохраняем выбранный день в context.user_data
    context.user_data['selected_day'] = day
    await update.message.reply_text("<b>Сколько обедов заказать?</b>", parse_mode=ParseMode.HTML, reply_markup=get_count_keyboard())
    return ORDER_COUNT

async def select_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_action(update.message.from_user, f"select_count: {update.message.text}")
    count_text = update.message.text
    valid_counts = ["1 обед", "2 обеда", "3 обеда", "4 обеда"]
    if count_text not in valid_counts:
        await update.message.reply_text(
            "Пожалуйста, используйте <b>кнопки</b> для выбора количества.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_count_retry_keyboard(),
        )
        return ORDER_COUNT

    # анти-спам: не чаще 1 заказа раз в 10 секунд
    now = time.time()
    last_ts = context.user_data.get("last_order_ts")
    if last_ts and now - last_ts < 10:
        await update.message.reply_text(
            "<b>Слишком часто.</b> Подождите немного и попробуйте снова или выберите другой день.",
            parse_mode=ParseMode.HTML,
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
        phone_line = profile.get('phone') or "вы можете добавить телефон через кнопку ниже"
        # Форматируем меню построчно для читабельности (HTML + экранирование)
        menu_lines_html = "\n".join(
            f" - {html.escape(it.strip())}" for it in str(menu_for_day_text).split(',') if it.strip()
        )
        confirm_text = (
            f"<b>Подтвердите заказ</b>\n\n"
            f"<b>День:</b> {html.escape(day)}\n"
            f"<b>Количество:</b> {html.escape(str(count))}\n"
            f"<b>Меню:</b>\n{menu_lines_html}\n\n"
            f"<b>Адрес доставки:</b>\n{html.escape(addr or '')}\n"
            f"<b>Телефон:</b> {html.escape(phone_line)}\n\n"
            f"Все верно?"
        )
        await update.message.reply_text(
            confirm_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_confirm_keyboard(),
        )
        return CONFIRM

    # иначе просим отправить контакт или ввести адрес текстом
    reply_text = (
        f"<b>Заказ почти готов</b>!\n\n"
        f"В {html.escape(day)} доставим <b>{html.escape(str(count))}</b> {html.escape(menu_for_day_text)}.\n\n"
        f"<b>Что дальше?</b>\n"
        f"Отправьте, пожалуйста, <b>точный адрес доставки</b> одним сообщением: улица, дом, подъезд/этаж/квартира, ориентир для курьера.\n"
        f"После этого вы сможете проверить и подтвердить заказ."
    )
    await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML, reply_markup=get_address_keyboard())
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

    if choice == 'изменить адрес':
        await update.message.reply_text(
            "<b>Введите новый адрес доставки</b>\n\n"
            "Укажите в одном сообщении:\n"
            " • улицу и дом\n"
            " • подъезд/этаж/квартиру (если есть)\n"
            " • ориентир для курьера",
            parse_mode=ParseMode.HTML,
            reply_markup=get_address_keyboard(),
        )
        return ADDRESS

    if choice != 'подтверждаю':
        # непредвиденный ввод - повторим вопрос
        await update.message.reply_text(
            "Пожалуйста, выберите: <b>Подтверждаю</b> или <b>Изменить адрес</b>.", parse_mode=ParseMode.HTML, reply_markup=get_confirm_keyboard()
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
    order_id = make_order_id(user.id)

    created_at = int(time.time())
    save_order(order_id, {
        "user_id": user.id,
        "username": user.username,
        "day": day,
        "count": count,
        "menu": menu_for_day,
        "address": profile.get('address'),
        "phone": profile.get('phone'),
        "status": "new",
        "created_at": created_at,
    })

    admin_text = (
        f"<b>Новый заказ!</b>\n"
        f"ID заказа: {html.escape(order_id)}\n"
        f"День недели: {html.escape(day)}\n"
        f"Количество обедов: {html.escape(str(count))}\n"
        f"Меню: {html.escape(menu_for_day)}\n"
        f"Клиент: {admin_link_html(user)} ({html.escape(username)})\n"
        f"Адрес: {html.escape(profile.get('address') or '')}\n"
        f"Телефон: {html.escape(profile.get('phone') or 'не указан')}"
    )
    log_console(f"Заказ от пользователя {user.id}")
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Ошибка отправки админу: {e}")

    # Гифка об успешном оформлении
    await send_success_gif(update)

    context.user_data['last_order_ts'] = time.time()
    context.user_data.pop('pending_order', None)

    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton("Посмотреть меню")],
            [KeyboardButton("Выбрать еще один день")],
            [KeyboardButton("🔄 Restart bot"), KeyboardButton("❗ Связаться с человеком")]
        ],
        resize_keyboard=True,
    )
    await update.message.reply_text(
        f"Спасибо! Ваш заказ принят.\n"
        f"ID заказа: {order_id}. Сохраните его.\n"
        f"День доставки: {day}, с 12:30 до 15:30.\n"
        f"Стоимость заказа {cost_lari} лари.\n"
        f"Оплатить можно наличными курьеру или переводом.\n\n"
        f"<b>Чтобы посмотреть детали позже:</b>\n"
        f"<blockquote>/order {order_id}</blockquote>",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )
    return MENU



# Назад с подтверждения к выбору количества
async def back_to_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Сколько обедов заказать?</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_count_keyboard(),
    )
    return ORDER_COUNT

# Назад с выбора количества к выбору дня
async def back_to_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Выберите день недели:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_day_keyboard(),
    )
    return ORDER_DAY

# На подтверждении: запросить телефон (покажем кнопку с запросом контакта)
async def confirm_request_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Нажмите кнопку ниже, чтобы отправить номер одним нажатием.",
        reply_markup=get_contact_keyboard(),
    )
    return CONFIRM

# На подтверждении: сохранить телефон и заново показать подтверждение
async def confirm_save_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.contact:
        return CONFIRM
    phone = update.message.contact.phone_number
    profile = context.user_data.get('profile') or {}
    profile['phone'] = phone
    context.user_data['profile'] = profile
    set_user_profile(update.effective_user.id, profile)

    # Восстанавливаем данные для подтверждения
    pend = context.user_data.get('pending_order') or {}
    day = pend.get('day', context.user_data.get('selected_day', '(не выбран)'))
    count = pend.get('count', context.user_data.get('selected_count', '(не выбрано)'))
    menu_for_day_text = pend.get('menu', context.user_data.get('menu_for_day', ''))
    addr = profile.get('address', '')
    phone_line = profile.get('phone') or "вы можете добавить телефон через кнопку ниже"
    menu_lines_html = "\n".join(
        f" - {html.escape(it.strip())}" for it in str(menu_for_day_text).split(',') if it.strip()
    )
    confirm_text = (
        f"<b>Подтвердите заказ</b>\n\n"
        f"<b>День:</b> {html.escape(day)}\n"
        f"<b>Количество:</b> {html.escape(str(count))}\n"
        f"<b>Меню:</b>\n{menu_lines_html}\n\n"
        f"<b>Адрес доставки:</b>\n{html.escape(addr or '')}\n"
        f"<b>Телефон:</b> {html.escape(phone_line)}\n\n"
        f"Все верно?"
    )
    await update.message.reply_text(
        confirm_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_confirm_keyboard(),
    )
    return CONFIRM

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
                "<b>Телефон получен.</b> Теперь введите <b>точный адрес доставки</b> текстом (улица, дом, подъезд/этаж, ориентир).",
                parse_mode=ParseMode.HTML,
                reply_markup=get_address_keyboard(),
            )
            return ADDRESS
        # если адрес уже есть - показываем подтверждение заказа
        pend = context.user_data.get('pending_order') or {}
        day = pend.get('day', context.user_data.get('selected_day', '(не выбран)'))
        count = pend.get('count', context.user_data.get('selected_count', '(не выбрано)'))
        menu_for_day_text = pend.get('menu', context.user_data.get('menu_for_day', ''))
        addr = profile.get('address', '')
        phone_line = profile.get('phone') or "вы можете добавить телефон через кнопку ниже"
        menu_lines_html = "\n".join(
            f" - {html.escape(it.strip())}" for it in str(menu_for_day_text).split(',') if it.strip()
        )
        confirm_text = (
            f"<b>Подтвердите заказ</b>\n\n"
            f"<b>День:</b> {html.escape(day)}\n"
            f"<b>Количество:</b> {html.escape(str(count))}\n"
            f"<b>Меню:</b>\n{menu_lines_html}\n\n"
            f"<b>Адрес доставки:</b>\n{html.escape(addr or '')}\n"
            f"<b>Телефон:</b> {html.escape(phone_line)}\n\n"
            f"Все верно?"
        )
        await update.message.reply_text(
            confirm_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_confirm_keyboard(),
        )
        return CONFIRM

    # Если пришел текст - считаем это адресом
    if update.message.text and not update.message.contact:
        address_text = update.message.text.strip()
        if address_text:
            profile['address'] = address_text
            context.user_data['profile'] = profile
            set_user_profile(user.id, profile)
            # Переходим на подтверждение с новым адресом
            pend = context.user_data.get('pending_order') or {}
            day = pend.get('day', context.user_data.get('selected_day', '(не выбран)'))
            count = pend.get('count', context.user_data.get('selected_count', '(не выбрано)'))
            menu_for_day_text = pend.get('menu', context.user_data.get('menu_for_day', ''))
            addr = profile.get('address', '')
            phone_line = profile.get('phone') or "вы можете добавить телефон через кнопку ниже"
            menu_lines_html = "\n".join(
                f" - {html.escape(it.strip())}" for it in str(menu_for_day_text).split(',') if it.strip()
            )
            confirm_text = (
                f"<b>Подтвердите заказ</b>\n\n"
                f"<b>День:</b> {html.escape(day)}\n"
                f"<b>Количество:</b> {html.escape(str(count))}\n"
                f"<b>Меню:</b>\n{menu_lines_html}\n\n"
                f"<b>Адрес доставки:</b>\n{html.escape(addr or '')}\n"
                f"<b>Телефон:</b> {html.escape(phone_line)}\n\n"
                f"Все верно?"
            )
            await update.message.reply_text(
                confirm_text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_confirm_keyboard(),
            )
            return CONFIRM
        else:
            await update.message.reply_text(
                "Адрес пустой. <b>Введите адрес доставки текстом</b>.", parse_mode=ParseMode.HTML, reply_markup=get_address_keyboard()
            )
            return ADDRESS

    # Если по каким-то причинам адрес все еще не заполнен, просим ввести адрес
    if not profile.get('address'):
        await update.message.reply_text(
            "Нам нужен точный адрес. <b>Пожалуйста, введите адрес доставки текстом</b>.", parse_mode=ParseMode.HTML, reply_markup=get_address_keyboard()
        )
        return ADDRESS
# Команда: получить информацию о заказе по ID (для пользователя и админа)
async def order_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args if hasattr(context, "args") else []
    if not args:
        await update.message.reply_text("Использование: /order <ID>\nНапример: /order BLB-ABCDEFG-1234-1XYZ")
        return
    order_id = args[0].strip()
    data = get_order(order_id)
    if not data:
        await update.message.reply_text("Заказ с таким ID не найден.")
        return

    user = update.effective_user
    is_admin = (user.id == ADMIN_ID)
    is_owner = (data.get("user_id") == user.id)
    if not (is_admin or is_owner):
        await update.message.reply_text("У вас нет доступа к этому заказу.")
        return

    created_at = data.get("created_at")
    created_line = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created_at)) if created_at else "-"
    phone_line = data.get("phone") or "не указан"
    text = (
        f"ID заказа: {order_id}\n"
        f"Создан: {created_line}\n"
        f"День недели: {data.get('day')}\n"
        f"Количество: {data.get('count')}\n"
        f"Меню: {data.get('menu')}\n"
        f"Адрес: {data.get('address')}\n"
        f"Телефон: {phone_line}"
    )
    await update.message.reply_text(text)

# Обработка некорректных действий
async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state', 'unknown')
    log_user_action(update.message.from_user, f"fallback state={state}")
    await update.message.reply_text(
        "Пожалуйста, используйте <b>кнопки</b> для навигации.", parse_mode=ParseMode.HTML, reply_markup=get_main_menu_keyboard()
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
    await update.message.reply_text(f"<b>Ваш сохраненный профиль:</b>\n<pre>{html.escape(pretty)}</pre>", parse_mode=ParseMode.HTML)


# Handler for "Связаться с человеком" button
async def contact_human(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handle = (OPERATOR_HANDLE or "").lstrip("@")
    phone = OPERATOR_PHONE or ""
    parts = []
    if handle:
        parts.append(f"\nTelegram: <a href=\"https://t.me/{html.escape(handle)}\">@{html.escape(handle)}</a>")
    if phone:
        parts.append(f"\nпо телефону: <a href=\"tel:{html.escape(phone)}\">{html.escape(phone)}</a>")
    msg = "Связаться с оператором можно через " + "\nили ".join(parts) if parts else "Контакты оператора временно недоступны."
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    return

# Универсальное логирование нажатий любых кнопок (ReplyKeyboard)
BUTTON_TEXTS = [
    "Показать меню на неделю",
    "Заказать обед",
    "Посмотреть меню",
    "Выбрать еще один день",
    "Выбрать день недели",
    "Выбрать день заново",
    "Понедельник", "Вторник", "Среда", "Четверг", "Пятница",
    "1 обед", "2 обеда", "3 обеда", "4 обеда",
    "Да",
    "Подтверждаю",
    "Изменить адрес",
    "Назад",
    "Отправить телефон",
    "🔄 Restart bot",
    "❗ Связаться с человеком",
    "Restart bot",
    "Связаться с человеком",
]

BUTTONS_REGEX = r"^(" + "|".join(re.escape(s) for s in BUTTON_TEXTS) + r")$"

async def log_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        log_user_action(update.message.from_user, f"button_click: {update.message.text}")

#
# Глобальный обработчик ошибок
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.exception("Unhandled exception", exc_info=context.error)
    try:
        from telegram import Update
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "Упс, возникла техническая ошибка. Попробуйте еще раз чуть позже.")
    except Exception:
        pass

# Основная функция запуска

if __name__ == "__main__":
    persistence = PicklePersistence(filepath="bot_state.pickle")
    application = Application.builder().token(BOT_TOKEN).persistence(persistence).build()

    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("my_profile", my_profile))
    application.add_handler(CommandHandler("order", order_info))

    # Логирование нажатий любых кнопок (универсальный handler, не блокирует дальнейшую обработку)
    application.add_handler(MessageHandler(filters.Regex(BUTTONS_REGEX), log_button), group=1)

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^🔄 Restart bot$"), start)
        ],
        states={
            MENU: [
                MessageHandler(filters.Regex("^Показать меню на неделю$"), show_menu),
                MessageHandler(filters.Regex("^Заказать обед$"), order_lunch),
                MessageHandler(filters.Regex("^Посмотреть меню$"), show_menu),
                MessageHandler(filters.Regex("^Выбрать еще один день$"), order_lunch),
                MessageHandler(filters.Regex("^🔄 Restart bot$"), start),
                MessageHandler(filters.Regex("^Restart bot$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
            ],
            ORDER_DAY: [
                MessageHandler(filters.Regex("^(Понедельник|Вторник|Среда|Четверг|Пятница)$"), select_day),
                MessageHandler(filters.Regex("^Да$"), order_lunch),
                MessageHandler(filters.Regex("^Выбрать день недели$"), order_lunch),
                MessageHandler(filters.Regex("^🔄 Restart bot$"), start),
                MessageHandler(filters.Regex("^Restart bot$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
            ],
            ORDER_COUNT: [
                MessageHandler(filters.Regex("^Назад$"), back_to_day),
                MessageHandler(filters.Regex("^Выбрать день заново$"), order_lunch),
                MessageHandler(filters.Regex("^(1 обед|2 обеда|3 обеда|4 обеда)$"), select_count),
                MessageHandler(filters.Regex("^🔄 Restart bot$"), start),
                MessageHandler(filters.Regex("^Restart bot$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
            ],
            ADDRESS: [
                MessageHandler(filters.Regex("^Назад$"), back_to_count),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
                MessageHandler((filters.TEXT | filters.CONTACT) & ~filters.COMMAND, address_phone),
                MessageHandler(filters.Regex("^🔄 Restart bot$"), start),
                MessageHandler(filters.Regex("^Restart bot$"), start),
            ],
            CONFIRM: [
                MessageHandler(filters.Regex("^Назад$"), back_to_count),
                MessageHandler(filters.CONTACT, confirm_save_phone),
                MessageHandler(filters.Regex("^(Подтверждаю|Изменить адрес)$"), confirm_order),
                MessageHandler(filters.Regex("^🔄 Restart bot$"), start),
                MessageHandler(filters.Regex("^Restart bot$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order),
            ],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(filters.ALL, fallback)]
    )
    application.add_handler(conv_handler)
    log_console("Бот запущен")
    application.run_polling(drop_pending_updates=True)
