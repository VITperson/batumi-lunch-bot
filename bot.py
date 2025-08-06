# Основной файл Telegram-бота для заказа обедов
# Для работы требуется заполнить BOT_TOKEN и ADMIN_ID

from config_secret import BOT_TOKEN, ADMIN_ID

import logging
import json
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler

# Состояния для ConversationHandler
MENU, ORDER_DAY, ORDER_COUNT = range(3)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Загрузка меню

def load_menu():
    try:
        with open("menu.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки меню: {e}")
        return None

# Стартовая команда
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сброс состояния и user_data
    context.user_data.clear()
    keyboard = [[KeyboardButton("Показать меню на неделю")], [KeyboardButton("Заказать обед")]]
    await update.message.reply_text(
        "Добро пожаловать! Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return MENU

# Обработка кнопки "Показать меню на неделю"
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_data = load_menu()
    if not menu_data:
        await update.message.reply_text("Техническая ошибка: меню недоступно. Попробуйте позже.")
        return MENU
    text = f"Неделя: {menu_data['week']}\n"
    for day, items in menu_data['menu'].items():
        text += f"{day}: {items}\n"
    await update.message.reply_text(text)
    # Кнопка "Да" для заказа
    keyboard = [[KeyboardButton("Да")]]
    await update.message.reply_text("Заказать ли обед?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return ORDER_DAY

# Обработка кнопки "Заказать обед" или "Да"
async def order_lunch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]
    keyboard = [[KeyboardButton(day)] for day in days]
    await update.message.reply_text(
        "Выберите день недели:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ORDER_DAY

# Обработка выбора дня недели
async def select_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = update.message.text
    menu_data = load_menu()
    if not menu_data or day not in menu_data['menu']:
        await update.message.reply_text("Ошибка: выберите день недели из списка.")
        return ORDER_DAY
    # Сохраняем выбранный день в context.user_data
    context.user_data['selected_day'] = day
    # Кнопки для выбора количества обедов
    keyboard = [[KeyboardButton(f"{i} обед{'' if i == 1 else 'а'}")] for i in range(1, 5)]
    await update.message.reply_text(
        "Сколько обедов заказать?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ORDER_COUNT

async def select_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count_text = update.message.text
    valid_counts = ["1 обед", "2 обеда", "3 обеда", "4 обеда"]
    if count_text not in valid_counts:
        await update.message.reply_text("Пожалуйста, выберите количество обедов с помощью кнопок.")
        return ORDER_COUNT
    count = count_text.split()[0]
    day = context.user_data.get('selected_day', '(не выбран)')
    menu_data = load_menu()
    menu_for_day = menu_data['menu'].get(day, '') if menu_data else ''
    context.user_data['selected_count'] = count
    context.user_data['menu_for_day'] = menu_for_day
    # Проверяем, есть ли сохранённый адрес и телефон
    address_phone = context.user_data.get('address_phone')
    if address_phone:
        # Если есть, сразу отправляем админу
        user = update.message.from_user
        username = f"@{user.username}" if user.username else "(нет username)"
        admin_text = (
            f"Новый заказ!\n"
            f"День недели: {day}\n"
            f"Количество обедов: {count}\n"
            f"Меню: {menu_for_day}\n"
            f"Username: {username}\n"
            f"Адрес и телефон: {address_phone}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text)
        except Exception as e:
            logging.error(f"Ошибка отправки админу: {e}")
        keyboard = [[KeyboardButton("Посмотреть меню")], [KeyboardButton("Выбрать еще один день")]]
        await update.message.reply_text(
            f"В {day} вам будет доставлено {count} {menu_for_day}.\nСпасибо, ваш заказ принят, ожидайте получения…\nЧто дальше?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return MENU
    else:
        # Если нет, запрашиваем адрес и телефон
        reply_text = f"В {day} вам будет доставлено {count} {menu_for_day}. \n\nПожалуйста, уточните ваш адрес и номер телефона:"
        await update.message.reply_text(reply_text)
        return ORDER_COUNT

async def address_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address_phone_text = update.message.text
    # Сохраняем адрес и телефон для будущих заказов
    context.user_data['address_phone'] = address_phone_text
    day = context.user_data.get('selected_day', '(не выбран)')
    count = context.user_data.get('selected_count', '(не выбрано)')
    menu_for_day = context.user_data.get('menu_for_day', '')
    user = update.message.from_user
    username = f"@{user.username}" if user.username else "(нет username)"
    admin_text = (
        f"Новый заказ!\n"
        f"День недели: {day}\n"
        f"Количество обедов: {count}\n"
        f"Меню: {menu_for_day}\n"
        f"Username: {username}\n"
        f"Адрес и телефон: {address_phone_text}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text)
    except Exception as e:
        logging.error(f"Ошибка отправки админу: {e}")
    keyboard = [[KeyboardButton("Посмотреть меню")], [KeyboardButton("Выбрать еще один день")]]
    await update.message.reply_text(
        f"Спасибо, ваш заказ принят, ожидайте получения заказа в {day}\nВы можете сделать новый заказ или посмотреть меню. Выберите одну из опций.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return MENU

# Обработка некорректных действий
async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Пожалуйста, используйте кнопки для навигации.")
    return MENU

# Основная функция запуска
if __name__ == "__main__":
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU: [
                MessageHandler(filters.Regex("^Показать меню на неделю$"), show_menu),
                MessageHandler(filters.Regex("^Заказать обед$"), order_lunch),
                MessageHandler(filters.Regex("^Посмотреть меню$"), show_menu),
                MessageHandler(filters.Regex("^Выбрать еще один день$"), order_lunch)
            ],
            ORDER_DAY: [
                MessageHandler(filters.Regex("^(Понедельник|Вторник|Среда|Четверг|Пятница)$"), select_day),
                MessageHandler(filters.Regex("^Да$"), order_lunch)
            ],
            ORDER_COUNT: [
                MessageHandler(filters.Regex("^(1 обед|2 обеда|3 обеда|4 обеда)$"), select_count),
                MessageHandler(filters.TEXT & ~filters.COMMAND, address_phone)
            ]
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(filters.ALL, fallback)]
    )
    application.add_handler(conv_handler)
    logging.info("Бот запущен.")
    application.run_polling()
