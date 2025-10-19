# Основной файл Telegram-бота для заказа обедов
# Для работы требуется заполнить BOT_TOKEN и ADMIN_ID


from config_secret import BOT_TOKEN, ADMIN_ID

# Дополнительные контакты оператора (опционально из config_secret)
try:
    from config_secret import OPERATOR_HANDLE
except Exception:
    OPERATOR_HANDLE = "@vitperson"

try:
    from config_secret import OPERATOR_PHONE
except Exception:
    OPERATOR_PHONE = "недоступен"

try:
    from config_secret import OPERATOR_INSTAGRAM
except Exception:
    OPERATOR_INSTAGRAM = ""

import logging
import json
import re
import secrets
from urllib.parse import urlparse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler, PicklePersistence
from keyboards import (
    add_start_button,
    get_main_menu_keyboard,
    get_main_menu_keyboard_admin,
    get_day_keyboard,
    get_count_keyboard,
    get_count_retry_keyboard,
    get_confirm_keyboard,
    get_contact_keyboard,
    get_address_keyboard,
    get_after_confirm_keyboard,
    get_admin_main_keyboard,
    get_admin_report_keyboard,
    get_duplicate_resolution_keyboard,
    get_weekly_duplicate_keyboard,
    get_admin_manage_menu_keyboard,
    get_admin_day_select_keyboard,
    get_admin_day_actions_keyboard,
    get_admin_confirm_keyboard,
    get_admin_back_keyboard,
)

from datetime import datetime, timedelta, date
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from telegram.error import NetworkError, TimedOut, RetryAfter, Forbidden, BadRequest
from logging.handlers import TimedRotatingFileHandler
import time
import os
import html
import asyncio

USERS_FILE = "users.json"
ORDERS_FILE = "orders.json"
ORDER_WINDOW_FILE = "order_window.json"
PRICE_LARI = 15

DAY_TO_INDEX = {
    "Понедельник": 0,
    "Вторник": 1,
    "Среда": 2,
    "Четверг": 3,
    "Пятница": 4,
}
INDEX_TO_DAY = {v: k for k, v in DAY_TO_INDEX.items()}
ORDER_CUTOFF_HOUR = 10  # Заказы на день принимаются до 10:00 этого дня

DAY_PHOTO_MAP = {
    "Понедельник": os.path.join("DishPhotos", "Monday.png"),
    "Вторник": os.path.join("DishPhotos", "Tuesday.png"),
    "Среда": os.path.join("DishPhotos", "Wednesday.png"),
    "Четверг": os.path.join("DishPhotos", "Thursday.png"),
    "Пятница": os.path.join("DishPhotos", "Friday.png"),
}

# Состояния для ConversationHandler
(
    MENU,
    ORDER_DAY,
    WEEKLY_DAY_PICK,
    ORDER_COUNT,
    UPDATE_ORDER_COUNT,
    ADDRESS,
    CONFIRM,
    DUPLICATE,
    WEEKLY_DUPLICATE,
    ADMIN_MENU,
    ADMIN_MENU_DAY_SELECT,
    ADMIN_MENU_ACTION,
    ADMIN_MENU_ITEM_SELECT,
    ADMIN_MENU_ITEM_TEXT,
    ADMIN_MENU_WEEK,
    ADMIN_MENU_PHOTO,
) = range(16)

# Настройка логирования с TimedRotatingFileHandler
logger = logging.getLogger()
logger.setLevel(logging.INFO)
# Храним логи в папке logs/
LOG_DIR = 'logs'
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except Exception:
    pass
log_handler = TimedRotatingFileHandler(
    os.path.join(LOG_DIR, 'bot.log'),
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


def save_menu(menu_data: dict) -> bool:
    try:
        tmp = "menu.json.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(menu_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, "menu.json")
        return True
    except Exception as e:
        logging.error(f"Не удалось сохранить menu.json: {e}")
        return False


def _get_current_menu() -> dict:
    data = load_menu()
    if not isinstance(data, dict):
        data = {"week": "", "menu": {}}
    data.setdefault("week", "")
    if not isinstance(data.get("menu"), dict):
        data["menu"] = {}
    return data


def _format_admin_menu(menu_data: dict) -> str:
    week = html.escape(str(menu_data.get("week") or "не указано"))
    lines = [f"<b>Неделя:</b> {week}"]
    window = _load_order_window()
    week_start_str = window.get("week_start")
    if window.get("next_week_enabled") and week_start_str:
        try:
            ws = date.fromisoformat(week_start_str)
            status = ws.strftime("приём открыт до старта недели %d.%m.%Y")
        except Exception:
            status = "приём открыт (дата старта неизвестна)"
    elif window.get("next_week_enabled"):
        status = "приём открыт (дата старта неизвестна)"
    else:
        status = "приём закрыт"
    lines.append(f"<i>Приём заказов на следующую неделю: {html.escape(status)}</i>")
    menu_block = menu_data.get("menu") or {}
    if not menu_block:
        lines.append("<i>Меню пока пустое.</i>")
        return "\n".join(lines)
    for day, items in menu_block.items():
        lines.append("")
        lines.append(f"<b>{html.escape(str(day))}</b>")
        if isinstance(items, list) and items:
            for idx, item in enumerate(items, start=1):
                lines.append(f"{idx}. {html.escape(str(item))}")
        else:
            lines.append("• (нет блюд)")
    return "\n".join(lines)


def _parse_menu_items(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            items.append(cleaned)
    if items:
        return items
    for part in text.split(","):
        cleaned = part.strip()
        if cleaned:
            items.append(cleaned)
    return items


def _is_day_available_for_order(day: str) -> tuple[bool, str | None, bool, date | None]:
    idx = DAY_TO_INDEX.get(day)
    if idx is None:
        return False, "Неверный день недели.", False, None
    now = datetime.now()
    today_idx = now.weekday()

    window = _load_order_window()
    week_start_str = window.get("week_start")
    next_week_enabled = bool(window.get("next_week_enabled"))
    week_start_date: date | None = None
    if week_start_str:
        try:
            week_start_date = date.fromisoformat(week_start_str)
        except Exception:
            week_start_date = None
            next_week_enabled = False
    today_date = now.date()
    next_week_active = False
    if next_week_enabled:
        if week_start_date and today_date < week_start_date:
            next_week_active = True
        else:
            _set_next_week_orders(False, None)
            next_week_enabled = False
            week_start_date = None

    current_week_start = _current_week_start(now)

    if idx < today_idx:
        if next_week_active and week_start_date is not None:
            return True, None, True, week_start_date
        return False, (
            f"Заказы на <b>{html.escape(day)}</b> уже закрыты для текущей недели. "
            "День снова станет доступен после обновления меню на следующую неделю (утро субботы)."
        ), False, current_week_start
    if idx == today_idx and now.hour >= ORDER_CUTOFF_HOUR:
        cutoff_str = f"{ORDER_CUTOFF_HOUR:02d}:00"
        return False, (
            f"Заказы на <b>{html.escape(day)}</b> принимаются до {cutoff_str} этого дня. "
            "Пожалуйста, выберите другой день недели."
        ), False, current_week_start

    target_week = week_start_date if next_week_active and week_start_date is not None else current_week_start
    return True, None, bool(next_week_active and week_start_date is not None), target_week


def _get_weekly_picker_state(context: ContextTypes.DEFAULT_TYPE) -> dict | None:
    state = context.user_data.get('weekly_picker_state')
    return state if isinstance(state, dict) else None


def _set_weekly_picker_state(context: ContextTypes.DEFAULT_TYPE, state: dict) -> None:
    context.user_data['weekly_picker_state'] = state


def _weekly_picker_selected(state: dict) -> list[str]:
    ordered_days: list[str] = state.get('ordered_days') or []
    selected_set = {str(day) for day in state.get('selection', [])}
    filtered = [day for day in ordered_days if day in selected_set]
    return filtered


def _weekly_picker_set_selection(state: dict, selected_days: list[str]) -> None:
    state['selection'] = list(selected_days)


def _weekly_picker_text(state: dict) -> str:
    week_label = str(state.get('week_label') or '').strip()
    lines: list[str] = []
    header = "<b>Пакетный заказ</b>"
    if week_label:
        header += f" — {html.escape(week_label)}"
    lines.append(header)
    lines.extend([
        "",
        "Отметьте дни, для которых хотите оформить заказ. После выбора нажмите «Продолжить».",
    ])
    selected = _weekly_picker_selected(state)
    if selected:
        lines.extend(["", "<b>Выбраны дни:</b>"])
        for day in selected:
            lines.append(f"• {html.escape(day)}")
    else:
        lines.extend(["", "Пока ничего не выбрано."])

    unavailable = state.get('unavailable') or []
    if unavailable:
        lines.extend(["", "<b>Недоступные дни:</b>"])
        for entry in unavailable:
            day = str((entry or {}).get('day') or '')
            warning = (entry or {}).get('warning')
            if warning:
                lines.append(str(warning))
            elif day:
                lines.append(f"• {html.escape(day)} — недоступно.")
    return "\n".join(lines)


def _weekly_picker_keyboard(state: dict) -> InlineKeyboardMarkup:
    selection = set(_weekly_picker_selected(state))
    buttons: list[list[InlineKeyboardButton]] = []
    ordered_days: list[str] = state.get('ordered_days') or []
    available: dict = state.get('available') or {}
    for day in ordered_days:
        if day not in available:
            continue
        is_selected = day in selection
        mark = "✅" if is_selected else "⬜️"
        idx = DAY_TO_INDEX.get(day)
        if idx is None:
            continue
        buttons.append([
            InlineKeyboardButton(
                text=f"{mark} {day}",
                callback_data=f"weekly_toggle:{idx}",
            )
        ])
    if buttons:
        buttons.append([
            InlineKeyboardButton("Выбрать все", callback_data="weekly_all"),
            InlineKeyboardButton("Снять все", callback_data="weekly_none"),
        ])
    buttons.append([InlineKeyboardButton("Продолжить", callback_data="weekly_continue")])
    buttons.append([InlineKeyboardButton("Отмена", callback_data="weekly_cancel")])
    return InlineKeyboardMarkup(buttons)


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


def _load_order_window() -> dict:
    default = {"next_week_enabled": False, "week_start": None}
    try:
        if not os.path.exists(ORDER_WINDOW_FILE):
            return default
        with open(ORDER_WINDOW_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return default
            result = default | data
            if not isinstance(result.get("next_week_enabled"), bool):
                result["next_week_enabled"] = False
            if result.get("week_start") and not isinstance(result.get("week_start"), str):
                result["week_start"] = None
            return result
    except Exception as e:
        logging.error(f"Не удалось загрузить {ORDER_WINDOW_FILE}: {e}")
        return default


def _save_order_window(data: dict) -> None:
    try:
        tmp = ORDER_WINDOW_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, ORDER_WINDOW_FILE)
    except Exception as e:
        logging.error(f"Не удалось сохранить {ORDER_WINDOW_FILE}: {e}")


def _next_week_start(now: datetime | None = None) -> date:
    now = now or datetime.now()
    days_ahead = (7 - now.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return (now + timedelta(days=days_ahead)).date()


def _set_next_week_orders(enabled: bool, week_start: date | None = None) -> None:
    payload = {
        "next_week_enabled": bool(enabled),
        "week_start": week_start.isoformat() if (enabled and week_start) else None,
    }
    _save_order_window(payload)


def _clear_weekly_context(context: ContextTypes.DEFAULT_TYPE) -> None:
    keys = [
        'weekly_mode',
        'weekly_days',
        'weekly_days_to_order',
        'weekly_menu',
        'pending_weekly_order',
        'weekly_duplicates',
        'weekly_duplicate_days',
        'weekly_picker_state',
    ]
    for key in keys:
        context.user_data.pop(key, None)


def _current_week_start(now: datetime | None = None) -> date:
    now = now or datetime.now()
    return (now - timedelta(days=now.weekday())).date()


def _build_order_actions_keyboard(order_id: str, allow_change: bool = True, allow_cancel: bool = True) -> InlineKeyboardMarkup | None:
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    if allow_change:
        row.append(InlineKeyboardButton("Изменить заказ", callback_data=f"change_order:{order_id}"))
    if allow_cancel:
        row.append(InlineKeyboardButton("Отменить этот заказ", callback_data=f"cancel_order:{order_id}"))
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons) if buttons else None


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


# Update status of an existing order
def set_order_status(order_id: str, new_status: str) -> bool:
    """Update status of an existing order. Returns True if changed."""
    data = _load_orders()
    if order_id not in data:
        return False
    data[order_id]["status"] = new_status
    _save_orders(data)
    return True


def get_order(order_id: str) -> dict | None:
    return _load_orders().get(order_id)

def find_user_order_same_day(uid: int, day_name: str, week_start: date | None = None) -> tuple[str, dict] | None:
    """Ищет активный (не отмененный) заказ пользователя на указанный день в текущую неделю.
    Возвращает пару (order_id, payload) с самым поздним созданием, либо None.
    """
    orders = _load_orders()
    now = datetime.now()
    if week_start is None:
        week_start = _current_week_start(now)
    start_dt = datetime.combine(week_start, datetime.min.time())
    end_dt = start_dt + timedelta(days=7) - timedelta(seconds=1)
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())
    best: tuple[str, dict] | None = None
    for oid, payload in orders.items():
        try:
            if int(payload.get("user_id") or 0) != int(uid):
                continue
        except Exception:
            continue
        dname = str(payload.get("day") or "")
        if dname != day_name:
            continue
        status = str(payload.get("status") or "").lower()
        if status.startswith("cancel"):
            continue
        ts = int(payload.get("created_at") or 0)
        delivery_week = payload.get('delivery_week_start')
        if delivery_week:
            try:
                delivery_week_date = date.fromisoformat(str(delivery_week))
            except Exception:
                delivery_week_date = None
            if delivery_week_date and delivery_week_date != week_start:
                continue
        else:
            if not (start_ts <= ts <= end_ts):
                continue
        if best is None or ts > int(best[1].get("created_at") or 0):
            best = (oid, payload)
    return best


def get_user_profile(uid: int) -> dict:
    data = _load_users()
    return data.get(str(uid), {})


def set_user_profile(uid: int, profile: dict) -> None:
    data = _load_users()
    data[str(uid)] = profile
    _save_users(data)


def ensure_user_registered(uid: int) -> None:
    """Гарантирует наличие записи пользователя в users.json."""
    data = _load_users()
    key = str(uid)
    if key not in data:
        data[key] = data.get(key, {})
        _save_users(data)


def get_broadcast_recipients() -> list[int]:
    """Собирает список chat_id для рассылки: все, кто есть в users.json и в orders.json. Админа исключаем."""
    uids: set[int] = set()
    try:
        for k in _load_users().keys():
            try:
                uids.add(int(k))
            except Exception:
                pass
    except Exception:
        pass
    try:
        for _, payload in _load_orders().items():
            uid = payload.get("user_id")
            if uid is not None:
                try:
                    uids.add(int(uid))
                except Exception:
                    pass
    except Exception:
        pass
    try:
        uids.discard(int(ADMIN_ID))
    except Exception:
        pass
    return sorted(uids)

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


# --- Admin menu management helper flows ---


async def admin_manage_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return MENU

    context.user_data.pop('admin_menu_day', None)
    context.user_data.pop('admin_menu_action', None)

    menu_data = _get_current_menu()
    overview = _format_admin_menu(menu_data)
    text = (
        "<b>Управление меню</b>\n\n"
        "Отсюда можно обновить название недели, блюда по дням и фотографию меню.\n\n"
        f"{overview}"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_manage_menu_keyboard(),
    )
    return ADMIN_MENU


async def admin_menu_show_day_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return MENU
    menu_data = _get_current_menu()
    days = list(menu_data.get('menu', {}).keys())
    if not days:
        await update.message.reply_text(
            "Меню пока не заполнено. Отредактируйте файл menu.json и попробуйте снова.",
            reply_markup=get_admin_manage_menu_keyboard(),
        )
        return ADMIN_MENU
    await update.message.reply_text(
        "Выберите день, который хотите отредактировать.",
        reply_markup=get_admin_day_select_keyboard(days),
    )
    return ADMIN_MENU_DAY_SELECT


async def admin_menu_day_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return MENU
    day = (update.message.text or "").strip()
    menu_data = _get_current_menu()
    menu_block = menu_data.get('menu', {})
    if day not in menu_block:
        await update.message.reply_text(
            "Пожалуйста, выберите день из предложенного списка.",
            reply_markup=get_admin_day_select_keyboard(list(menu_block.keys())),
        )
        return ADMIN_MENU_DAY_SELECT
    context.user_data['admin_menu_day'] = day

    context.user_data.pop('admin_menu_action', None)
    items = menu_block.get(day) or []
    lines = [f"<b>{html.escape(day)}</b>"]
    if items:
        for idx, item in enumerate(items, start=1):
            lines.append(f"{idx}. {html.escape(str(item))}")
    else:
        lines.append("(Блюда не указаны)")
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_day_actions_keyboard(),
    )
    return ADMIN_MENU_ACTION


