from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import sqlite3

ADMIN_USERNAME = "zzitraks"  # Username администратора
ADMIN_CHAT_ID = 1037859537  # Ваш chat_id для уведомлений

# Статусы для ConversationHandler
SELECT_FLAVOR, QUANTITY, CONTACT_INFO = range(3)

# Подключение и инициализация базы данных
def initialize_db():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        flavor TEXT,
        quantity INTEGER,
        status TEXT DEFAULT 'В обработке',
        contact_info TEXT
    )
    """)
    conn.commit()
    conn.close()

def add_order(user_id, username, flavor, quantity, contact_info):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO orders (user_id, username, flavor, quantity, contact_info)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, username, flavor, quantity, contact_info))
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()
    return order_id

def update_order_status(order_id, new_status):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    conn.close()

# Стартовая команда
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Сделать заказ", callback_data="make_order")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Добро пожаловать! Выберите опцию:", reply_markup=reply_markup)

# Обработка кнопки "Сделать заказ"
async def handle_make_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Шоколад", callback_data="flavor_Chocolate")],
        [InlineKeyboardButton("Ваниль", callback_data="flavor_Vanilla")],
        [InlineKeyboardButton("Клубника", callback_data="flavor_Strawberry")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите вкус:", reply_markup=reply_markup)
    return SELECT_FLAVOR

# Обработка выбора вкуса
async def flavor_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    flavor = query.data.split("_")[1]
    context.user_data['flavor'] = flavor
    await query.answer()
    await query.edit_message_text(f"Вы выбрали {flavor}. Укажите количество:")
    return QUANTITY

# Указание количества
async def collect_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        quantity = int(update.message.text)
        if quantity <= 0:
            raise ValueError("Invalid quantity")
        context.user_data['quantity'] = quantity
        await update.message.reply_text("Укажите ваш контакт (телефон или Telegram):")
        return CONTACT_INFO
    except ValueError:
        await update.message.reply_text("Введите корректное количество.")
        return QUANTITY

# Завершение заказа
async def finalize_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact_info = update.message.text
    context.user_data['contact_info'] = contact_info
    user_id = update.effective_user.id
    username = update.effective_user.username
    flavor = context.user_data['flavor']
    quantity = context.user_data['quantity']

    # Сохранение заказа
    order_id = add_order(user_id, username, flavor, quantity, contact_info)
    await update.message.reply_text("Ваш заказ принят. Ожидайте подтверждения!")

    keyboard = [
        [InlineKeyboardButton("Принять", callback_data=f"confirm_{order_id}")],
        [InlineKeyboardButton("Завершить", callback_data=f"complete_{order_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    admin_message = (
        f"🔔 Новый заказ!\n"
        f"ID: {order_id}\n"
        f"Пользователь: @{username if username else 'Неизвестно'}\n"
        f"Вкус: {flavor}\n"
        f"Количество: {quantity}\n"
        f"Контакт: {contact_info}"
    )
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_message, reply_markup=reply_markup)
    return ConversationHandler.END

# Принятие или завершение заказа
async def handle_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, order_id = query.data.split("_")
    order_id = int(order_id)

    if action == "confirm":
        update_order_status(order_id, "Подтвержден")
        conn = sqlite3.connect('orders.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
        user_id = cursor.fetchone()[0]
        conn.close()
        await context.bot.send_message(chat_id=user_id, text=f"Ваш заказ с ID {order_id} подтвержден!")
        await query.edit_message_text(f"Заказ с ID {order_id} принят.")
    elif action == "complete":
        update_order_status(order_id, "Выполнено")
        conn = sqlite3.connect('orders.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
        user_id = cursor.fetchone()[0]
        conn.close()
        await context.bot.send_message(chat_id=user_id, text=f"Ваш заказ с ID {order_id} завершён. Спасибо за покупку!")
        await query.edit_message_text(f"Заказ с ID {order_id} завершён.")

# Завершение заказа через команду
async def complete_order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    try:
        order_id = int(context.args[0])
        update_order_status(order_id, "Выполнено")
        conn = sqlite3.connect('orders.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
        user_id = cursor.fetchone()[0]
        conn.close()
        await context.bot.send_message(chat_id=user_id, text=f"Ваш заказ с ID {order_id} завершён. Спасибо за покупку!")
        await update.message.reply_text(f"Заказ с ID {order_id} завершён.")
    except (IndexError, ValueError):
        await update.message.reply_text("Пожалуйста, укажите корректный ID заказа.")

# Просмотр заказов
async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, flavor, quantity, contact_info, status FROM orders")
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        await update.message.reply_text("Нет текущих заказов.")
        return

    response = "📋 Текущие заказы:\n"
    for order in orders:
        response += (
            f"ID: {order[0]} | Пользователь: @{order[1]}\n"
            f"Вкус: {order[2]} | Количество: {order[3]}\n"
            f"Контакт: {order[4]} | Статус: {order[5]}\n"
            "----------------------\n"
        )
    await update.message.reply_text(response)

# Основная функция запуска
def main():
    initialize_db()
    app = Application.builder().token("7534331911:AAFlUuVfxM3tr1Lz86Fm-WMfzhI4EkfRYwA").build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('orders', show_orders))
    app.add_handler(CommandHandler('complete_order', complete_order_command))
    app.add_handler(CallbackQueryHandler(handle_admin_action, pattern="^(confirm|complete)_"))

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_make_order, pattern="make_order")],
        states={
            SELECT_FLAVOR: [CallbackQueryHandler(flavor_selected, pattern="^flavor_")],
            QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_quantity)],
            CONTACT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_order)],
        },
        fallbacks=[],
    )
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()