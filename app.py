from flask import Flask, request
import os
import asyncio
import logging
import json
import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
from database import init_database, save_user_data, load_user_data

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get('BOT_TOKEN', '8240746309:AAEqhznhHLgSd2K0QMpmdBQHMHIyJNdrYG8')

# Состояния для ConversationHandler
(
    ADD_SCHEDULE_DAY,
    ADD_SCHEDULE_TIME,
    ADD_SCHEDULE_CLASS,
    ADD_SCHEDULE_PROFESSOR,
    ADD_SCHEDULE_REMINDER,
    ADD_DEADLINE_NAME,
    ADD_DEADLINE_DATETIME,
    ADD_DEADLINE_DESCRIPTION,
    ADD_DEADLINE_REMINDER,
    EDIT_SCHEDULE_DAY,
    EDIT_SCHEDULE_FIELD,
    EDIT_SCHEDULE_VALUE,
    EDIT_DEADLINE_FIELD,
    EDIT_DEADLINE_VALUE,
) = range(14)

# Упорядоченный список дней недели
WEEKDAYS = [
    "понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"
]

# Маппинг английских дней недели на русские
RUSSIAN_WEEKDAYS = {
    'monday': 'понедельник',
    'tuesday': 'вторник', 
    'wednesday': 'среда',
    'thursday': 'четверг',
    'friday': 'пятница',
    'saturday': 'суббота',
    'sunday': 'воскресеньe'
}

# Создаем application
application = Application.builder().token(TOKEN).build()

# === ФУНКЦИИ ИЗ TypeKeeper.py ===