async def admin_menu_request_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return MENU
    await update.message.reply_text(
        "Отправьте новую фотографию меню (как фото или как изображение-файл).",
        reply_markup=get_admin_back_keyboard(),
    )
    return ADMIN_MENU_PHOTO


async def admin_menu_request_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return MENU
    current_week = str((_get_current_menu()).get('week') or "")
    prompt = "Введите новое название недели."
    if current_week:
        prompt += f"\nТекущее значение: {current_week}"
    await update.message.reply_text(
        prompt,
        reply_markup=get_admin_back_keyboard(),
    )
    return ADMIN_MENU_WEEK


async def admin_open_next_week_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return MENU

    window = _load_order_window()
    week_start_str = window.get('week_start')
    if window.get('next_week_enabled') and week_start_str:
        try:
            ws = date.fromisoformat(week_start_str)
            formatted = ws.strftime('%d.%m.%Y')
        except Exception:
            formatted = week_start_str
        await update.message.reply_text(
            f"Приём заказов уже открыт на неделю, начинающуюся {formatted}.",
        )
        return await admin_manage_menu(update, context)

    week_start = _next_week_start()
    _set_next_week_orders(True, week_start)
    formatted = week_start.strftime('%d.%m.%Y')
    await update.message.reply_text(
        (
            "✅ Приём заказов на следующую неделю открыт.\n"
            f"Первая дата доставки: {formatted}."
        ),
    )
    return await admin_manage_menu(update, context)


async def admin_menu_day_action_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['admin_menu_action'] = 'add'
    await update.message.reply_text(
        "Введите текст нового блюда.",
        reply_markup=get_admin_back_keyboard(),
    )
    return ADMIN_MENU_ITEM_TEXT


async def admin_menu_day_action_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = context.user_data.get('admin_menu_day')
    menu_data = _get_current_menu()
    items = menu_data.get('menu', {}).get(day) or []
    if not items:
        await update.message.reply_text(
            "Для этого дня пока нет блюд. Добавьте блюдо, чтобы его можно было изменить.",
            reply_markup=get_admin_day_actions_keyboard(),
        )
        return ADMIN_MENU_ACTION
    listing = [f"{idx}. {item}" for idx, item in enumerate(items, start=1)]
    await update.message.reply_text(
        "Укажите номер блюда, которое нужно изменить:\n" + "\n".join(listing),
        reply_markup=get_admin_back_keyboard(),
    )
    context.user_data['admin_menu_action'] = 'edit'
    return ADMIN_MENU_ITEM_SELECT


async def admin_menu_day_action_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = context.user_data.get('admin_menu_day')
    menu_data = _get_current_menu()
    items = menu_data.get('menu', {}).get(day) or []
    if not items:
        await update.message.reply_text(
            "Для этого дня пока нет блюд, удалять нечего.",
            reply_markup=get_admin_day_actions_keyboard(),
        )
        return ADMIN_MENU_ACTION
    listing = [f"{idx}. {item}" for idx, item in enumerate(items, start=1)]
    await update.message.reply_text(
        "Укажите номер блюда, которое нужно удалить:\n" + "\n".join(listing),
        reply_markup=get_admin_back_keyboard(),
    )
    context.user_data['admin_menu_action'] = 'delete'
    return ADMIN_MENU_ITEM_SELECT


async def admin_menu_day_action_replace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['admin_menu_action'] = 'replace'
    await update.message.reply_text(
        (
            "Отправьте новый список блюд для выбранного дня.\n"
            "Каждое блюдо — с новой строки (или через запятую)."
        ),
        reply_markup=get_admin_back_keyboard(),
    )
    return ADMIN_MENU_ITEM_TEXT


