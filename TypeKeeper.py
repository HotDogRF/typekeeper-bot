
import logging
import asyncio
import json
import os
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
from database import init_database, save_user_data, load_user_data, get_db_connection

# Включаем логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Получаем токен из переменных окружения (для Railway) или используем по умолчанию
TOKEN = os.getenv('BOT_TOKEN', '8240746309:AAEqhznhHLgSd2K0QMpmdBQHMHIyJNdrYG8')
DATA_FILE = 'data.json'

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

# --- Хелперы для работы с локальными данными ---

def load_data():
    """Загружает данные из локального JSON-файла."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return {}

def save_data(data):
    """Сохраняет данные в локальный JSON-файл."""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def save_user_data(user_id, schedule, deadlines):
    """Сохраняет данные пользователя в базу данных"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO users (user_id, schedule, deadlines)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                schedule = EXCLUDED.schedule,
                deadlines = EXCLUDED.deadlines
        ''', (user_id, json.dumps(schedule), json.dumps(deadlines)))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False
    finally:
        conn.close()

async def get_schedule(user_id):
    """Получает расписание пользователя."""
    user_data = await load_user_data(user_id)
    return user_data.get('schedule', [])

async def get_deadlines(user_id):
    """Получает дедлайны пользователя."""
    user_data = await load_user_data(user_id)
    return user_data.get('deadlines', [])

async def add_item(user_id, collection_name, item):
    user_data = await load_user_data(user_id)                    # ← изменили
    user_data[collection_name].append(item)
    save_user_data(user_id, user_data['schedule'], user_data['deadlines'])  # ← изменили

async def update_item(user_id, collection_name, item_index, item):
    user_data = await load_user_data(user_id)                    # ← изменили
    user_data[collection_name][item_index] = item
    save_user_data(user_id, user_data['schedule'], user_data['deadlines'])  # ← изменили

async def delete_item(user_id, collection_name, item_index):
    user_data = await load_user_data(user_id)                    # ← изменили
    del user_data[collection_name][item_index]
    save_user_data(user_id, user_data['schedule'], user_data['deadlines'])  # ← изменили

# --- Клавиатуры ---

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

# --- Команды бота ---

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

# --- Диалог добавления расписания ---

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
        await add_item(user_id, "schedule", context.user_data['schedule_data'])
        await update.message.reply_text("Расписание успешно добавлено!", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите числовое значение.", reply_markup=get_main_keyboard())
        return ADD_SCHEDULE_REMINDER

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущий диалог."""
    await update.message.reply_text("Действие отменено.", reply_markup=get_main_keyboard())
    return ConversationHandler.END

# --- Диалог добавления дедлайна ---
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
        await add_item(user_id, "deadlines", context.user_data['deadline_data'])
        await update.message.reply_text("Дедлайн успешно добавлен!", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите числовое значение.", reply_markup=get_main_keyboard())
        return ADD_DEADLINE_REMINDER


# --- Управление данными ---

async def manage_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает список расписания с кнопками, сгруппированный по дням."""
    user_id = str(update.effective_user.id)
    items = await get_schedule(user_id)
    if not items:
        await update.message.reply_text("Ваше расписание пусто.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    # Группируем расписание по дням
    grouped_schedule = defaultdict(list)
    for i, item in enumerate(items):
        item['original_index'] = i
        grouped_schedule[item['day'].capitalize()].append(item)

    text = "Ваше расписание:\n\n"
    keyboard = []
    
    # Сортируем дни по заданному порядку
    sorted_days = sorted(grouped_schedule.keys(), key=lambda d: WEEKDAYS.index(d.lower()) if d.lower() in WEEKDAYS else len(WEEKDAYS))

    for day in sorted_days:
        text += f"**{day}**:\n"
        day_items = grouped_schedule[day]
        # Сортируем пары внутри каждого дня по времени
        day_items.sort(key=lambda x: x['time'])
        
        day_item_count = 0
        for item in day_items:
            day_item_count += 1
            text += f"{day_item_count}. {item['className']}, {item['time']}, {item['professor']}\n"
        
        # Добавляем кнопки для редактирования всего дня и удаления
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

    # Сортируем дедлайны по дате
    items.sort(key=lambda x: datetime.strptime(x['datetime'], "%Y-%m-%d %H:%M"))

    text = "Ваши дедлайны:\n\n"
    keyboard = []
    for i, item in enumerate(items):
        item['original_index'] = i # Добавляем original_index
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

# --- Диалог редактирования расписания ---

async def edit_schedule_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает список пар для выбранного дня."""
    query = update.callback_query
    await query.answer()
    
    selected_day = query.data.split('_')[2]
    context.user_data['selected_day'] = selected_day
    
    user_id = str(query.from_user.id)
    items = await get_schedule(user_id)
    
    # Фильтруем и сортируем пары для выбранного дня
    day_items = sorted([item for item in items if item['day'].lower() == selected_day.lower()], key=lambda x: x['time'])
    
    if not day_items:
        await query.edit_message_text(f"В этот день у вас нет пар.")
        return ConversationHandler.END

    text = f"Пары на {selected_day.capitalize()}:\n\n"
    keyboard = []
    for i, item in enumerate(day_items):
        text += f"{i+1}. {item['className']}, {item['time']}, {item['professor']}\n"
        # original_index нужен, чтобы найти правильный элемент в общем списке
        original_index = items.index(item)
        keyboard.append([
            InlineKeyboardButton(f"Редактировать {item['className']}", callback_data=f"edit_item_{original_index}"),
            InlineKeyboardButton(f"Удалить {item['className']}", callback_data=f"delete_schedule_{original_index}"),
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)
    
    return EDIT_SCHEDULE_FIELD # Переходим к выбору поля

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
    # Check if item_index is valid
    if item_index >= len(user_data['schedule']):
        await update.message.reply_text("Произошла ошибка. Пожалуйста, начните редактирование заново.", reply_markup=get_main_keyboard())
        return ConversationHandler.END
        
    item = user_data['schedule'][item_index]
    item[field_to_edit] = new_value
    save_user_data(user_id, user_data['schedule'], user_data['deadlines'])
    
    await update.message.reply_text("Расписание успешно обновлено!", reply_markup=get_main_keyboard())
    return ConversationHandler.END

# --- Диалог редактирования дедлайна ---
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


# --- Обработчики нажатий кнопок ---
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

# --- Напоминания ---

async def schedule_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверяет расписание и отправляет напоминания."""
    data = load_data()
    now = datetime.now()
    current_day = now.strftime('%A').lower()
    current_time_minutes = now.hour * 60 + now.minute

    for user_id, user_data in data.items():
        schedule_items = user_data.get('schedule', [])
        for item in schedule_items:
            try:
                # Парсим время начала и конца пары
                start_time_str = item['time'].split('-')[0].strip()
                end_time_str = item['time'].split('-')[1].strip()

                time_obj = datetime.strptime(start_time_str, "%H:%M").time()
                schedule_time_minutes = time_obj.hour * 60 + time_obj.minute
                
                # Отправляем напоминание за указанное пользователем время
                reminder_minutes = item.get('reminderBefore', 15)
                if item['day'] == current_day and (schedule_time_minutes - current_time_minutes) == reminder_minutes:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"🔔 Напоминание: через {reminder_minutes} минут(у) начинается пара: **{item['className']}**. Преподаватель: {item['professor']}.",
                        parse_mode='Markdown'
                    )
            except (ValueError, KeyError) as e:
                logging.error(f"Ошибка в данных расписания для пользователя {user_id}: {e}")

async def deadline_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверяет дедлайны и отправляет напоминания."""
    data = load_data()
    now = datetime.now()
    
    for user_id, user_data in data.items():
        deadlines = user_data.get('deadlines', [])
        for item in deadlines:
            try:
                deadline_dt = datetime.strptime(item['datetime'], "%Y-%m-%d %H:%M")
                reminder_minutes = item.get('reminderBefore', 60)
                reminder_dt = deadline_dt - timedelta(minutes=reminder_minutes)
                
                # Проверяем, что текущее время попадает в одноминутный интервал после времени напоминания
                if now > reminder_dt and now < reminder_dt + timedelta(minutes=1):
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"⚠️ Напоминание! Дедлайн по **{item['name']}** наступит через {reminder_minutes} минут(у).",
                        parse_mode='Markdown'
                    )
            except (ValueError, KeyError) as e:
                logging.error(f"Ошибка в данных дедлайна для пользователя {user_id}: {e}")

def main() -> None:
    # Инициализируем базу данных
    init_database()

    """Основная функция для запуска бота."""
    # Упрощенная проверка токена
    if not TOKEN:
        logging.error("❌ Токен бота не установлен!")
        print("❌ Токен бота не установлен! Проверьте переменную BOT_TOKEN в Railway.")
        return
    
    print(f"✅ Токен получен, запускаю бота...")
    
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
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
    
    # Отдельные обработчики для удаления, чтобы они работали вне диалогов
    application.add_handler(CallbackQueryHandler(delete_item_callback, pattern="^delete_"))

    # Запускаем фоновые задачи для напоминаний (если JobQueue доступен)
    if application.job_queue:
        job_queue = application.job_queue
        job_queue.run_repeating(schedule_reminder_job, interval=60, first=5)
        job_queue.run_repeating(deadline_reminder_job, interval=60, first=10)
        print("✅ JobQueue запущен для напоминаний")
    else:
        print("⚠️ JobQueue недоступен. Напоминания не будут работать.")
        
    # 🔧 ЗАПУСК НА RAILWAY (исправленная версия)
    port = int(os.environ.get('PORT', 8080))
    webhook_url = os.environ.get('RAILWAY_STATIC_URL')

    if webhook_url:
        # Используем вебхук на Railway
        logging.info("🚀 Запуск через вебхук на Railway...")
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=TOKEN,
            webhook_url=f"{webhook_url}/{TOKEN}",
            drop_pending_updates=True
        )
    else:
        # Используем polling для локальной разработки
        logging.info("🚀 Запуск через polling...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

if __name__ == "__main__":
    main()