def get_main_keyboard():
    """Возвращает клавиатуру с основным меню."""
    keyboard = [
        [
            KeyboardButton("Добавить расписание"),
            KeyboardButton("Добавить дедлайн"),
        ],
        [
            KeyboardButton("Мое расписание"),
            KeyboardButton("Мои дедлайны"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_weekday_keyboard():
    """Возвращает инлайн-клавиатуру для выбора дня недели."""
    keyboard = [[InlineKeyboardButton(day.capitalize(), callback_data=f"select_day_{day}")] for day in WEEKDAYS]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение и кнопки меню."""
    await update.message.reply_text(
        "Привет! Я бот-напоминалка, который поможет тебе не забыть о парах и дедлайнах. Выбери действие:",
        reply_markup=get_main_keyboard()
    )

async def start_add_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запускает диалог добавления расписания."""
    context.user_data['schedule_data'] = {}
    await update.message.reply_text("Отлично! На какой день недели назначена пара? Выберите из списка или напишите вручную:", reply_markup=get_weekday_keyboard())
    return ADD_SCHEDULE_DAY

async def start_add_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запускает диалог добавления дедлайна."""
    context.user_data['deadline_data'] = {}
    await update.message.reply_text("Отлично! Как назовем дедлайн?", reply_markup=get_main_keyboard())
    return ADD_DEADLINE_NAME

async def add_schedule_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет день и запрашивает время (для ручного ввода)."""
    context.user_data['schedule_data']['day'] = update.message.text.strip().lower()
    await update.message.reply_text("Теперь введите время начала и конца пары в формате ЧЧ:ММ-ЧЧ:ММ (Например: 14:30-15:30)", reply_markup=get_main_keyboard())
    return ADD_SCHEDULE_TIME

async def add_schedule_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет день из кнопки и запрашивает время."""
    query = update.callback_query
    await query.answer()
    
    day = query.data.split('_')[2]
    context.user_data['schedule_data']['day'] = day
    
    await query.edit_message_text(f"Вы выбрали: {day.capitalize()}.\nТеперь введите время начала и конца пары в формате ЧЧ:ММ-ЧЧ:ММ (Например: 14:30-15:30)", reply_markup=None)
    
    return ADD_SCHEDULE_TIME

async def add_schedule_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет время и запрашивает название."""
    context.user_data['schedule_data']['time'] = update.message.text.strip()
    await update.message.reply_text("Введите название предмета (Например: Математический анализ)", reply_markup=get_main_keyboard())
    return ADD_SCHEDULE_CLASS

async def add_schedule_class(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет название и запрашивает преподавателя."""
    context.user_data['schedule_data']['className'] = update.message.text.strip()
    await update.message.reply_text("Введите имя преподавателя (Например: Иванов И.И.)", reply_markup=get_main_keyboard())
    return ADD_SCHEDULE_PROFESSOR

async def add_schedule_professor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет преподавателя и запрашивает время напоминания."""
    context.user_data['schedule_data']['professor'] = update.message.text.strip()
    await update.message.reply_text("За сколько минут до начала пары напомнить? Введите число (например, 15)", reply_markup=get_main_keyboard())
    return ADD_SCHEDULE_REMINDER

async def add_schedule_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет напоминание и добавляет запись в БД."""
    try:
        reminder_minutes = int(update.message.text.strip())
        context.user_data['schedule_data']['reminderBefore'] = reminder_minutes
        user_id = str(update.message.from_user.id)
        
        user_data = await load_user_data(user_id)
        user_data['schedule'].append(context.user_data['schedule_data'])
        save_user_data(user_id, user_data['schedule'], user_data['deadlines'])
        
        await update.message.reply_text("Расписание успешно добавлено!", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите числовое значение.", reply_markup=get_main_keyboard())
        return ADD_SCHEDULE_REMINDER

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущий диалог."""
    await update.message.reply_text("Действие отменено.", reply_markup=get_main_keyboard())
    return ConversationHandler.END

async def add_deadline_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет название дедлайна и запрашивает дату и время."""
    context.user_data['deadline_data']['name'] = update.message.text.strip()
    await update.message.reply_text("Введите дату и время дедлайна в формате ГГГГ-ММ-ДД ЧЧ:ММ (Например: 2024-12-25 10:00)", reply_markup=get_main_keyboard())
    return ADD_DEADLINE_DATETIME

async def add_deadline_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет дату и время и запрашивает описание."""
    try:
        datetime.strptime(update.message.text.strip(), "%Y-%m-%d %H:%M")
        context.user_data['deadline_data']['datetime'] = update.message.text.strip()
        await update.message.reply_text("Введите описание дедлайна (Необязательно, можно пропустить)", reply_markup=get_main_keyboard())
        return ADD_DEADLINE_DESCRIPTION
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Пожалуйста, попробуйте еще раз в формате ГГГГ-ММ-ДД ЧЧ:ММ.", reply_markup=get_main_keyboard())
        return ADD_DEADLINE_DATETIME

async def add_deadline_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет описание и запрашивает время напоминания."""
    context.user_data['deadline_data']['description'] = update.message.text.strip()
    await update.message.reply_text("За сколько минут до дедлайна напомнить? Введите число (например, 60)", reply_markup=get_main_keyboard())
    return ADD_DEADLINE_REMINDER

async def add_deadline_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет время напоминания и добавляет запись в БД."""
    try:
        reminder_minutes = int(update.message.text.strip())
        context.user_data['deadline_data']['reminderBefore'] = reminder_minutes
        user_id = str(update.message.from_user.id)
        
        user_data = await load_user_data(user_id)
        user_data['deadlines'].append(context.user_data['deadline_data'])
        save_user_data(user_id, user_data['schedule'], user_data['deadlines'])
        
        await update.message.reply_text("Дедлайн успешно добавлен!", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите числовое значение.", reply_markup=get_main_keyboard())
        return ADD_DEADLINE_REMINDER

async def get_schedule(user_id):
    """Получает расписание пользователя."""
    user_data = await load_user_data(user_id)
    return user_data.get('schedule', [])

async def get_deadlines(user_id):
    """Получает дедлайны пользователя."""
    user_data = await load_user_data(user_id)
    return user_data.get('deadlines', [])

async def add_item(user_id, collection_name, item):
    user_data = await load_user_data(user_id)
    user_data[collection_name].append(item)
    save_user_data(user_id, user_data['schedule'], user_data['deadlines'])

async def update_item(user_id, collection_name, item_index, item):
    user_data = await load_user_data(user_id)
    user_data[collection_name][item_index] = item
    save_user_data(user_id, user_data['schedule'], user_data['deadlines'])

async def delete_item(user_id, collection_name, item_index):
    user_data = await load_user_data(user_id)
    del user_data[collection_name][item_index]
    save_user_data(user_id, user_data['schedule'], user_data['deadlines'])

async def manage_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает список расписания с кнопками, сгруппированный по дням."""
    user_id = str(update.effective_user.id)
    items = await get_schedule(user_id)
    if not items:
        await update.message.reply_text("Ваше расписание пусто.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    grouped_schedule = defaultdict(list)
    for i, item in enumerate(items):
        item['original_index'] = i
        grouped_schedule[item['day'].capitalize()].append(item)

    text = "Ваше расписание:\n\n"
    keyboard = []
    
    sorted_days = sorted(grouped_schedule.keys(), key=lambda d: WEEKDAYS.index(d.lower()) if d.lower() in WEEKDAYS else len(WEEKDAYS))

    for day in sorted_days:
        text += f"**{day}**:\n"
        day_items = grouped_schedule[day]
        day_items.sort(key=lambda x: x['time'])
        
        day_item_count = 0
        for item in day_items:
            day_item_count += 1
            text += f"{day_item_count}. {item['className']}, {item['time']}, {item['professor']}\n"
        
        keyboard.append([
            InlineKeyboardButton(f"Редактировать {day}", callback_data=f"edit_day_{day}"),
        ])
        text += "\n"

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    return EDIT_SCHEDULE_DAY

async def manage_deadlines(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает список дедлайнов с кнопками."""
    user_id = str(update.effective_user.id)
    items = await get_deadlines(user_id)
    if not items:
        await update.message.reply_text("У вас нет дедлайнов.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    items.sort(key=lambda x: datetime.strptime(x['datetime'], "%Y-%m-%d %H:%M"))

    text = "Ваши дедлайны:\n\n"
    keyboard = []
    for i, item in enumerate(items):
        item['original_index'] = i
        try:
            deadline_dt = datetime.strptime(item['datetime'], "%Y-%m-%d %H:%M")
            formatted_date = deadline_dt.strftime('%d.%m.%Y %H:%M')
        except ValueError:
            formatted_date = "Неверный формат даты"
            
        text += f"{i + 1}. **{item['name']}**: до {formatted_date}\n"
        if item['description']:
            text += f"Описание: {item['description']}\n"
        keyboard.append([
            InlineKeyboardButton(f"Редактировать {item['name']}", callback_data=f"edit_deadline_{i}"),
            InlineKeyboardButton(f"Удалить {item['name']}", callback_data=f"delete_deadline_{i}"),
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    return EDIT_DEADLINE_FIELD

async def edit_schedule_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает список пар для выбранного дня."""
    query = update.callback_query
    await query.answer()
    
    selected_day = query.data.split('_')[2]
    context.user_data['selected_day'] = selected_day
    
    user_id = str(query.from_user.id)
    items = await get_schedule(user_id)
    
    day_items = sorted([item for item in items if item['day'].lower() == selected_day.lower()], key=lambda x: x['time'])
    
    if not day_items:
        await query.edit_message_text(f"В этот день у вас нет пар.")
        return ConversationHandler.END

    text = f"Пары на {selected_day.capitalize()}:\n\n"
    keyboard = []
    for i, item in enumerate(day_items):
        text += f"{i+1}. {item['className']}, {item['time']}, {item['professor']}\n"
        original_index = items.index(item)
        keyboard.append([
            InlineKeyboardButton(f"Редактировать {item['className']}", callback_data=f"edit_item_{original_index}"),
            InlineKeyboardButton(f"Удалить {item['className']}", callback_data=f"delete_schedule_{original_index}"),
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)
    
    return EDIT_SCHEDULE_FIELD

async def edit_schedule_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбирает поле для редактирования для конкретной пары."""
    query = update.callback_query
    await query.answer()
    
    item_index = int(query.data.split('_')[2])
    context.user_data['item_index'] = item_index

    keyboard = [
        [InlineKeyboardButton("День", callback_data="field_day")],
        [InlineKeyboardButton("Время", callback_data="field_time")],
        [InlineKeyboardButton("Предмет", callback_data="field_className")],
        [InlineKeyboardButton("Преподаватель", callback_data="field_professor")],
        [InlineKeyboardButton("Напоминание", callback_data="field_reminderBefore")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text("Что вы хотите отредактировать?", reply_markup=reply_markup)
    return EDIT_SCHEDULE_VALUE

async def edit_schedule_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает новое значение для выбранного поля."""
    query = update.callback_query
    await query.answer()

    context.user_data['field_to_edit'] = query.data.split('_')[1]
    await query.edit_message_text("Введите новое значение:", reply_markup=None)
    
    return ConversationHandler.END

async def update_schedule_value_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = str(update.effective_user.id)
    item_index = context.user_data['item_index']
    field_to_edit = context.user_data['field_to_edit']
    new_value = update.message.text.strip()
    
    if field_to_edit == 'reminderBefore':
        try:
            new_value = int(new_value)
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите числовое значение для напоминания.", reply_markup=get_main_keyboard())
            return EDIT_SCHEDULE_VALUE
        
    user_data = await load_user_data(user_id)
    if item_index >= len(user_data['schedule']):
        await update.message.reply_text("Произошла ошибка. Пожалуйста, начните редактирование заново.", reply_markup=get_main_keyboard())
        return ConversationHandler.END
        
    item = user_data['schedule'][item_index]
    item[field_to_edit] = new_value
    save_user_data(user_id, user_data['schedule'], user_data['deadlines'])
    
    await update.message.reply_text("Расписание успешно обновлено!", reply_markup=get_main_keyboard())
    return ConversationHandler.END

async def edit_deadline_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбирает поле для редактирования для конкретного дедлайна."""
    query = update.callback_query
    await query.answer()
    
    item_index = int(query.data.split('_')[2])
    context.user_data['item_index'] = item_index

    keyboard = [
        [InlineKeyboardButton("Название", callback_data="field_name")],
        [InlineKeyboardButton("Дата и время", callback_data="field_datetime")],
        [InlineKeyboardButton("Описание", callback_data="field_description")],
        [InlineKeyboardButton("Напоминание", callback_data="field_reminderBefore")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text("Что вы хотите отредактировать?", reply_markup=reply_markup)
    return EDIT_DEADLINE_VALUE

async def edit_deadline_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает новое значение для выбранного поля."""
    query = update.callback_query
    await query.answer()

    context.user_data['field_to_edit'] = query.data.split('_')[1]
    await query.edit_message_text("Введите новое значение:", reply_markup=None)
    
    return ConversationHandler.END

async def update_deadline_value_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обновляет значение в дедлайне."""
    user_id = str(update.effective_user.id)
    item_index = context.user_data['item_index']
    field_to_edit = context.user_data['field_to_edit']
    new_value = update.message.text.strip()
    
    if field_to_edit == 'datetime':
        try:
            datetime.strptime(new_value, "%Y-%m-%d %H:%M")
        except ValueError:
            await update.message.reply_text("Неверный формат даты. Пожалуйста, попробуйте еще раз в формате ГГГГ-ММ-ДД ЧЧ:ММ.", reply_markup=get_main_keyboard())
            return EDIT_DEADLINE_VALUE
    elif field_to_edit == 'reminderBefore':
        try:
            new_value = int(new_value)
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите числовое значение для напоминания.", reply_markup=get_main_keyboard())
            return EDIT_DEADLINE_VALUE

    user_data = await load_user_data(user_id)
    if item_index >= len(user_data['deadlines']):
        await update.message.reply_text("Произошла ошибка. Пожалуйста, начните редактирование заново.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    item = user_data['deadlines'][item_index]
    item[field_to_edit] = new_value
    save_user_data(user_id, user_data['schedule'], user_data['deadlines'])
    
    await update.message.reply_text("Дедлайн успешно обновлен!", reply_markup=get_main_keyboard())
    return ConversationHandler.END

async def delete_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет элемент по нажатию кнопки."""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    parts = query.data.split('_')
    item_type = parts[1]
    item_index = int(parts[2])
    collection_name = 'schedule' if item_type == 'schedule' else 'deadlines'
    
    await delete_item(user_id, collection_name, item_index)
    await query.message.reply_text(f"{'Пара' if item_type == 'schedule' else 'Дедлайн'} успешно удалена!", reply_markup=get_main_keyboard())

async def schedule_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверяет расписание и отправляет напоминания."""
    # Для упрощения временно отключим напоминания в этой версии
    pass

async def deadline_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверяет дедлайны и отправляет напоминания."""
    # Для упрощения временно отключим напоминания в этой версии
    pass

# === FLASK WEBHOOK HANDLING ===

def register_handlers():
    """Регистрирует все обработчики"""
    application.add_handler(CommandHandler("start", start))
    
    # ConversationHandler для добавления расписания
    conv_handler_add_schedule = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Добавить расписание$"), start_add_schedule)],
        states={
            ADD_SCHEDULE_DAY: [
                CallbackQueryHandler(add_schedule_day_callback, pattern="^select_day_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_schedule_day)
            ],
            ADD_SCHEDULE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_schedule_time)],
            ADD_SCHEDULE_CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_schedule_class)],
            ADD_SCHEDULE_PROFESSOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_schedule_professor)],
            ADD_SCHEDULE_REMINDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_schedule_reminder)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # ConversationHandler для добавления дедлайна
    conv_handler_add_deadline = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Добавить дедлайн$"), start_add_deadline)],
        states={
            ADD_DEADLINE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_deadline_name)],
            ADD_DEADLINE_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_deadline_datetime)],
            ADD_DEADLINE_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_deadline_description)],
            ADD_DEADLINE_REMINDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_deadline_reminder)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # ConversationHandler для редактирования расписания
    conv_handler_edit_schedule = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Мое расписание$"), manage_schedule)],
        states={
            EDIT_SCHEDULE_DAY: [CallbackQueryHandler(edit_schedule_day_callback, pattern="^edit_day_")],
            EDIT_SCHEDULE_FIELD: [CallbackQueryHandler(edit_schedule_item_callback, pattern="^edit_item_")],
            EDIT_SCHEDULE_VALUE: [
                CallbackQueryHandler(edit_schedule_value, pattern="^field_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_schedule_value_from_text)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # ConversationHandler для редактирования дедлайна
    conv_handler_edit_deadline = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Мои дедлайны$"), manage_deadlines)],
        states={
            EDIT_DEADLINE_FIELD: [CallbackQueryHandler(edit_deadline_callback, pattern="^edit_deadline_")],
            EDIT_DEADLINE_VALUE: [
                CallbackQueryHandler(edit_deadline_field, pattern="^field_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_deadline_value_from_text)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler_add_schedule)
    application.add_handler(conv_handler_add_deadline)
    application.add_handler(conv_handler_edit_schedule)
    application.add_handler(conv_handler_edit_deadline)
    
    # Отдельные обработчики для удаления
    application.add_handler(CallbackQueryHandler(delete_item_callback, pattern="^delete_"))

@app.route('/')
def index():
    logger.info("Health check received")
    return "Bot is running with webhooks!"

@app.route('/webhook/' + TOKEN, methods=['POST'])
def webhook():
    """Endpoint для получения обновлений от Telegram"""
    try:
        logger.info("Webhook request received")
        
        json_data = request.get_json()
        
        if not json_data:
            logger.error("Empty JSON in webhook request")
            return 'empty json', 400
            
        logger.info(f"Update type: {json_data.keys()}")
        
        update = Update.de_json(json_data, application.bot)
        
        # 🔥 СИНХРОННАЯ ОБРАБОТКА - сразу обрабатываем
        async def process():
            try:
                await application.process_update(update)
                logger.info("Update processed successfully")
            except Exception as e:
                logger.error(f"Error processing update: {e}")
        
        # Создаем и запускаем event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process())
        loop.close()
        
        return 'ok'
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return 'error', 500
def setup_webhook():
    """Устанавливает webhook"""
    try:
        railway_url = os.environ.get('RAILWAY_STATIC_URL')
        if not railway_url:
            logger.error("RAILWAY_STATIC_URL not found!")
            return False
            
        # 🔥 ДОБАВЛЯЕМ https:// к URL
        if not railway_url.startswith('https://'):
            railway_url = f"https://{railway_url}"
            
        webhook_url = f"{railway_url}/webhook/{TOKEN}"
        logger.info(f"Setting webhook to: {webhook_url}")
        
        # Устанавливаем webhook синхронно
        async def set_wh():
            # Сначала удаляем старый webhook
            await application.bot.delete_webhook()
            # Затем устанавливаем новый
            result = await application.bot.set_webhook(webhook_url)
            logger.info(f"Webhook set result: {result}")
            
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(set_wh())
        loop.close()
        
        logger.info("Webhook set successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        return False


if __name__ == '__main__':
    # Инициализируем базу данных
    init_database()
    
    # Регистрируем обработчики
    register_handlers()
    
    # Устанавливаем webhook
    if setup_webhook():
        logger.info("✅ Bot started with webhooks")
    else:
        logger.error("❌ Failed to setup webhook")
    
    # Запускаем Flask в отдельном потоке
    port = int(os.environ.get('PORT', 8080))
    
    def run_flask():
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info(f"Flask started in background on port {port}")
    
    # 🔥 БЕСКОНЕЧНЫЙ ЦИКЛ - ГЛАВНОЕ ИСПРАВЛЕНИЕ
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")