async def admin_menu_handle_item_index(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return MENU
    action = context.user_data.get('admin_menu_action')
    if action not in {'edit', 'delete'}:
        return await admin_manage_menu(update, context)
    text = (update.message.text or "").strip()
    if not text.isdigit():
        await update.message.reply_text(
            "Введите номер блюда цифрой.",
            reply_markup=get_admin_back_keyboard(),
        )
        return ADMIN_MENU_ITEM_SELECT
    index = int(text) - 1
    day = context.user_data.get('admin_menu_day')
    menu_data = _get_current_menu()
    items = menu_data.get('menu', {}).get(day) or []
    if index < 0 or index >= len(items):
        await update.message.reply_text(
            "Неверный номер. Попробуйте снова.",
            reply_markup=get_admin_back_keyboard(),
        )
        return ADMIN_MENU_ITEM_SELECT

    if action == 'edit':
        context.user_data['admin_menu_item_index'] = index
        await update.message.reply_text(
            "Введите новый текст блюда.",
            reply_markup=get_admin_back_keyboard(),
        )
        return ADMIN_MENU_ITEM_TEXT

    removed = items.pop(index)
    menu_data['menu'][day] = items
    if save_menu(menu_data):
        await update.message.reply_text(
            f"Блюдо удалено: {html.escape(str(removed))}",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text("Не удалось сохранить изменения. Попробуйте позже.")
    context.user_data.pop('admin_menu_action', None)
    context.user_data.pop('admin_menu_item_index', None)
    return await admin_menu_back_to_day_actions(update, context)


async def admin_menu_handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return MENU
    action = context.user_data.get('admin_menu_action')
    text = (update.message.text or "").strip()

    if action == 'add':
        if not text:
            await update.message.reply_text(
                "Текст не может быть пустым. Введите блюдо.",
                reply_markup=get_admin_back_keyboard(),
            )
            return ADMIN_MENU_ITEM_TEXT
        day = context.user_data.get('admin_menu_day')
        menu_data = _get_current_menu()
        menu_data.setdefault('menu', {}).setdefault(day, []).append(text)
        if save_menu(menu_data):
            await update.message.reply_text("Блюдо добавлено.")
        else:
            await update.message.reply_text("Не удалось сохранить изменения. Попробуйте позже.")
        context.user_data.pop('admin_menu_action', None)
        return await admin_menu_back_to_day_actions(update, context)

    if action == 'edit':
        if not text:
            await update.message.reply_text(
                "Текст не может быть пустым.",
                reply_markup=get_admin_back_keyboard(),
            )
            return ADMIN_MENU_ITEM_TEXT
        day = context.user_data.get('admin_menu_day')
        index = context.user_data.get('admin_menu_item_index')
        menu_data = _get_current_menu()
        items = menu_data.get('menu', {}).get(day)
        if items is None or index is None or index < 0 or index >= len(items):
            await update.message.reply_text("Не удалось обновить блюдо. Попробуйте снова.")
            return await admin_manage_menu(update, context)
        items[index] = text
        if save_menu(menu_data):
            await update.message.reply_text("Блюдо обновлено.")
        else:
            await update.message.reply_text("Не удалось сохранить изменения. Попробуйте позже.")
        context.user_data.pop('admin_menu_action', None)
        context.user_data.pop('admin_menu_item_index', None)
        return await admin_menu_back_to_day_actions(update, context)

    if action == 'replace':
        day = context.user_data.get('admin_menu_day')
        items = _parse_menu_items(text)
        menu_data = _get_current_menu()
        menu_data.setdefault('menu', {})[day] = items
        if save_menu(menu_data):
            await update.message.reply_text("Список обновлен.")
        else:
            await update.message.reply_text("Не удалось сохранить изменения. Попробуйте позже.")
        context.user_data.pop('admin_menu_action', None)
        return await admin_menu_back_to_day_actions(update, context)

    if action == 'set_week':
        menu_data = _get_current_menu()
        menu_data['week'] = text
        if save_menu(menu_data):
            await update.message.reply_text("Название недели обновлено.")
        else:
            await update.message.reply_text("Не удалось сохранить изменения. Попробуйте позже.")
        context.user_data.pop('admin_menu_action', None)
        return await admin_manage_menu(update, context)

    return await admin_manage_menu(update, context)


async def admin_menu_save_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['admin_menu_action'] = 'set_week'
    return await admin_menu_handle_text_input(update, context)


async def admin_menu_handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return MENU
    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document and str(update.message.document.mime_type or "").startswith("image/"):
        file_id = update.message.document.file_id
    if not file_id:
        await update.message.reply_text(
            "Отправьте фотографию или изображение (можно как файл).",
            reply_markup=get_admin_back_keyboard(),
        )
        return ADMIN_MENU_PHOTO
    try:
        file = await context.bot.get_file(file_id)
        target_path = "Menu.jpeg"
        tmp_path = target_path + ".tmp"
        await file.download_to_drive(tmp_path)
        os.replace(tmp_path, target_path)
    except Exception as e:
        logging.error(f"Не удалось обновить фото меню: {e}")
        await update.message.reply_text("Не вышло сохранить фото. Попробуйте еще раз.")
        return ADMIN_MENU_PHOTO
    await update.message.reply_text(
        "Фото меню обновлено.",
        reply_markup=get_admin_manage_menu_keyboard(),
    )
    return ADMIN_MENU


async def admin_menu_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await admin_manage_menu(update, context)


async def admin_menu_back_to_day_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = context.user_data.get('admin_menu_day')
    if not day:
        return await admin_manage_menu(update, context)
    menu_data = _get_current_menu()
    items = menu_data.get('menu', {}).get(day) or []
    lines = [f"<b>{html.escape(day)}</b>"]
    if items:
        for idx, item in enumerate(items, start=1):
            lines.append(f"{idx}. {html.escape(str(item))}")
    else:
        lines.append("(Блюда не указаны)")
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_day_actions_keyboard(),
    )
    return ADMIN_MENU_ACTION


async def admin_menu_back_to_day_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_data = _get_current_menu()
    days = list(menu_data.get('menu', {}).keys())
    if not days:
        return await admin_manage_menu(update, context)
    await update.message.reply_text(
        "Выберите день.",
        reply_markup=get_admin_day_select_keyboard(days),
    )
    return ADMIN_MENU_DAY_SELECT


async def admin_menu_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return MENU
    await update.message.reply_text(
        "Режим администратора.",
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_main_keyboard(),
    )
    return MENU

# Стартовая команда
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_action(update.message.from_user, "start")
    # Сброс состояния и user_data
    # Сохраним флаг режима админа, если был
    prev_admin_ui = context.user_data.get('admin_ui', True)
    context.user_data.clear()
    context.user_data['admin_ui'] = prev_admin_ui
    is_admin = update.effective_user.id == ADMIN_ID
    admin_ui = context.user_data.get('admin_ui', True)
    if is_admin and admin_ui:
        admin_caption = (
            "<b>Режим администратора</b>\n\n"
            "📊 <b>Отчеты</b>:\n"
            "1) Нажмите «Показать заказы на эту неделю».\n"
            "2) Выберите «Неделя целиком» или нужный день.\n"
            "3) Детали заказа: отправьте <code>/order ID</code>.\n\n"
            "📣 <b>Рассылка</b>: <code>/sms текст</code>"
        )
        try:
            with open("Admin.png", "rb") as logo:
                await update.message.reply_photo(
                    photo=logo,
                    caption=admin_caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_admin_main_keyboard(),
                )
        except FileNotFoundError:
            await update.message.reply_text(
                admin_caption,
                reply_markup=get_admin_main_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        return MENU
    # Подтягиваем сохраненный профиль из users.json, если есть
    saved_profile = get_user_profile(update.effective_user.id)
    if saved_profile:
        context.user_data["profile"] = saved_profile
    # Регистрируем пользователя для последующих рассылок
    ensure_user_registered(update.effective_user.id)
    log_console("Пользователь начал работу с ботом")

    contacts = _prepare_operator_contacts()
    contact_links: list[str] = []
    if contacts["handle"]:
        handle = contacts["handle"]
        contact_links.append(
            f"<a href=\"https://t.me/{html.escape(handle)}\">@{html.escape(handle)}</a>"
        )
    if contacts["phone_href"]:
        phone_display = contacts["phone_display"] or contacts["phone_href"]
        contact_links.append(
            f"<a href=\"tel:{html.escape(contacts['phone_href'])}\">{html.escape(phone_display)}</a>"
        )
    if contacts["instagram_url"]:
        contact_links.append(
            f"<a href=\"{html.escape(contacts['instagram_url'])}\">{html.escape(contacts['instagram_label'])}</a>"
        )
    if contact_links:
        contact_line = "• Связаться с оператором " + " / ".join(contact_links)
    else:
        contact_line = "• Связаться с оператором — контакты временно недоступны"

    greeting_caption = (
        "<b>Привет! Я Batumi Lunch Bot 👋</b>\n"
        "🥗 Домашние обеды с доставкой по Батуми\n"
        "💸 15 лари за порцию, доставка бесплатная"
    )
    details_text = (
        "Каждый обед: мясо 110 г • гарнир 300 г • салат 250 г\n"
        "Готовим и привозим в будни с 12:30 до 15:30"
    )
    actions_text = (
        "Готов помочь:\n"
        "• Посмотреть меню недели\n"
        "• Принять заказ\n"
        f"{contact_line}\n\n"
        "Выберите действие на клавиатуре ниже 👇"
    )

    try:
        with open("Logo.png", "rb") as logo:
            await update.message.reply_photo(
                photo=logo,
                caption=greeting_caption,
                parse_mode=ParseMode.HTML,
            )
    except FileNotFoundError:
        await update.message.reply_text(
            greeting_caption,
            parse_mode=ParseMode.HTML,
        )

    await update.message.reply_text(details_text, parse_mode=ParseMode.HTML)

    await update.message.reply_text(
        actions_text,
        parse_mode=ParseMode.HTML,
        reply_markup=(get_main_menu_keyboard_admin() if is_admin else get_main_menu_keyboard()),
    )
    return MENU


async def admin_show_week_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return MENU

    await update.message.reply_text(
        "<b>Выберите отчет:</b>\nНеделя целиком или конкретный день.",
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_report_keyboard(),
    )
    return MENU


async def admin_report_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return MENU

    selection = (update.message.text or "").strip()
    if selection not in {"Неделя целиком", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница"}:
        await update.message.reply_text("Выберите вариант из клавиатуры.", reply_markup=get_admin_report_keyboard())
        return MENU

    day_filter = None if selection == "Неделя целиком" else selection

    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    start_dt = datetime(monday.year, monday.month, monday.day, 0, 0, 0)
    end_dt = start_dt + timedelta(days=6, hours=23, minutes=59, seconds=59)
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    orders = _load_orders()
    week_orders_active = []
    week_orders_cancelled = []

    for oid, payload in orders.items():
        ts = int(payload.get("created_at") or 0)
        dname = str(payload.get("day") or "")
        if not (start_ts <= ts <= end_ts):
            continue
        if day_filter is not None and dname != day_filter:
            continue
        status = str(payload.get("status") or "").lower()
        p = dict(payload)
        p["__id"] = oid
        p["__status"] = status
        if status.startswith("cancel"):
            week_orders_cancelled.append(p)
        else:
            week_orders_active.append(p)

    day_order = {"Понедельник":0, "Вторник":1, "Среда":2, "Четверг":3, "Пятница":4, "Суббота":5, "Воскресенье":6}
    sort_key = lambda x: (day_order.get(str(x.get("day")), 99), int(x.get("created_at") or 0))
    week_orders_active.sort(key=sort_key)
    week_orders_cancelled.sort(key=sort_key)

    totals_by_day = {}
    cancelled_by_day = {}
    grand = 0

    def _count_int(v):
        try:
            return int(str(v).split()[0])
        except Exception:
            return 1

    for o in week_orders_active:
        cnt = _count_int(o.get("count", 1))
        grand += cnt
        d = str(o.get("day") or "-")
        b = totals_by_day.setdefault(d, {"count": 0, "items": []})
        b["count"] += cnt
        b["items"].append(o)

    for o in week_orders_cancelled:
        d = str(o.get("day") or "-")
        b = cancelled_by_day.setdefault(d, [])
        b.append(o)

    menu_data = load_menu() or {}
    week_label = menu_data.get("week") or "эта неделя"

    if day_filter:
        header = f"<b>📊 Заказы за день:</b> {html.escape(day_filter)}"
    else:
        header = f"<b>📊 Заказы за неделю:</b> {html.escape(str(week_label))}"

    lines = [header]
    if not week_orders_active and not week_orders_cancelled:
        lines.append("Заказов пока нет.")
    else:
        days_iter = [day_filter] if day_filter else ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        for d_name in days_iter:
            active_block = totals_by_day.get(d_name)
            cancelled_block = cancelled_by_day.get(d_name, [])
            if not active_block and not cancelled_block:
                continue

            # Активные
            if active_block:
                day_sum = active_block["count"] * PRICE_LARI
                lines.append(f"\n<b>{html.escape(d_name)}</b> - {active_block['count']} шт. / {day_sum} лари")
                for o in active_block["items"]:
                    oid = o.get("__id")
                    cnt = _count_int(o.get("count", 1))
                    addr_txt = str(o.get("address") or "-").strip()
                    uid = int(o.get("user_id") or 0)
                    uname = o.get("username") or ""
                    uname_tag = f"@{uname}" if uname else ""
                    cust = f"<a href=\"tg://user?id={uid}\">{uid}</a>" if uid else "-"
                    username_part = f" {html.escape(uname_tag)}" if uname_tag else ""
                    lines.append(f"• <code>/order {html.escape(oid)}</code> ×{cnt} - {html.escape(addr_txt)} - {cust}{username_part}")

            # Отмененные (не входят в итоги)
            if cancelled_block:
                lines.append(f"<i>❌ Отмененные ({html.escape(d_name)})</i>")
                for o in cancelled_block:
                    oid = o.get("__id")
                    cnt = _count_int(o.get("count", 1))
                    addr_txt = str(o.get("address") or "-").strip()
                    uid = int(o.get("user_id") or 0)
                    uname = o.get("username") or ""
                    uname_tag = f"@{uname}" if uname else ""
                    cust = f"<a href=\"tg://user?id={uid}\">{uid}</a>" if uid else "-"
                    username_part = f" {html.escape(uname_tag)}" if uname_tag else ""
                    lines.append(f"• <s><code>/order {html.escape(oid)}</code> ×{cnt} - {html.escape(addr_txt)} - {cust}{username_part}</s>")

        lines.append(f"\n<b>Итого (без отмененных):</b> {grand} шт. / {grand*PRICE_LARI} лари")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=get_admin_report_keyboard())
    return MENU

# --- Переключение интерфейса админа ---
async def switch_to_user_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ переключается в пользовательский интерфейс."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return MENU
    context.user_data['admin_ui'] = False
    await update.message.reply_text(
        "Переключено в режим пользователя.",
        reply_markup=get_main_menu_keyboard_admin(),
    )
    return MENU

async def switch_to_admin_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ переключается обратно в админский интерфейс."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return MENU
    context.user_data['admin_ui'] = True
    admin_caption = (
        "<b>Режим администратора</b>\n\n"
        "📊 <b>Отчеты</b>: воспользуйтесь кнопкой ниже.\n"
        "📣 <b>Рассылка</b>: /sms <i>текст</i>"
    )
    await update.message.reply_text(
        admin_caption,
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_main_keyboard(),
    )
    return MENU

# --- Мои текущие заказы (для пользователя) ---
def _ru_obed_plural(n: int) -> str:
    n = abs(n) % 100
    n1 = n % 10
    if 11 <= n <= 19:
        return "обедов"
    if n1 == 1:
        return "обед"
    if 2 <= n1 <= 4:
        return "обеда"
    return "обедов"

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает заказы на текущую или следующую неделю в зависимости от статуса приёма."""
    user = update.effective_user
    uid = user.id

    now = datetime.now()
    today_idx = now.weekday()  # 0..6

    window = _load_order_window()
    show_next_week = False
    target_week_start = _current_week_start(now)
    week_start_str = window.get('week_start')
    if window.get('next_week_enabled') and week_start_str:
        try:
            ws = date.fromisoformat(week_start_str)
            if now.date() < ws:
                show_next_week = True
                target_week_start = ws
            else:
                _set_next_week_orders(False, None)
        except Exception:
            _set_next_week_orders(False, None)

    start_dt = datetime.combine(target_week_start, datetime.min.time())
    end_dt = start_dt + timedelta(days=7) - timedelta(seconds=1)
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    orders = _load_orders()
    mine: list[dict] = []
    for oid, payload in orders.items():
        try:
            if int(payload.get("user_id") or 0) != uid:
                continue
        except Exception:
            continue
        status = str(payload.get("status") or "").lower()
        if status.startswith("cancel"):
            continue
        dname = str(payload.get("day") or "")
        didx = DAY_TO_INDEX.get(dname, 99)
        if didx > 4:
            continue
        delivery_week = payload.get("delivery_week_start")
        if delivery_week:
            try:
                delivery_week_date = date.fromisoformat(str(delivery_week))
            except Exception:
                delivery_week_date = None
        else:
            delivery_week_date = None

        ts = int(payload.get("created_at") or 0)
        if show_next_week:
            if delivery_week_date != target_week_start:
                continue
        else:
            if delivery_week_date and delivery_week_date != target_week_start:
                continue
            if not delivery_week_date and not (start_ts <= ts <= end_ts):
                continue
            if didx < today_idx:
                continue

        item = dict(payload)
        item["__id"] = oid
        item["__didx"] = didx
        item["__ts"] = ts
        mine.append(item)

    if not mine:
        msg = "У вас нет заказов на следующую неделю." if show_next_week else "У вас нет актуальных заказов на эту неделю."
        await update.message.reply_text(msg)
        return MENU

    mine.sort(key=lambda x: (x.get("__didx", 99), x.get("__ts", 0)))

    if show_next_week:
        header_parts = ["🧾 <b>Заказы на следующую неделю</b>", f"<i>Неделя начинается {target_week_start.strftime('%d.%m.%Y')}</i>"]
    else:
        header_parts = ["🧾 <b>Ваши текущие заказы</b>"]
        try:
            md = load_menu() or {}
            if md.get("week"):
                header_parts.append(f"<i>Неделя:</i> {html.escape(str(md.get('week')))}")
        except Exception:
            pass

    lines = ["\n".join(header_parts)]

    for i, o in enumerate(mine, start=1):
        dname = str(o.get("day") or "")
        didx = o.get("__didx", 99)
        is_today = (didx == today_idx)
        raw_count = o.get("count", 1)
        try:
            count_int = int(str(raw_count).split()[0])
        except Exception:
            count_int = 1

        title = f"{i}. <b>{html.escape(dname)}</b>"
        if is_today and not show_next_week:
            title += " <i>(сегодня)</i>"
        title += f": <b>{count_int} {_ru_obed_plural(count_int)}</b>"
        lines.append(title)

        menu_val = o.get("menu")
        if isinstance(menu_val, list):
            items = [str(x).strip() for x in menu_val if str(x).strip()]
        else:
            items = [s.strip() for s in str(menu_val or '').split(',') if s.strip()]
        if items:
            for it in items:
                lines.append(f"• {html.escape(it)}")

        order_id = o.get('__id') or ''
        lines.append(f"<code>/order {html.escape(order_id)}</code>")
        lines.append("")

    await update.message.reply_text("\n".join(lines).rstrip(), parse_mode=ParseMode.HTML)
    return MENU

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админская рассылка: /sms <текст>. Поддерживается HTML-разметка."""
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Недоступно.")
        return

    # Текст берем из аргументов команды
    text = " ".join(context.args) if getattr(context, "args", None) else ""
    if not text:
        await update.message.reply_text("Использование: /sms <текст>\nМожно использовать HTML-разметку.")
        return

    recipients = get_broadcast_recipients()
    if not recipients:
        await update.message.reply_text("Нет получателей для рассылки.")
        return

    sent = 0
    failed = 0
    for uid in recipients:
        try:
            await context.bot.send_message(chat_id=uid, text=text, parse_mode=ParseMode.HTML)
            sent += 1
        except Exception as e:
            logging.warning(f"Broadcast failed for {uid}: {e}")
            failed += 1
        await asyncio.sleep(0.05)  # анти-спам лимиты Telegram

    await update.message.reply_text(
        f"Рассылка завершена: отправлено {sent}, ошибок {failed}. Получателей: {len(recipients)}.")


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = (update.effective_user.id == ADMIN_ID)
    if is_admin and context.user_data.get('admin_ui', True):
        await update.message.reply_text(
            "Вы админ. Используйте кнопку: Показать заказы на эту неделю.",
            reply_markup=get_admin_main_keyboard(),
        )
        return MENU
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
    await update.message.reply_text(
        "<b>Выберите день недели:</b>", parse_mode=ParseMode.HTML, reply_markup=get_day_keyboard()
    )
    return ORDER_DAY

# Обработка кнопки "Заказать обед" или "Да"
async def order_lunch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = (update.effective_user.id == ADMIN_ID)
    if is_admin and context.user_data.get('admin_ui', True):
        await update.message.reply_text(
            "Вы админ. Используйте кнопку: Показать заказы на эту неделю.",
            reply_markup=get_admin_main_keyboard(),
        )
        return MENU
    log_user_action(update.message.from_user, "order_lunch")
    _clear_weekly_context(context)
    context.user_data.pop('order_for_next_week', None)
    context.user_data.pop('order_week_start', None)
    await update.message.reply_text("<b>Выберите день недели:</b>", parse_mode=ParseMode.HTML, reply_markup=get_day_keyboard())
    return ORDER_DAY
async def order_week_lunch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = (update.effective_user.id == ADMIN_ID)
    if is_admin and context.user_data.get('admin_ui', True):
        await update.message.reply_text(
            "Вы админ. Используйте кнопку: Показать заказы на эту неделю.",
            reply_markup=get_admin_main_keyboard(),
        )
        return MENU
    log_user_action(update.message.from_user, "order_week_lunch")
    menu_data = load_menu()
    main_keyboard = get_main_menu_keyboard_admin() if is_admin else get_main_menu_keyboard()
    if not menu_data or not isinstance(menu_data.get('menu'), dict) or not menu_data['menu']:
        await update.message.reply_text(
            "Меню недели пока не заполнено. Попросите администратора обновить меню.",
            reply_markup=main_keyboard,
        )
        return MENU

    menu_block = menu_data['menu']
    ordered_days = [day for day in DAY_TO_INDEX if day in menu_block]
    if not ordered_days:
        await update.message.reply_text(
            "Меню на неделю пока отсутствует. Попросите администратора обновить меню.",
            reply_markup=main_keyboard,
        )
        return MENU

    _clear_weekly_context(context)
    context.user_data.pop('pending_order', None)
    context.user_data.pop('selected_day', None)

    available_info: dict[str, dict] = {}
    unavailable: list[dict] = []
    for day in ordered_days:
        allowed, warning, is_next_week, week_start_date = _is_day_available_for_order(day)
        items = menu_block.get(day)
        if isinstance(items, list):
            prepared = [str(it).strip() for it in items if str(it).strip()]
        else:
            prepared = [str(items).strip()] if str(items).strip() else []
        if allowed:
            available_info[day] = {
                'is_next_week': bool(is_next_week),
                'week_start': week_start_date.isoformat() if week_start_date else None,
                'menu': prepared,
            }
        else:
            unavailable.append({'day': day, 'warning': warning})

    if not available_info:
        lines = [
            "Пакетный заказ недоступен: на этой неделе нет открытых дней.",
        ]
        if unavailable:
            lines.append("")
            lines.append("<b>Причины:</b>")
            for entry in unavailable:
                warning = entry.get('warning')
                day = entry.get('day')
                if warning:
                    lines.append(str(warning))
                elif day:
                    lines.append(f"• {html.escape(day)} — недоступно.")
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard,
        )
        return MENU

    picker_state = {
        'ordered_days': ordered_days,
        'available': available_info,
        'unavailable': unavailable,
        'week_label': menu_data.get('week') or '',
        'selection': [],
    }
    _set_weekly_picker_state(context, picker_state)

    message_text = _weekly_picker_text(picker_state)
    await update.message.reply_text(
        message_text,
        parse_mode=ParseMode.HTML,
        reply_markup=_weekly_picker_keyboard(picker_state),
    )
    return WEEKLY_DAY_PICK


async def _weekly_picker_refresh_message(query, state: dict) -> None:
    message_text = _weekly_picker_text(state)
    try:
        await query.edit_message_text(
            message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=_weekly_picker_keyboard(state),
        )
    except BadRequest as exc:
        if 'Message is not modified' in str(exc):
            return
        raise


async def weekly_picker_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    log_user_action(query.from_user, f"weekly_picker_toggle:{query.data}")
    state = _get_weekly_picker_state(context)
    if not state:
        await query.edit_message_text("Выбор дней устарел. Начните заново /start.")
        return MENU
    try:
        _, idx_str = query.data.split(":", 1)
        idx = int(idx_str)
    except Exception:
        return WEEKLY_DAY_PICK
    day = INDEX_TO_DAY.get(idx)
    available = state.get('available') or {}
    if not day or day not in available:
        return WEEKLY_DAY_PICK
    current = set(_weekly_picker_selected(state))
    if day in current:
        current.remove(day)
    else:
        current.add(day)
    ordered_days: list[str] = state.get('ordered_days') or []
    new_selection = [d for d in ordered_days if d in current and d in available]
    _weekly_picker_set_selection(state, new_selection)
    await _weekly_picker_refresh_message(query, state)
    return WEEKLY_DAY_PICK


async def weekly_picker_select_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    log_user_action(query.from_user, "weekly_picker_select_all")
    state = _get_weekly_picker_state(context)
    if not state:
        await query.edit_message_text("Выбор дней устарел. Начните заново /start.")
        return MENU
    ordered_days: list[str] = state.get('ordered_days') or []
    available = state.get('available') or {}
    new_selection = [day for day in ordered_days if day in available]
    _weekly_picker_set_selection(state, new_selection)
    await _weekly_picker_refresh_message(query, state)
    return WEEKLY_DAY_PICK


async def weekly_picker_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    log_user_action(query.from_user, "weekly_picker_clear")
    state = _get_weekly_picker_state(context)
    if not state:
        await query.edit_message_text("Выбор дней устарел. Начните заново /start.")
        return MENU
    _weekly_picker_set_selection(state, [])
    await _weekly_picker_refresh_message(query, state)
    return WEEKLY_DAY_PICK


async def weekly_picker_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    log_user_action(query.from_user, "weekly_picker_cancel")
    _clear_weekly_context(context)
    context.user_data.pop('weekly_picker_state', None)
    try:
        await query.edit_message_text("Пакетное оформление отменено.")
    except BadRequest as exc:
        if 'Message is not modified' not in str(exc):
            raise
    keyboard = get_main_menu_keyboard_admin() if query.from_user.id == ADMIN_ID else get_main_menu_keyboard()
    await query.message.reply_text(
        "Пакетное оформление отменено.",
        reply_markup=keyboard,
    )
    return MENU


async def weekly_picker_continue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    log_user_action(query.from_user, "weekly_picker_continue")
    state = _get_weekly_picker_state(context)
    if not state:
        await query.answer()
        await query.edit_message_text("Выбор дней устарел. Начните заново /start.")
        return MENU
    selected_days = _weekly_picker_selected(state)
    if not selected_days:
        await query.answer("Выберите хотя бы один день.", show_alert=True)
        return WEEKLY_DAY_PICK
    await query.answer()

    available = state.get('available') or {}
    week_starts = [available[day].get('week_start') for day in selected_days if day in available]
    target_week_iso = next((ws for ws in week_starts if ws), None)
    if target_week_iso:
        try:
            target_week = date.fromisoformat(str(target_week_iso))
        except Exception:
            target_week = _current_week_start()
            target_week_iso = target_week.isoformat()
    else:
        target_week = _current_week_start()
        target_week_iso = target_week.isoformat()

    is_next_week_delivery = any(available.get(day, {}).get('is_next_week') for day in selected_days)

    weekly_menu: dict[str, list[str]] = {
        day: available.get(day, {}).get('menu', [])
        for day in selected_days
    }

    context.user_data['weekly_mode'] = True
    context.user_data['weekly_days'] = selected_days
    context.user_data['weekly_days_to_order'] = list(selected_days)
    context.user_data['weekly_menu'] = weekly_menu
    context.user_data['order_for_next_week'] = bool(is_next_week_delivery)
    context.user_data['order_week_start'] = target_week_iso
    context.user_data.pop('selected_count', None)
    context.user_data.pop('pending_weekly_order', None)
    context.user_data.pop('weekly_duplicates', None)
    context.user_data.pop('weekly_duplicate_days', None)

    try:
        await query.edit_message_text(
            "Дни выбраны. Укажите количество обедов на клавиатуре.",
            parse_mode=ParseMode.HTML,
        )
    except BadRequest as exc:
        if 'Message is not modified' not in str(exc):
            raise

    week_label = str(state.get('week_label') or '')
    lines: list[str] = ["<b>Заказ на выбранные дни</b>"]
    if week_label:
        lines.append(f"<i>Неделя:</i> {html.escape(week_label)}")
    if target_week:
        if is_next_week_delivery:
            lines.append(f"🗓️ Доставка с {target_week.strftime('%d.%m.%Y')} (следующая неделя)")
        else:
            lines.append(f"🗓️ Неделя начинается {target_week.strftime('%d.%m.%Y')}")
    menu_html = _build_weekly_menu_html(selected_days, weekly_menu)
    if menu_html:
        lines.extend(["", menu_html])
    lines.extend(["", "<b>Сколько обедов в день оформить?</b>"])
    message_text = "\n".join(lines)

    await query.message.reply_text(
        message_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_count_keyboard(),
    )
    return ORDER_COUNT


def _build_weekly_menu_html(days: list[str], menu_map: dict[str, list[str]]) -> str:
    blocks: list[str] = []
    for day in days:
        lines = [f"<b>{html.escape(day)}</b>"]
        items = menu_map.get(day) or []
        if items:
            for item in items:
                lines.append(f"• {html.escape(item)}")
        else:
            lines.append("• (меню не указано)")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _weekly_delivery_hint(context: ContextTypes.DEFAULT_TYPE) -> str:
    week_iso = context.user_data.get('order_week_start')
    if context.user_data.get('order_for_next_week'):
        if week_iso:
            try:
                ws = date.fromisoformat(str(week_iso))
                return f"<i>Доставка на неделе, начинающейся {ws.strftime('%d.%m.%Y')}.</i>"
            except Exception:
                return "<i>Доставка на следующей неделе.</i>"
        return "<i>Доставка на следующей неделе.</i>"
    if week_iso:
        try:
            ws = date.fromisoformat(str(week_iso))
            return f"<i>Неделя начинается {ws.strftime('%d.%m.%Y')}.</i>"
        except Exception:
            return ""
    return ""


async def _weekly_prepare_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    is_admin_user = update.effective_user.id == ADMIN_ID
    main_keyboard = get_main_menu_keyboard_admin() if is_admin_user else get_main_menu_keyboard()
    days = context.user_data.get('weekly_days_to_order') or context.user_data.get('weekly_days') or []
    if not days:
        await update.message.reply_text(
            "Не удалось определить дни доставки. Попробуйте начать заново.",
            reply_markup=main_keyboard,
        )
        _clear_weekly_context(context)
        return MENU

    count = context.user_data.get('selected_count') or '1'
    try:
        count_int = int(str(count))
    except Exception:
        count_int = 1
    total_meals = count_int * len(days)
    total_cost = total_meals * PRICE_LARI

    profile = context.user_data.get('profile')
    if not profile:
        profile = get_user_profile(update.effective_user.id)
        if profile:
            context.user_data['profile'] = profile

    menu_map = context.user_data.get('weekly_menu') or {}
    menu_html = _build_weekly_menu_html(days, menu_map)
    delivery_hint = _weekly_delivery_hint(context)

    if profile and profile.get('address'):
        phone_line = profile.get('phone') or "вы можете добавить телефон через кнопку ниже"
        context.user_data['pending_weekly_order'] = {
            'days': days,
            'count': count,
        }
        parts = ["<b>Подтвердите заказ на всю неделю</b>", ""]
        parts.append(f"<b>Количество в день:</b> {html.escape(str(count))}")
        parts.append(f"<b>Всего обедов:</b> {total_meals} {_ru_obed_plural(total_meals)}")
        parts.append(f"<b>Сумма к оплате:</b> {total_cost} лари")
        if delivery_hint:
            parts.append(delivery_hint)
        parts.extend(["", "<b>Меню:</b>", menu_html, ""])
        parts.append(f"<b>Адрес доставки:</b>\n{html.escape(profile.get('address') or '')}")
        parts.append(f"<b>Телефон:</b> {html.escape(phone_line)}")
        parts.extend(["", "Все верно?"])
        confirm_text = "\n".join(parts)
        await update.message.reply_text(
            confirm_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_confirm_keyboard(),
        )
        return CONFIRM

    address_parts = ["🎯 <b>Заказ почти готов</b>", "", menu_html]
    address_parts.append(f"🔢 <b>Количество в день:</b> {html.escape(str(count))}")
    address_parts.append(f"🍽️ <b>Всего обедов:</b> {total_meals} {_ru_obed_plural(total_meals)}")
    address_parts.append(f"💸 <b>Сумма:</b> {total_cost} лари")
    if delivery_hint:
        address_parts.append(delivery_hint)
    address_parts.extend([
        "",
        "📍 Остался 1 шаг — укажите <b>адрес доставки</b> одним сообщением:",
        "• улица и дом",
        "• подъезд/этаж/квартира",
        "• ориентир для курьера",
        "",
        "✍️ <i>Пример:</i>",
        "<code>ул. Руставели 10, подъезд 2, этаж 5, кв. 42; домофон 5423; ориентир — аптека</code>",
    ])
    address_text = "\n".join(address_parts)
    await update.message.reply_text(
        address_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_address_keyboard(),
    )
    return ADDRESS

# Обработка выбора дня недели
async def select_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_action(update.message.from_user, f"select_day: {update.message.text}")
    day = update.message.text
    menu_data = load_menu()
    if not menu_data or day not in menu_data['menu']:
        await update.message.reply_text("<b>Ошибка:</b> выберите день недели из списка.", parse_mode=ParseMode.HTML, reply_markup=get_day_keyboard())
        return ORDER_DAY
    day_allowed, day_warning, is_next_week, week_start_date = _is_day_available_for_order(day)
    if not day_allowed and day_warning:
        await update.message.reply_text(day_warning, parse_mode=ParseMode.HTML, reply_markup=get_day_keyboard())
        return ORDER_DAY
    # Сохраняем выбранный день и показываем меню этого дня
    context.user_data['selected_day'] = day
    context.user_data['order_for_next_week'] = bool(is_next_week)
    if week_start_date:
        context.user_data['order_week_start'] = week_start_date.isoformat()
    else:
        context.user_data['order_week_start'] = _current_week_start().isoformat()

    menu_for_day = menu_data['menu'][day]
    if isinstance(menu_for_day, list):
        menu_for_day_text = ", ".join(str(it).strip() for it in menu_for_day)
        menu_lines_html = "\n".join(f" - {html.escape(str(it).strip())}" for it in menu_for_day if str(it).strip())
    else:
        menu_for_day_text = str(menu_for_day).strip()
        menu_lines_html = f" - {html.escape(menu_for_day_text)}"

    # Сохраним текст меню в user_data, пригодится на подтверждении
    context.user_data['menu_for_day'] = menu_for_day_text

    notice = "\n<i>Заказ будет оформлен на следующую неделю.</i>" if is_next_week else ""
    message_text = (
        f"<b>{html.escape(day)}</b>\n{menu_lines_html}{notice}\n\n"
        f"<b>Сколько обедов заказать?</b>"
    )

    photo_path = DAY_PHOTO_MAP.get(day)
    if photo_path:
        try:
            with open(photo_path, "rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=message_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_count_keyboard(),
                )
            return ORDER_COUNT
        except FileNotFoundError:
            logging.warning(f"Фото для {day} не найдено по пути {photo_path}")
        except Exception as e:
            logging.error(f"Не удалось отправить фото для {day}: {e}")

    await update.message.reply_text(
        message_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_count_keyboard(),
    )
    return ORDER_COUNT

async def select_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user_action(update.message.from_user, f"select_count: {update.message.text}")
    raw_text = (update.message.text or "").strip()
    valid_counts = ["1 обед", "2 обеда", "3 обеда", "4 обеда"]
    digit_aliases = {
        "1": "1 обед",
        "2": "2 обеда",
        "3": "3 обеда",
        "4": "4 обеда",
    }
    count_text = raw_text
    if raw_text in digit_aliases:
        count_text = digit_aliases[raw_text]
    if count_text not in valid_counts:
        await update.message.reply_text(
            (
                "Можно выбрать от <b>1</b> до <b>4</b> обедов. "
                "Используйте кнопки ниже или введите число от 1 до 4."
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=get_count_keyboard(),
        )
        return ORDER_COUNT

    now = time.time()
    last_ts = context.user_data.get("last_order_ts")
    if last_ts and now - last_ts < 10:
        await update.message.reply_text(
            "<b>Слишком часто.</b> Подождите немного и попробуйте снова или выберите другой день.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_count_keyboard(),
        )
        return ORDER_COUNT

    count = count_text.split()[0]
    context.user_data['selected_count'] = count

    if context.user_data.get('weekly_mode'):
        week_start_iso = context.user_data.get('order_week_start')
        week_start_date = None
        if week_start_iso:
            try:
                week_start_date = date.fromisoformat(str(week_start_iso))
            except Exception:
                week_start_date = None
        days = context.user_data.get('weekly_days_to_order') or context.user_data.get('weekly_days') or []
        context.user_data['weekly_days_to_order'] = days
        duplicates: list[dict] = []
        for day in days:
            same = find_user_order_same_day(update.effective_user.id, day, week_start_date)
            if not same:
                continue
            oid, payload = same
            try:
                prev_cnt = int(str(payload.get('count', 1)).split()[0])
            except Exception:
                prev_cnt = 1
            duplicates.append(
                {
                    'order_id': oid,
                    'day': day,
                    'prev_count': prev_cnt,
                }
            )
        if duplicates:
            context.user_data['weekly_duplicates'] = duplicates
            context.user_data['weekly_duplicate_days'] = [entry['day'] for entry in duplicates]
            lines = [
                "На некоторые дни уже есть активные заказы:",
                "",
            ]
            for entry in duplicates:
                lines.append(
                    f"• {html.escape(entry['day'])}: <code>/order {html.escape(entry['order_id'])}</code> — "
                    f"{entry['prev_count']} {_ru_obed_plural(entry['prev_count'])}"
                )
            lines.extend([
                "",
                "Как поступить с этими заказами?",
            ])
            await update.message.reply_text(
                "\n".join(lines),
                parse_mode=ParseMode.HTML,
                reply_markup=get_weekly_duplicate_keyboard(),
            )
            return WEEKLY_DUPLICATE
        context.user_data.pop('weekly_duplicates', None)
        context.user_data.pop('weekly_duplicate_days', None)
        return await _weekly_prepare_confirmation(update, context)

    day = context.user_data.get('selected_day', '(не выбран)')
    week_start_iso = context.user_data.get('order_week_start')
    week_start_date = None
    if week_start_iso:
        try:
            week_start_date = date.fromisoformat(str(week_start_iso))
        except Exception:
            week_start_date = None
    menu_data = load_menu()
    menu_for_day = menu_data['menu'].get(day, '') if menu_data else ''
    if isinstance(menu_for_day, list):
        menu_for_day_text = ", ".join(menu_for_day)
    else:
        menu_for_day_text = str(menu_for_day)

    context.user_data['menu_for_day'] = menu_for_day_text

    same = find_user_order_same_day(update.effective_user.id, day, week_start_date)
    if same:
        oid, payload = same
        try:
            prev_cnt = int(str(payload.get('count', 1)).split()[0])
        except Exception:
            prev_cnt = 1
        context.user_data['duplicate_target'] = {
            'order_id': oid,
            'prev_count': prev_cnt,
            'day': day,
        }
        msg = (
            f"На <b>{html.escape(day)}</b> у вас уже есть заказ: "
            f"<code>/order {html.escape(oid)}</code>\n\n"
            "Что сделать с предыдущим заказом?"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=get_duplicate_resolution_keyboard())
        return DUPLICATE

    profile = context.user_data.get('profile')
    if not profile:
        profile = get_user_profile(update.effective_user.id)
        if profile:
            context.user_data['profile'] = profile
    has_address = bool((profile or {}).get('address'))

    if has_address:
        context.user_data['pending_order'] = {
            'day': day,
            'count': count,
            'menu': menu_for_day_text,
        }
        addr = profile.get('address')
        phone_line = profile.get('phone') or "вы можете добавить телефон через кнопку ниже"
        menu_lines_html = "\n".join(
            f" - {html.escape(it.strip())}" for it in str(menu_for_day_text).split(',') if it.strip()
        )
        try:
            count_int = int(str(count))
        except Exception:
            count_int = 1
        cost_lari = count_int * PRICE_LARI
        week_notice = "\n<i>Доставка будет на следующей неделе.</i>" if context.user_data.get('order_for_next_week') else ""
        confirm_text = (
            f"<b>Подтвердите заказ</b>\n\n"
            f"<b>День:</b> {html.escape(day)}\n"
            f"<b>Количество:</b> {html.escape(str(count))}\n"
            f"<b>Меню:</b>\n{menu_lines_html}\n\n"
            f"<b>Сумма к оплате:</b> {cost_lari} лари\n\n"
            f"<b>Адрес доставки:</b>\n{html.escape(addr or '')}\n"
            f"<b>Телефон:</b> {html.escape(phone_line)}\n\n"
            f"Все верно?{week_notice}"
        )
        await update.message.reply_text(
            confirm_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_confirm_keyboard(),
        )
        return CONFIRM

    menu_lines_html = "\n".join(
        f"• {html.escape(it.strip())}" for it in str(menu_for_day_text).split(',') if it.strip()
    )
    week_notice = "\n<i>Доставка будет на следующей неделе.</i>" if context.user_data.get('order_for_next_week') else ""
    reply_text = (
        f"🎯 <b>Заказ почти готов</b>\n\n"
        f"📅 <b>{html.escape(day)}</b>\n"
        f"🍽️ <b>Состав:</b>\n{menu_lines_html}\n"
        f"🔢 <b>Количество:</b> {html.escape(str(count))}\n\n"
        f"📍 Остался 1 шаг - укажите <b>адрес доставки</b> одним сообщением:\n"
        f"• улица и дом\n"
        f"• подъезд/этаж/квартира\n"
        f"• ориентир для курьера\n\n"
        f"✍️ <i>Пример:</i>\n"
        f"<code>ул. Руставели 10, подъезд 2, этаж 5, кв. 42; домофон 5423; ориентир - аптека</code>\n\n"
        f"После этого покажу итог и предложу подтвердить заказ ✅{week_notice}"
    )
    await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML, reply_markup=get_address_keyboard())
    return ADDRESS

# --- Разрешение ситуации с дублирующимся заказом на тот же день ---
async def confirm_save_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.contact:
        return CONFIRM
    phone = update.message.contact.phone_number
    profile = context.user_data.get('profile') or {}
    profile['phone'] = phone
    context.user_data['profile'] = profile
    set_user_profile(update.effective_user.id, profile)

    if context.user_data.get('weekly_mode'):
        return await _weekly_prepare_confirmation(update, context)

    pend = context.user_data.get('pending_order') or {}
    day = pend.get('day', context.user_data.get('selected_day', '(не выбран)'))
    count = pend.get('count', context.user_data.get('selected_count', '(не выбрано)'))
    menu_for_day_text = pend.get('menu', context.user_data.get('menu_for_day', ''))
    addr = profile.get('address', '')
    phone_line = profile.get('phone') or "вы можете добавить телефон через кнопку ниже"
    menu_lines_html = "\n".join(
        f" - {html.escape(it.strip())}" for it in str(menu_for_day_text).split(',') if it.strip()
    )
    try:
        count_int = int(str(count))
    except Exception:
        count_int = 1
    cost_lari = count_int * PRICE_LARI
    week_notice = "\n<i>Доставка будет на следующей неделе.</i>" if context.user_data.get('order_for_next_week') else ""
    confirm_text = (
        f"<b>Подтвердите заказ</b>\n\n"
        f"<b>День:</b> {html.escape(day)}\n"
        f"<b>Количество:</b> {html.escape(str(count))}\n"
        f"<b>Меню:</b>\n{menu_lines_html}\n\n"
        f"<b>Сумма к оплате:</b> {cost_lari} лари\n\n"
        f"<b>Адрес доставки:</b>\n{html.escape(addr or '')}\n"
        f"<b>Телефон:</b> {html.escape(phone_line)}\n\n"
        f"Все верно?{week_notice}"
    )
    await update.message.reply_text(
        confirm_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_confirm_keyboard(),
    )
    return CONFIRM

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = (update.message.text or "").strip().lower()
    profile = context.user_data.get('profile') or {}

    if choice == 'изменить адрес':
        if context.user_data.get('weekly_mode'):
            hint = _weekly_delivery_hint(context)
            parts = [
                "<b>Введите новый адрес доставки</b>",
                "",
                "Напишите адрес одним сообщением:",
                "• улица и дом",
                "• подъезд/этаж/квартира",
                "• ориентир для курьера",
            ]
            if hint:
                parts.extend(["", hint])
            await update.message.reply_text(
                "\n".join(parts),
                parse_mode=ParseMode.HTML,
                reply_markup=get_address_keyboard(),
            )
        else:
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
        await update.message.reply_text(
            "Пожалуйста, выберите: <b>Подтверждаю</b> или <b>Изменить адрес</b>.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_confirm_keyboard(),
        )
        return CONFIRM

    if context.user_data.get('weekly_mode') or context.user_data.get('pending_weekly_order'):
        return await _finalize_weekly_order(update, context, profile)
    return await _finalize_single_order(update, context, profile)


async def _finalize_single_order(update: Update, context: ContextTypes.DEFAULT_TYPE, profile: dict) -> int:
    pend = context.user_data.get('pending_order') or {}
    day = pend.get('day', context.user_data.get('selected_day', '(не выбран)'))
    count = pend.get('count', context.user_data.get('selected_count', '1'))
    menu_for_day = pend.get('menu', context.user_data.get('menu_for_day', ''))

    try:
        count_int = int(str(count))
    except Exception:
        count_int = 1
    cost_lari = count_int * PRICE_LARI
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
        "delivery_week_start": context.user_data.get('order_week_start'),
        "next_week": bool(context.user_data.get('order_for_next_week')),
    })

    menu_lines_html = "\n".join(
        f"• {html.escape(it.strip())}" for it in str(menu_for_day).split(',') if it.strip()
    )
    created_line = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created_at))
    admin_text = (
        f"<b>🍱 Новый заказ</b> <code>{html.escape(order_id)}</code>\n"
        f"<b>Создан:</b> {created_line}\n"
        f"<b>Клиент:</b> {admin_link_html(user)} ({html.escape(username)})\n"
        f"<b>День:</b> {html.escape(day)}\n"
        f"<b>Меню:</b>\n{menu_lines_html}\n"
        f"<b>Количество:</b> {html.escape(str(count))}\n"
        f"<b>Сумма:</b> {cost_lari} лари (по {PRICE_LARI} лари за обед)\n"
        f"<b>Адрес:</b>\n<blockquote>{html.escape(profile.get('address') or '')}</blockquote>\n"
        f"<b>Телефон:</b> {html.escape(profile.get('phone') or 'не указан')}\n\n"
        f"<b>Быстрый просмотр:</b> <code>/order {html.escape(order_id)}</code>"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Ошибка отправки админу {ADMIN_ID}: {e}")

    await send_success_gif(update)

    context.user_data['last_order_ts'] = time.time()
    is_next_week_delivery = bool(context.user_data.get('order_for_next_week'))
    delivery_week_iso = context.user_data.get('order_week_start')
    context.user_data.pop('pending_order', None)
    context.user_data.pop('order_for_next_week', None)
    context.user_data.pop('order_week_start', None)

    week_line = ""
    if is_next_week_delivery and delivery_week_iso:
        try:
            ws = date.fromisoformat(delivery_week_iso)
            week_line = f"\n🗓️ Доставка с {ws.strftime('%d.%m.%Y')} (следующая неделя)."
        except Exception:
            week_line = "\n🗓️ Доставка на следующей неделе."
    elif is_next_week_delivery:
        week_line = "\n🗓️ Доставка на следующей неделе."

    await update.message.reply_text(
        (
            f"<b>🎉 Спасибо! Заказ принят</b>\n\n"
            f"🧾 <b>ID заказа:</b> <code>{html.escape(order_id)}</code>\n"
            f"📅 <b>Доставка:</b> {html.escape(day)}{week_line}\n"
            f"⏰ <b>Окно:</b> 12:30-15:30\n"
            f"💸 <b>Сумма:</b> {cost_lari} лари\n"
            f"💳 Оплата: наличными курьеру или переводом.\n\n"
            f"<b>🔎 Посмотреть детали позже:</b>\n"
            f"<code>/order {html.escape(order_id)}</code>"
        ),
        reply_markup=_build_order_actions_keyboard(order_id),
        parse_mode=ParseMode.HTML,
    )
    await update.message.reply_text(
        "Что дальше?",
        reply_markup=get_after_confirm_keyboard(),
    )
    return MENU


async def _finalize_weekly_order(update: Update, context: ContextTypes.DEFAULT_TYPE, profile: dict) -> int:
    pending = context.user_data.get('pending_weekly_order') or {}
    days = pending.get('days') or context.user_data.get('weekly_days_to_order') or context.user_data.get('weekly_days') or []
    if not days:
        await update.message.reply_text(
            "Не удалось определить дни доставки. Попробуйте начать оформление заново.",
            reply_markup=get_main_menu_keyboard(),
        )
        _clear_weekly_context(context)
        context.user_data.pop('selected_count', None)
        return MENU

    count = pending.get('count', context.user_data.get('selected_count', '1'))
    try:
        count_int = int(str(count))
    except Exception:
        count_int = 1

    weekly_menu = context.user_data.get('weekly_menu') or {}
    week_iso = context.user_data.get('order_week_start')
    week_start_date = None
    if week_iso:
        try:
            week_start_date = date.fromisoformat(str(week_iso))
        except Exception:
            week_start_date = None
    total_meals = count_int * len(days)
    total_cost = total_meals * PRICE_LARI

    user = update.message.from_user
    username = f"@{user.username}" if user.username else "(нет username)"
    created_at = int(time.time())
    created_orders: list[dict] = []

    for day in days:
        menu_items = weekly_menu.get(day) or []
        menu_text = ", ".join(menu_items)
        order_id = make_order_id(user.id)
        save_order(order_id, {
            "user_id": user.id,
            "username": user.username,
            "day": day,
            "count": count,
            "menu": menu_text,
            "address": profile.get('address'),
            "phone": profile.get('phone'),
            "status": "new",
            "created_at": created_at,
            "delivery_week_start": week_iso,
            "next_week": bool(context.user_data.get('order_for_next_week')),
        })
        created_orders.append(
            {
                'day': day,
                'order_id': order_id,
                'menu_items': menu_items,
            }
        )

    menu_blocks = []
    for entry in created_orders:
        items_html = "\n".join(f"• {html.escape(it)}" for it in entry['menu_items']) if entry['menu_items'] else "• (меню не указано)"
        menu_blocks.append(
            f"<b>{html.escape(entry['day'])}</b>\n{items_html}\n<code>/order {html.escape(entry['order_id'])}</code>"
        )

    delivery_hint = _weekly_delivery_hint(context)
    admin_lines = [
        "<b>🍱 Пакетный заказ на неделю</b>",
        f"<b>Клиент:</b> {admin_link_html(user)} ({html.escape(username)})",
        f"<b>Количество в день:</b> {count_int} {_ru_obed_plural(count_int)}",
        f"<b>Всего обедов:</b> {total_meals} {_ru_obed_plural(total_meals)}",
        f"<b>Сумма:</b> {total_cost} лари",
        f"<b>Адрес:</b>\n<blockquote>{html.escape(profile.get('address') or '')}</blockquote>",
        f"<b>Телефон:</b> {html.escape(profile.get('phone') or 'не указан')}",
    ]
    if delivery_hint:
        admin_lines.append(delivery_hint)
    admin_lines.extend(["", "<b>Дни:</b>"])
    admin_lines.extend(menu_blocks)
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text="\n".join(admin_lines),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logging.error(f"Ошибка отправки пакетного заказа админу: {e}")

    await send_success_gif(update)
    context.user_data['last_order_ts'] = time.time()

    user_lines = [
        "<b>🎉 Спасибо! Заказ на неделю принят</b>",
        f"🔢 <b>Количество в день:</b> {count_int} {_ru_obed_plural(count_int)}",
        f"🍽️ <b>Всего обедов:</b> {total_meals} {_ru_obед_plural(total_meals)}",
        f"💸 <b>Сумма:</b> {total_cost} лари",
    ]
    if week_start_date:
        if context.user_data.get('order_for_next_week'):
            user_lines.append(f"🗓️ Доставка с {week_start_date.strftime('%d.%m.%Y')} (следующая неделя)")
        else:
            user_lines.append(f"🗓️ Неделя начинается {week_start_date.strftime('%d.%m.%Y')}")
    user_lines.extend(["", "<b>Дни:</b>"])
    user_lines.extend(menu_blocks)
    await update.message.reply_text("\n".join(user_lines), parse_mode=ParseMode.HTML)
    await update.message.reply_text("Что дальше?", reply_markup=get_after_confirm_keyboard())

    _clear_weekly_context(context)
    context.user_data.pop('selected_count', None)
    context.user_data.pop('order_for_next_week', None)
    context.user_data.pop('order_week_start', None)
    context.user_data.pop('pending_weekly_order', None)
    context.user_data.pop('pending_order', None)
    return MENU


# Назад с подтверждения к выбору количества
async def back_to_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('weekly_mode'):
        context.user_data.pop('pending_weekly_order', None)
        summary = _build_weekly_menu_html(
            context.user_data.get('weekly_days') or [],
            context.user_data.get('weekly_menu') or {},
        )
        lines = ["<b>Заказ на всю неделю</b>"]
        if summary:
            lines.extend(["", summary])
        lines.append("<b>Сколько обедов в день оформить?</b>")
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=get_count_keyboard(),
        )
        return ORDER_COUNT
    await update.message.reply_text(
        "<b>Сколько обедов заказать?</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_count_keyboard(),
    )
    return ORDER_COUNT


# Назад с выбора количества к выбору дня
async def back_to_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('weekly_mode'):
        picker_state = _get_weekly_picker_state(context)
        _clear_weekly_context(context)
        context.user_data.pop('selected_count', None)
        context.user_data.pop('order_for_next_week', None)
        context.user_data.pop('order_week_start', None)
        if picker_state:
            _set_weekly_picker_state(context, picker_state)
            message_text = _weekly_picker_text(picker_state)
            await update.message.reply_text(
                message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=_weekly_picker_keyboard(picker_state),
            )
            return WEEKLY_DAY_PICK
        keyboard = get_main_menu_keyboard_admin() if update.effective_user.id == ADMIN_ID else get_main_menu_keyboard()
        await update.message.reply_text(
            "Возвращаемся в главное меню.",
            reply_markup=keyboard,
        )
        return MENU
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

async def resolve_duplicate_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = (update.message.text or "").strip()
    dup = context.user_data.get('duplicate_target') or {}
    oid = dup.get('order_id')
    day = dup.get('day') or context.user_data.get('selected_day')
    # Текущий выбор пользователя
    count = context.user_data.get('selected_count')
    menu_for_day_text = context.user_data.get('menu_for_day', '')
    # Обновим профиль
    profile = context.user_data.get('profile')
    if not profile:
        profile = get_user_profile(update.effective_user.id)
        if profile:
            context.user_data['profile'] = profile
    has_address = bool((profile or {}).get('address'))

    if choice == "Удалить предыдущий заказ" and oid:
        # Отменяем предыдущий заказ
        if set_order_status(oid, "cancelled_by_user"):
            try:
                who = admin_link_html(update.effective_user)
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=(
                        f"<b>🚫 Отмена заказа</b> <code>{html.escape(oid)}</code>\n"
                        f"Кем: {who} (user_id={update.effective_user.id})"
                    ),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
        # Продолжаем оформление нового заказа с ранее выбранным количеством
        try:
            count_int = int(str(count))
        except Exception:
            count_int = 1
        cost_lari = count_int * PRICE_LARI
        if has_address:
            context.user_data['pending_order'] = {
                'day': day,
                'count': count,
                'menu': menu_for_day_text,
            }
            addr = profile.get('address')
            phone_line = profile.get('phone') or "вы можете добавить телефон через кнопку ниже"
            menu_lines_html = "\n".join(
                f" - {html.escape(it.strip())}" for it in str(menu_for_day_text).split(',') if it.strip()
            )
            week_notice = "\n<i>Доставка будет на следующей неделе.</i>" if context.user_data.get('order_for_next_week') else ""
            confirm_text = (
                f"<b>Подтвердите заказ</b>\n\n"
                f"<b>День:</b> {html.escape(day)}\n"
                f"<b>Количество:</b> {html.escape(str(count))}\n"
                f"<b>Меню:</b>\n{menu_lines_html}\n\n"
                f"<b>Сумма к оплате:</b> {cost_lari} лари\n\n"
                f"<b>Адрес доставки:</b>\n{html.escape(addr or '')}\n"
                f"<b>Телефон:</b> {html.escape(phone_line)}\n\n"
                f"Все верно?{week_notice}"
            )
            await update.message.reply_text(
                confirm_text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_confirm_keyboard(),
            )
            context.user_data.pop('duplicate_target', None)
            return CONFIRM
        else:
            # запрашиваем адрес
            menu_lines_html = "\n".join(
                f"• {html.escape(it.strip())}" for it in str(menu_for_day_text).split(',') if it.strip()
            )
            week_notice = "\n<i>Доставка будет на следующей неделе.</i>" if context.user_data.get('order_for_next_week') else ""
            reply_text = (
                f"🎯 <b>Заказ почти готов</b>\n\n"
                f"📅 <b>{html.escape(day)}</b>\n"
                f"🍽️ <b>Состав:</b>\n{menu_lines_html}\n"
                f"🔢 <b>Количество:</b> {html.escape(str(count))}\n\n"
                f"📍 Остался 1 шаг - укажите <b>адрес доставки</b> одним сообщением:\n"
                f"• улица и дом\n"
                f"• подъезд/этаж/квартира\n"
                f"• ориентир для курьера\n\n"
                f"После этого покажу итог и предложу подтвердить заказ ✅{week_notice}"
            )
            await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML, reply_markup=get_address_keyboard())
            context.user_data.pop('duplicate_target', None)
            return ADDRESS

    if choice == "Добавить к существующему" and oid:
        # Увеличиваем количество в существующем заказе
        try:
            add_cnt = int(str(count))
        except Exception:
            add_cnt = 1
        prev_cnt = dup.get('prev_count') or 0
        new_total = max(1, int(prev_cnt) + add_cnt)
        orders = _load_orders()
        if oid in orders:
            orders[oid]['count'] = str(new_total)
            _save_orders(orders)
        # Уведомим админа об изменении
        try:
            who = admin_link_html(update.effective_user)
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"<b>✏️ Обновление заказа</b> <code>{html.escape(oid)}</code>\n"
                    f"Кем: {who} (user_id={update.effective_user.id})\n"
                    f"Количество: было {prev_cnt}, стало {new_total}"
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass
        # Сообщение пользователю
        await update.message.reply_text(
            (
                f"<b>Готово!</b> Обновил ваш заказ на <b>{html.escape(day)}</b>.\n"
                f"Текущее количество: <b>{new_total} {_ru_obed_plural(new_total)}</b>\n"
                f"<code>/order {html.escape(oid)}</code>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=get_after_confirm_keyboard(),
        )
        context.user_data.pop('duplicate_target', None)
        return MENU

    # Непредвиденный ввод — спросим снова
    await update.message.reply_text(
        "Выберите один из вариантов ниже:",
        reply_markup=get_duplicate_resolution_keyboard(),
    )
    return DUPLICATE

async def resolve_weekly_duplicates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = (update.message.text or "").strip()
    duplicates = context.user_data.get('weekly_duplicates') or []
    if not duplicates:
        main_keyboard = get_main_menu_keyboard_admin() if update.effective_user.id == ADMIN_ID else get_main_menu_keyboard()
        await update.message.reply_text(
            "Предыдущих заказов для изменения не найдено. Начнем сначала.",
            reply_markup=main_keyboard,
        )
        _clear_weekly_context(context)
        context.user_data.pop('selected_count', None)
        return MENU

    count_raw = context.user_data.get('selected_count') or '1'
    try:
        add_count = int(str(count_raw))
    except Exception:
        add_count = 1
    user = update.effective_user

    if choice == "Заменить предыдущие заказы":
        cancelled: list[dict] = []
        for entry in duplicates:
            oid = entry.get('order_id')
            if not oid:
                continue
            if set_order_status(oid, "cancelled_by_user"):
                cancelled.append(entry)
        if cancelled:
            lines = [
                "<b>🚫 Отмена предыдущих заказов</b>",
                f"Клиент: {admin_link_html(user)} (user_id={user.id})",
                "",
            ]
            for entry in cancelled:
                lines.append(
                    f"• {html.escape(entry['day'])}: <code>{html.escape(entry['order_id'])}</code>"
                )
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text="\n".join(lines),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
        await update.message.reply_text(
            "Предыдущие заказы удалены. Продолжаем оформление нового недельного заказа.",
            parse_mode=ParseMode.HTML,
        )
        context.user_data['weekly_days_to_order'] = context.user_data.get('weekly_days') or []
        context.user_data.pop('weekly_duplicates', None)
        context.user_data.pop('weekly_duplicate_days', None)
        context.user_data.pop('pending_weekly_order', None)
        return await _weekly_prepare_confirmation(update, context)

    if choice == "Добавить к существующим":
        orders = _load_orders()
        updated: list[tuple[str, str, int, int]] = []
        for entry in duplicates:
            oid = entry.get('order_id')
            if not oid or oid not in orders:
                continue
            prev_cnt = entry.get('prev_count') or 0
            new_total = max(1, int(prev_cnt) + add_count)
            orders[oid]['count'] = str(new_total)
            updated.append((entry.get('day') or '', oid, int(prev_cnt), new_total))
        if updated:
            _save_orders(orders)
            lines = [
                "<b>✏️ Обновление заказов</b>",
                f"Клиент: {admin_link_html(user)} (user_id={user.id})",
                "",
            ]
            for day_name, oid, prev_cnt, new_total in updated:
                lines.append(
                    f"• {html.escape(day_name)}: было {prev_cnt}, стало {new_total} — <code>{html.escape(oid)}</code>"
                )
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text="\n".join(lines),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
        remaining_days = [
            day for day in (context.user_data.get('weekly_days') or [])
            if day not in {entry.get('day') for entry in duplicates}
        ]
        if not remaining_days:
            summary = [
                "<b>Готово!</b> Обновил количество в существующих заказах:",
                "",
            ]
            for day_name, oid, prev_cnt, new_total in updated:
                summary.append(
                    f"• {html.escape(day_name)} — {new_total} {_ru_obed_plural(new_total)} (<code>/order {html.escape(oid)}</code>)"
                )
            await update.message.reply_text(
                "\n".join(summary),
                parse_mode=ParseMode.HTML,
                reply_markup=get_after_confirm_keyboard(),
            )
            _clear_weekly_context(context)
            context.user_data.pop('selected_count', None)
            return MENU
        context.user_data['weekly_days_to_order'] = remaining_days
        context.user_data.pop('weekly_duplicates', None)
        context.user_data.pop('weekly_duplicate_days', None)
        context.user_data.pop('pending_weekly_order', None)
        await update.message.reply_text(
            "Количество в существующих заказах обновлено. Оформим новые заказы на оставшиеся дни.",
            parse_mode=ParseMode.HTML,
        )
        return await _weekly_prepare_confirmation(update, context)

    if choice == "Отменить оформление":
        _clear_weekly_context(context)
        context.user_data.pop('selected_count', None)
        main_keyboard = get_main_menu_keyboard_admin() if update.effective_user.id == ADMIN_ID else get_main_menu_keyboard()
        await update.message.reply_text(
            "Пакетное оформление отменено.",
            reply_markup=main_keyboard,
        )
        return MENU

    await update.message.reply_text(
        "Пожалуйста, выберите один из вариантов ниже.",
        reply_markup=get_weekly_duplicate_keyboard(),
    )
    return WEEKLY_DUPLICATE

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

        if context.user_data.get('weekly_mode'):
            return await _weekly_prepare_confirmation(update, context)

        pend = context.user_data.get('pending_order') or {}
        day = pend.get('day', context.user_data.get('selected_day', '(не выбран)'))
        count = pend.get('count', context.user_data.get('selected_count', '(не выбрано)'))
        menu_for_day_text = pend.get('menu', context.user_data.get('menu_for_day', ''))
        addr = profile.get('address', '')
        phone_line = profile.get('phone') or "вы можете добавить телефон через кнопку ниже"
        menu_lines_html = "\n".join(
            f" - {html.escape(it.strip())}" for it in str(menu_for_day_text).split(',') if it.strip()
        )
        try:
            count_int = int(str(count))
        except Exception:
            count_int = 1
        cost_lari = count_int * PRICE_LARI
        confirm_text = (
            f"<b>Подтвердите заказ</b>\n\n"
            f"<b>День:</b> {html.escape(day)}\n"
            f"<b>Количество:</b> {html.escape(str(count))}\n"
            f"<b>Меню:</b>\n{menu_lines_html}\n\n"
            f"<b>Сумма к оплате:</b> {cost_lari} лари\n\n"
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
            await update.message.reply_text("<b>Адрес сохранен.</b>", parse_mode=ParseMode.HTML)

            if context.user_data.get('weekly_mode'):
                context.user_data.pop('pending_order', None)
                return await _weekly_prepare_confirmation(update, context)

            pend = context.user_data.get('pending_order') or {}
            day = pend.get('day', context.user_data.get('selected_day', '(не выбран)'))
            count = pend.get('count', context.user_data.get('selected_count', '(не выбрано)'))
            menu_for_day_text = pend.get('menu', context.user_data.get('menu_for_day', ''))
            addr = profile.get('address', '')
            phone_line = profile.get('phone') or "вы можете добавить телефон через кнопку ниже"
            menu_lines_html = "\n".join(
                f" - {html.escape(it.strip())}" for it in str(menu_for_day_text).split(',') if it.strip()
            )
            try:
                count_int = int(str(count))
            except Exception:
                count_int = 1
            cost_lari = count_int * PRICE_LARI
            confirm_text = (
                f"<b>Подтвердите заказ</b>\n\n"
                f"<b>День:</b> {html.escape(day)}\n"
                f"<b>Количество:</b> {html.escape(str(count))}\n"
                f"<b>Меню:</b>\n{menu_lines_html}\n\n"
                f"<b>Сумма к оплате:</b> {cost_lari} лари\n\n"
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

    if not profile.get('address'):
        await update.message.reply_text(
            "Нам нужен точный адрес. <b>Пожалуйста, введите адрес доставки текстом</b>.", parse_mode=ParseMode.HTML, reply_markup=get_address_keyboard()
        )
        return ADDRESS
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

    # Форматируем меню списком
    menu_for_day = data.get("menu") or ""
    menu_lines_html = "\n".join(
        f"• {html.escape(it.strip())}" for it in str(menu_for_day).split(',') if it.strip()
    )

    # Парсим количество и считаем сумму
    raw_count = data.get("count", 1)
    try:
        count_int = int(str(raw_count).split()[0])
    except Exception:
        count_int = 1
    cost_lari = count_int * PRICE_LARI

    status = data.get("status") or "-"

    text_html = (
        f"<b>Заказ</b> <code>{html.escape(order_id)}</code>\n"
        f"<b>Создан:</b> {created_line}\n"
        f"<b>Статус:</b> {html.escape(status)}\n"
        f"<b>День:</b> {html.escape(str(data.get('day') or ''))}\n"
        f"<b>Меню:</b>\n{menu_lines_html}\n"
        f"<b>Количество:</b> {count_int}\n"
        f"<b>Сумма:</b> {cost_lari} лари (по {PRICE_LARI} лари за обед)\n"
        f"<b>Адрес:</b>\n<blockquote>{html.escape(str(data.get('address') or ''))}</blockquote>\n"
        f"<b>Телефон:</b> {html.escape(phone_line)}"
    )
    # Кнопка отмены для активного заказа (new) и при наличии прав (владелец или админ)
    reply_kb = None
    if (is_admin or is_owner) and str(status).lower() == "new":
        reply_kb = _build_order_actions_keyboard(order_id, allow_change=is_owner, allow_cancel=True)
    await update.message.reply_text(text_html, parse_mode=ParseMode.HTML, reply_markup=reply_kb)

#
# Cancel order via command
async def cancel_order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User or admin cancels an order: /cancel <ID>"""
    args = context.args if hasattr(context, "args") else []
    if not args:
        await update.message.reply_text("Использование: /cancel <ID>\nНапример: /cancel BLB-ABCDEFG-1234-1XYZ")
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
        await update.message.reply_text("У вас нет прав отменять этот заказ.")
        return

    status = str(data.get("status") or "-").lower()
    if status != "new":
        await update.message.reply_text("Отмена недоступна. Заказ уже в обработке или завершен.")
        return

    if set_order_status(order_id, "cancelled_by_user" if is_owner and not is_admin else "cancelled"):
        # Уведомим админа
        try:
            who = admin_link_html(user)
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"<b>🚫 Отмена заказа</b> <code>{html.escape(order_id)}</code>\n"
                    f"Кем: {who} (user_id={user.id})"
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass
        await update.message.reply_text(
            f"Заказ <code>{html.escape(order_id)}</code> отменен.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text("Не удалось обновить статус заказа. Попробуйте позже.")


# Cancel order via inline button
async def cancel_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline-кнопка отмены текущего заказа"""
    query = update.callback_query
    await query.answer()
    data_cb = (query.data or "")
    if not data_cb.startswith("cancel_order:"):
        return
    order_id = data_cb.split(":", 1)[1]
    # Получим заказ
    data = get_order(order_id)
    if not data:
        await query.edit_message_text("Заказ не найден.")
        return
    user_id = query.from_user.id
    is_admin = (user_id == ADMIN_ID)
    is_owner = (data.get("user_id") == user_id)
    if not (is_admin or is_owner):
        await query.edit_message_text("Нет прав для отмены этого заказа.")
        return
    status = str(data.get("status") or "-").lower()
    if status != "new":
        await query.edit_message_text("Отмена недоступна. Заказ уже в обработке или завершен.")
        return
    if set_order_status(order_id, "cancelled_by_user" if is_owner and not is_admin else "cancelled"):
        try:
            who = admin_link_html(query.from_user)
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"<b>🚫 Отмена заказа</b> <code>{html.escape(order_id)}</code>\n"
                    f"Кем: {who} (user_id={query.from_user.id})"
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass
        await query.edit_message_text(
            f"Заказ <code>{html.escape(order_id)}</code> отменен.",
            parse_mode=ParseMode.HTML,
        )


async def change_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_cb = (query.data or "")
    if not data_cb.startswith("change_order:"):
        return
    order_id = data_cb.split(":", 1)[1]
    order = get_order(order_id)
    if not order:
        await query.answer("Заказ не найден", show_alert=True)
        return
    user_id = query.from_user.id
    is_admin = (user_id == ADMIN_ID)
    is_owner = (order.get("user_id") == user_id)
    if not (is_admin or is_owner):
        await query.answer("Нет доступа", show_alert=True)
        return
    status = str(order.get("status") or "").lower()
    if status != "new":
        await query.answer("Изменения недоступны: заказ уже в обработке.", show_alert=True)
        return

    day = str(order.get("day") or "")
    raw_count = order.get("count", 1)
    try:
        current_count_int = int(str(raw_count).split()[0])
    except Exception:
        current_count_int = 1
    current_count = str(current_count_int)
    context.user_data['update_order'] = {
        'id': order_id,
        'day': day,
        'menu': order.get('menu'),
        'count': current_count,
        'delivery_week_start': order.get('delivery_week_start'),
        'next_week': bool(order.get('next_week')),
    }
    context.user_data['selected_day'] = day
    context.user_data['menu_for_day'] = order.get('menu', '')
    if order.get('delivery_week_start'):
        context.user_data['order_week_start'] = str(order.get('delivery_week_start'))
    else:
        context.user_data['order_week_start'] = _current_week_start().isoformat()
    context.user_data['order_for_next_week'] = bool(order.get('next_week'))
    prompt = (
        f"<b>Изменение заказа</b>\n\n"
        f"Текущий день: <b>{html.escape(day)}</b>\n"
        f"Текущее количество: <b>{html.escape(str(current_count_int))}</b> {_ru_obed_plural(current_count_int)}\n\n"
        "Выберите новое количество на клавиатуре ниже."
    )
    await query.message.reply_text(
        prompt,
        parse_mode=ParseMode.HTML,
        reply_markup=get_count_keyboard(),
    )
    return UPDATE_ORDER_COUNT


async def update_order_count_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_ctx = context.user_data.get('update_order')
    if not update_ctx:
        await update.message.reply_text("Заказ для изменения не найден. Попробуйте снова перейти через кнопку.")
        return MENU

    raw_text = (update.message.text or "").strip()
    valid_counts = {"1", "2", "3", "4"}
    digit_aliases = {
        "1 обед": "1",
        "2 обеда": "2",
        "3 обеда": "3",
        "4 обеда": "4",
    }
    selected = digit_aliases.get(raw_text, raw_text)
    if selected not in valid_counts:
        await update.message.reply_text(
            "Выберите количество от 1 до 4 с клавиатуры или числом.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_count_keyboard(),
        )
        return UPDATE_ORDER_COUNT

    new_count = int(selected)
    order_id = update_ctx['id']
    orders = _load_orders()
    if order_id not in orders:
        await update.message.reply_text("Не удалось найти заказ. Возможно, он уже был изменен или отменен.")
        context.user_data.pop('update_order', None)
        return MENU

    orders[order_id]['count'] = str(new_count)
    orders[order_id]['updated_at'] = int(time.time())
    _save_orders(orders)

    # Уведомим администратора
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"<b>✏️ Изменение заказа</b> <code>{html.escape(order_id)}</code>\n"
                f"Клиент: {admin_link_html(update.effective_user)}\n"
                f"Новый объем: {new_count} {_ru_obed_plural(new_count)}"
            ),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass

    context.user_data.pop('update_order', None)
    context.user_data.pop('menu_for_day', None)
    context.user_data.pop('selected_day', None)
    context.user_data.pop('order_week_start', None)
    context.user_data.pop('order_for_next_week', None)

    await update.message.reply_text(
        (
            f"Количество обновлено: <b>{new_count} {_ru_obed_plural(new_count)}</b>\n"
            f"<code>/order {html.escape(order_id)}</code>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=get_after_confirm_keyboard(),
    )
    return MENU


async def cancel_update_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('update_order', None)
    await update.message.reply_text(
        "Изменение заказа отменено.",
        reply_markup=get_after_confirm_keyboard(),
    )
    return MENU

#
# Callback: скопировать номер заказа
async def copy_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = (query.data or "")
    await query.answer()
    if not data.startswith("copy_order:"):
        return
    order_id = data.split(":", 1)[1]
    try:
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"/order {order_id}")
    except Exception as e:
        logging.error(f"Не удалось отправить команду для копирования: {e}")

# Обработка некорректных действий
async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state', 'unknown')
    log_user_action(update.message.from_user, f"fallback state={state}")
    is_admin = (update.effective_user.id == ADMIN_ID)
    admin_ui = context.user_data.get('admin_ui', True)
    kb = get_main_menu_keyboard()
    if is_admin and not admin_ui:
        from keyboards import get_main_menu_keyboard_admin
        kb = get_main_menu_keyboard_admin()
    elif is_admin and admin_ui:
        kb = get_admin_main_keyboard()
    hint = _build_fallback_hint(context, is_admin)
    message = (
        "Кажется, я не распознал сообщение 🤔\n"
        f"{hint}\n\n"
        "Команда /start всегда возвращает в начало диалога."
    )
    await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=kb)
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


# Формируем подпись для Instagram-ссылки
def _get_instagram_label(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    label = parsed.path.strip("/")
    if label:
        label = label.split("/")[-1]
    else:
        label = parsed.netloc or url
    if "?" in label:
        label = label.split("?")[0]
    return label or "Instagram"


def _prepare_operator_contacts() -> dict[str, str]:
    handle = (OPERATOR_HANDLE or "").lstrip("@").strip()
    phone_display = (OPERATOR_PHONE or "").strip()
    phone_href = re.sub(r"[^\d+]", "", phone_display)
    instagram_url = (OPERATOR_INSTAGRAM or "").strip()
    instagram_label = _get_instagram_label(instagram_url) if instagram_url else ""
    return {
        "handle": handle,
        "phone_display": phone_display,
        "phone_href": phone_href,
        "instagram_url": instagram_url,
        "instagram_label": instagram_label,
    }


# Handler for "Связаться с человеком" button
async def contact_human(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contacts = _prepare_operator_contacts()
    parts: list[str] = []
    if contacts["handle"]:
        handle = contacts["handle"]
        parts.append(
            f"Telegram: <a href=\"https://t.me/{html.escape(handle)}\">@{html.escape(handle)}</a>"
        )
    if contacts["phone_href"]:
        phone_display = contacts["phone_display"] or contacts["phone_href"]
        parts.append(
            "по телефону: "
            f"<a href=\"tel:{html.escape(contacts['phone_href'])}\">{html.escape(phone_display)}</a>"
        )
    if contacts["instagram_url"]:
        parts.append(
            "Instagram: "
            f"<a href=\"{html.escape(contacts['instagram_url'])}\">{html.escape(contacts['instagram_label'])}</a>"
        )
    if parts:
        msg = "Связаться с оператором можно через:\n" + "\n".join(parts)
    else:
        msg = "Контакты оператора временно недоступны."
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    return


def _build_fallback_hint(context: ContextTypes.DEFAULT_TYPE, is_admin: bool) -> str:
    """Возвращает подсказку для fallback-ответа в зависимости от шага пользователя."""
    admin_ui = context.user_data.get('admin_ui', True)
    if is_admin and admin_ui:
        return (
            "Вы сейчас в <b>режиме администратора</b>. "
            "Выберите пункт на клавиатуре или отправьте /start, чтобы вернуться в начало."
        )
    if context.user_data.get('weekly_duplicates'):
        return (
            "Нужно решить, что делать с предыдущими заказами. Выберите действие на клавиатуре."
        )
    if _get_weekly_picker_state(context):
        return (
            "Мы выбираем <b>дни доставки</b>. Используйте кнопки под сообщением, чтобы отметить дни, или нажмите «Отмена»."
        )
    if context.user_data.get('pending_weekly_order'):
        return (
            "Мы на шаге <b>подтверждения пакетного заказа</b>. Используйте кнопки «Подтверждаю» или "
            "«Изменить адрес», либо отправьте телефон."
        )
    if context.user_data.get('weekly_mode'):
        return (
            "Укажите количество обедов в день на клавиатуре (от 1 до 4) или нажмите «Назад», чтобы вернуться."
        )
    if context.user_data.get('duplicate_target'):
        return (
            "Нужно решить, что делать с предыдущим заказом. Нажмите «Удалить предыдущий заказ» "
            "или «Добавить к существующему»."
        )
    if context.user_data.get('update_order'):
        return (
            "Мы меняем количество в заказе. Выберите новое значение на клавиатуре "
            "или нажмите «Назад», чтобы отменить изменения."
        )
    if context.user_data.get('pending_order'):
        return (
            "Мы на шаге <b>подтверждения заказа</b>. Используйте кнопки «Подтверждаю» или "
            "«Изменить адрес», либо отправьте телефон."
        )
    if context.user_data.get('selected_count'):
        return (
            "Осталось <b>указать адрес доставки</b>. Напишите адрес одним сообщением "
            "или нажмите «Отправить телефон»."
        )
    if context.user_data.get('selected_day'):
        return "Сейчас нужно выбрать <b>количество обедов</b> на клавиатуре (от 1 до 4)."
    return "Выберите действие на главной клавиатуре или отправьте /start, чтобы начать сначала."


# Универсальное логирование нажатий любых кнопок (ReplyKeyboard)
BUTTON_TEXTS = [
    "Показать меню на неделю",
    "Показать заказы на эту неделю",
    "Мои заказы",
    "Удалить предыдущий заказ",
    "Добавить к существующему",
    "Заменить предыдущие заказы",
    "Добавить к существующим",
    "Отменить оформление",
    "Заказать на всю неделю",
    "Перейти в режим пользователя",
    "Перейти в режим администратора",
    "Управление меню",
    "Изменить название недели",
    "Редактировать блюда дня",
    "Обновить фото меню",
    "Открыть заказы на следующую неделю",
    "Изменить заказ",
    "Добавить блюдо",
    "Изменить блюдо",
    "Удалить блюдо",
    "Заменить список блюд",
    "Да",
    "Нет",
    "Неделя целиком",
    "Заказать обед",
    "Посмотреть меню",
    "Выбрать еще один день",
    "Выбрать день заново",
    "Понедельник", "Вторник", "Среда", "Четверг", "Пятница",
    "1 обед", "2 обеда", "3 обеда", "4 обеда",
    "Подтверждаю",
    "Изменить адрес",
    "Назад",
    "Отправить телефон",
    "🔄 В начало",
    "❗ Связаться с человеком",
    "В начало",
    "Связаться с человеком",
]

BUTTONS_REGEX = r"^(" + "|".join(re.escape(s) for s in BUTTON_TEXTS) + r")$"

async def log_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        log_user_action(update.message.from_user, f"button_click: {update.message.text}")

#
# Глобальный обработчик ошибок
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    # Тихая обработка сетевых проблем и ограничений
    try:
        if isinstance(err, (NetworkError, TimedOut)):
            logging.warning(f"Network issue: {err}")
            return
        if isinstance(err, RetryAfter):
            ra = getattr(err, 'retry_after', 1)
            logging.warning(f"Rate limited, retry after {ra}s")
            try:
                await asyncio.sleep(float(ra) if ra else 1)
            except Exception:
                pass
            return
        if isinstance(err, Forbidden):
            logging.info(f"Forbidden: {err}")
            return
        if isinstance(err, BadRequest):
            logging.warning(f"BadRequest: {err}")
            return
    except Exception:
        # В случае ошибки в самом обработчике — продолжим стандартным путем
        pass

    logging.exception("Unhandled exception", exc_info=err)
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
    # Настройка таймаутов HTTPX для стабильного long polling
    request = HTTPXRequest(
        connect_timeout=10,
        read_timeout=80,
        write_timeout=10,
        pool_timeout=5,
    )
    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .persistence(persistence)
        .request(request)
        .build()
    )

    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("my_profile", my_profile))
    application.add_handler(CommandHandler("order", order_info))
    application.add_handler(CommandHandler("sms", broadcast))
    application.add_handler(CallbackQueryHandler(copy_order_callback, pattern=r"^copy_order:"))
    application.add_handler(CommandHandler("cancel", cancel_order_command))
    application.add_handler(CallbackQueryHandler(cancel_order_callback, pattern=r"^cancel_order:"))

    # Логирование нажатий любых кнопок (универсальный handler, не блокирует дальнейшую обработку)
    application.add_handler(MessageHandler(filters.Regex(BUTTONS_REGEX), log_button), group=1)

    conv_handler = ConversationHandler(
        name="lunch_conv",
        persistent=True,
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^🔄 В начало$"), start)
        ],
        states={
            MENU: [
                CallbackQueryHandler(change_order_callback, pattern=r"^change_order:"),
                MessageHandler(filters.Regex("^Показать меню на неделю$"), show_menu),
                MessageHandler(filters.Regex("^Показать заказы на эту неделю$"), admin_show_week_orders),
                MessageHandler(filters.Regex("^Мои заказы$"), my_orders),
                MessageHandler(filters.Regex("^Перейти в режим пользователя$"), switch_to_user_mode),
                MessageHandler(filters.Regex("^Перейти в режим администратора$"), switch_to_admin_mode),
                MessageHandler(filters.Regex("^Управление меню$"), admin_manage_menu),
                MessageHandler(filters.Regex("^(Неделя целиком|Понедельник|Вторник|Среда|Четверг|Пятница)$"), admin_report_pick),
                MessageHandler(filters.Regex("^Заказать обед$"), order_lunch),
                MessageHandler(filters.Regex("^Заказать на всю неделю$"), order_week_lunch),
                MessageHandler(filters.Regex("^Посмотреть меню$"), show_menu),
                MessageHandler(filters.Regex("^Выбрать еще один день$"), order_lunch),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
            ],
            ORDER_DAY: [
                MessageHandler(filters.Regex("^(Понедельник|Вторник|Среда|Четверг|Пятница)$"), select_day),
                MessageHandler(filters.Regex("^Заказать на всю неделю$"), order_week_lunch),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
            ],
            WEEKLY_DAY_PICK: [
                CallbackQueryHandler(weekly_picker_toggle, pattern=r"^weekly_toggle:\d+$"),
                CallbackQueryHandler(weekly_picker_select_all, pattern=r"^weekly_all$"),
                CallbackQueryHandler(weekly_picker_clear, pattern=r"^weekly_none$"),
                CallbackQueryHandler(weekly_picker_continue, pattern=r"^weekly_continue$"),
                CallbackQueryHandler(weekly_picker_cancel, pattern=r"^weekly_cancel$"),
                MessageHandler(filters.Regex("^Заказать на всю неделю$"), order_week_lunch),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
            ],
            ORDER_COUNT: [
                CallbackQueryHandler(change_order_callback, pattern=r"^change_order:"),
                MessageHandler(filters.Regex("^Назад$"), back_to_day),
                MessageHandler(filters.Regex("^Выбрать день заново$"), order_lunch),
                MessageHandler(filters.Regex("^(1 обед|2 обеда|3 обеда|4 обеда|[1-4])$"), select_count),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
            ],
            UPDATE_ORDER_COUNT: [
                MessageHandler(filters.Regex("^Назад$"), cancel_update_order),
                MessageHandler(filters.Regex("^(1 обед|2 обеда|3 обеда|4 обеда|[1-4])$"), update_order_count_choice),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
            ],
            ADDRESS: [
                MessageHandler(filters.Regex("^Назад$"), back_to_count),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
                MessageHandler((filters.TEXT | filters.CONTACT) & ~filters.COMMAND, address_phone),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
            ],
            CONFIRM: [
                MessageHandler(filters.Regex("^Назад$"), back_to_count),
                MessageHandler(filters.CONTACT, confirm_save_phone),
                MessageHandler(filters.Regex("^(Подтверждаю|Изменить адрес)$"), confirm_order),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order),
            ],
            DUPLICATE: [
                MessageHandler(filters.Regex("^Удалить предыдущий заказ$"), resolve_duplicate_order),
                MessageHandler(filters.Regex("^Добавить к существующему$"), resolve_duplicate_order),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
            ],
            WEEKLY_DUPLICATE: [
                MessageHandler(filters.Regex("^Заменить предыдущие заказы$"), resolve_weekly_duplicates),
                MessageHandler(filters.Regex("^Добавить к существующим$"), resolve_weekly_duplicates),
                MessageHandler(filters.Regex("^Отменить оформление$"), resolve_weekly_duplicates),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
            ],
            
            ADMIN_MENU: [
                MessageHandler(filters.Regex("^Изменить название недели$"), admin_menu_request_week),
                MessageHandler(filters.Regex("^Редактировать блюда дня$"), admin_menu_show_day_prompt),
                MessageHandler(filters.Regex("^Обновить фото меню$"), admin_menu_request_photo),
                MessageHandler(filters.Regex("^Открыть заказы на следующую неделю$"), admin_open_next_week_orders),
                MessageHandler(filters.Regex("^Назад$"), admin_menu_exit),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
            ],
            ADMIN_MENU_DAY_SELECT: [
                MessageHandler(filters.Regex("^Назад$"), admin_menu_back_to_main),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu_day_chosen),
            ],
            ADMIN_MENU_ACTION: [
                MessageHandler(filters.Regex("^Добавить блюдо$"), admin_menu_day_action_add),
                MessageHandler(filters.Regex("^Изменить блюдо$"), admin_menu_day_action_edit),
                MessageHandler(filters.Regex("^Удалить блюдо$"), admin_menu_day_action_delete),
                MessageHandler(filters.Regex("^Заменить список блюд$"), admin_menu_day_action_replace),
                MessageHandler(filters.Regex("^Назад$"), admin_menu_back_to_day_select),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
            ],
            ADMIN_MENU_ITEM_SELECT: [
                MessageHandler(filters.Regex("^Назад$"), admin_menu_back_to_day_actions),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu_handle_item_index),
            ],
            ADMIN_MENU_ITEM_TEXT: [
                MessageHandler(filters.Regex("^Назад$"), admin_menu_back_to_day_actions),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu_handle_text_input),
            ],
            ADMIN_MENU_WEEK: [
                MessageHandler(filters.Regex("^Назад$"), admin_manage_menu),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu_save_week),
            ],
            ADMIN_MENU_PHOTO: [
                MessageHandler(filters.Regex("^Назад$"), admin_manage_menu),
                MessageHandler(filters.Regex("^🔄 В начало$"), start),
                MessageHandler(filters.Regex("^В начало$"), start),
                MessageHandler(filters.Regex("^❗ Связаться с человеком$"), contact_human),
                MessageHandler(filters.Regex("^Связаться с человеком$"), contact_human),
                MessageHandler((filters.PHOTO | filters.Document.IMAGE), admin_menu_handle_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu_handle_photo),
            ],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(filters.ALL, fallback)]
    )
    application.add_handler(conv_handler)
    log_console("Бот запущен")
    application.run_polling(drop_pending_updates=True)
