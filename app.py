from flask import Flask, request
import os
import asyncio
import logging
import json
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

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get('BOT_TOKEN')

# ==================== СОСТОЯНИЯ ДЛЯ ConversationHandler ====================
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

# Создаем application
application = Application.builder().token(TOKEN).build()

# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================

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
    keyboard = []
    for day in WEEKDAYS:
        # 🔥 ИСПОЛЬЗУЕМ КОРОТКИЙ ФОРМАТ callback_data для надежности
        callback_data = f"day_{day}"
        keyboard.append([InlineKeyboardButton(day.capitalize(), callback_data=callback_data)])
    
    logger.info(f"Сгенерирована клавиатура с {len(keyboard)} кнопками")
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение и кнопки меню."""
    await update.message.reply_text(
        "Привет! Я бот-напоминалка, который поможет тебе не забыть о парах и дедлайнах. Выбери действие:",
        reply_markup=get_main_keyboard()
    )

# ==================== ОБРАБОТЧИКИ CALLBACK'ОВ ====================

async def global_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    🔥 ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ДЛЯ ВСЕХ CALLBACK'ОВ
    Этот обработчик ловит ВСЕ callback'и и логирует их для диагностики
    """
    query = update.callback_query
    await query.answer()  # Важно: всегда отвечаем на callback
    
    # 🔥 ЛОГИРУЕМ КАЖДЫЙ CALLBACK ДЛЯ ДИАГНОСТИКИ
    logger.info(f"📢 GLOBAL CALLBACK ПРИНЯТ: {query.data}")
    logger.info(f"👤 Пользователь: {query.from_user.id}")
    logger.info(f"💬 Сообщение: {query.message.message_id if query.message else 'No message'}")
    
    # Если callback не был обработан другими обработчиками
    await query.message.reply_text(
        "Эта кнопка пока не работает. Пожалуйста, используйте текстовые команды.", 
        reply_markup=get_main_keyboard()
    )

async def add_schedule_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    🔥 ОБРАБОТЧИК ВЫБОРА ДНЯ НЕДЕЛИ ИЗ ИНЛАЙН-КНОПОК
    """
    query = update.callback_query
    await query.answer()  # Важно: подтверждаем получение callback
    
    # 🔥 ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ ДЛЯ ДИАГНОСТИКИ
    logger.info(f"🎯 CALLBACK ВЫБОРА ДНЯ: {query.data}")
    logger.info(f"👤 Пользователь: {query.from_user.id}")
    
    try:
        # Извлекаем день из callback_data
        day = query.data.split('_')[1]  # формат: "day_понедельник"
        logger.info(f"📅 Выбран день: {day}")
        
        # Сохраняем в контексте
        if 'schedule_data' not in context.user_data:
            context.user_data['schedule_data'] = {}
        context.user_data['schedule_data']['day'] = day
        
        # 🔥 ПЫТАЕМСЯ ОТРЕДАКТИРОВАТЬ СООБЩЕНИЕ
        try:
            await query.edit_message_text(
                f"✅ Вы выбрали: {day.capitalize()}.\n\n"
                f"Теперь введите время начала и конца пары в формате:\n"
                f"<b>ЧЧ:ММ-ЧЧ:ММ</b>\n"
                f"Например: <i>14:30-15:30</i>",
                parse_mode='HTML'
            )
            logger.info("✅ Сообщение успешно отредактировано")
        except Exception as edit_error:
            logger.error(f"❌ Ошибка редактирования сообщения: {edit_error}")
            # 🔥 РЕЗЕРВНЫЙ ВАРИАНТ: отправляем новое сообщение
            await query.message.reply_text(
                f"✅ Вы выбрали: {day.capitalize()}.\n\n"
                f"Теперь введите время начала и конца пары в формате ЧЧ:ММ-ЧЧ:ММ\n"
                f"Например: 14:30-15:30",
                reply_markup=get_main_keyboard()
            )
        
        return ADD_SCHEDULE_TIME
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА в обработчике кнопок: {e}")
        # 🔥 РЕЗЕРВНЫЙ ВАРИАНТ ПРИ ЛЮБОЙ ОШИБКЕ
        await query.message.reply_text(
            "Произошла ошибка. Пожалуйста, введите день недели текстом:",
            reply_markup=get_main_keyboard()
        )
        return ADD_SCHEDULE_DAY

# ==================== ДИАЛОГ ДОБАВЛЕНИЯ РАСПИСАНИЯ ====================

async def start_add_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запускает диалог добавления расписания."""
    context.user_data['schedule_data'] = {}
    
    # 🔥 ЛОГИРУЕМ НАЧАЛО ПРОЦЕССА
    logger.info(f"🔄 Начало добавления расписания для пользователя {update.effective_user.id}")
    
    keyboard = get_weekday_keyboard()
    
    await update.message.reply_text(
        "📅 Отлично! На какой день недели назначена пара? Выберите из списка:",
        reply_markup=keyboard
    )
    return ADD_SCHEDULE_DAY

async def add_schedule_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет день (ручной ввод) и запрашивает время."""
    day = update.message.text.strip().lower()
    
    # Проверяем что день валидный
    if day not in WEEKDAYS:
        await update.message.reply_text(
            "❌ Пожалуйста, выберите корректный день недели из списка:",
            reply_markup=get_weekday_keyboard()
        )
        return ADD_SCHEDULE_DAY
    
    context.user_data['schedule_data']['day'] = day
    await update.message.reply_text(
        f"✅ Вы выбрали: {day.capitalize()}.\n\n"
        f"Теперь введите время начала и конца пары в формате ЧЧ:ММ-ЧЧ:ММ\n"
        f"Например: 14:30-15:30",
        reply_markup=get_main_keyboard()
    )
    return ADD_SCHEDULE_TIME

async def add_schedule_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет время и запрашивает название."""
    context.user_data['schedule_data']['time'] = update.message.text.strip()
    await update.message.reply_text(
        "Введите название предмета:\nНапример: <i>Математический анализ</i>",
        parse_mode='HTML',
        reply_markup=get_main_keyboard()
    )
    return ADD_SCHEDULE_CLASS

async def add_schedule_class(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет название и запрашивает преподавателя."""
    context.user_data['schedule_data']['className'] = update.message.text.strip()
    await update.message.reply_text(
        "Введите имя преподавателя:\nНапример: <i>Иванов И.И.</i>",
        parse_mode='HTML',
        reply_markup=get_main_keyboard()
    )
    return ADD_SCHEDULE_PROFESSOR

async def add_schedule_professor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет преподавателя и запрашивает время напоминания."""
    context.user_data['schedule_data']['professor'] = update.message.text.strip()
    await update.message.reply_text(
        "⏰ За сколько минут до начала пары напомнить?\n"
        "Введите число (например, 15):",
        reply_markup=get_main_keyboard()
    )
    return ADD_SCHEDULE_REMINDER

async def add_schedule_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет напоминание и добавляет запись в БД."""
    try:
        reminder_minutes = int(update.message.text.strip())
        context.user_data['schedule_data']['reminderBefore'] = reminder_minutes
        user_id = str(update.message.from_user.id)
        
        # Загружаем текущие данные
        user_data = await load_user_data(user_id)
        # Добавляем новое расписание
        user_data['schedule'].append(context.user_data['schedule_data'])
        # Сохраняем в БД
        await save_user_data(user_id, user_data['schedule'], user_data['deadlines'])
        
        await update.message.reply_text(
            "✅ Расписание успешно добавлено!",
            reply_markup=get_main_keyboard()
        )
        
        # 🔥 ЛОГИРУЕМ УСПЕШНОЕ ДОБАВЛЕНИЕ
        logger.info(f"✅ Добавлено расписание для пользователя {user_id}")
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введите числовое значение.",
            reply_markup=get_main_keyboard()
        )
        return ADD_SCHEDULE_REMINDER

# ==================== ДИАЛОГ ДОБАВЛЕНИЯ ДЕДЛАЙНА ====================

async def start_add_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запускает диалог добавления дедлайна."""
    context.user_data['deadline_data'] = {}
    await update.message.reply_text(
        "📝 Отлично! Как назовем дедлайн?",
        reply_markup=get_main_keyboard()
    )
    return ADD_DEADLINE_NAME

async def add_deadline_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет название дедлайна и запрашивает дату и время."""
    context.user_data['deadline_data']['name'] = update.message.text.strip()
    await update.message.reply_text(
        "📅 Введите дату и время дедлайна в формате:\n"
        "<b>ГГГГ-ММ-ДД ЧЧ:ММ</b>\n"
        "Например: <i>2024-12-25 10:00</i>",
        parse_mode='HTML',
        reply_markup=get_main_keyboard()
    )
    return ADD_DEADLINE_DATETIME

async def add_deadline_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет дату и время и запрашивает описание."""
    try:
        datetime.strptime(update.message.text.strip(), "%Y-%m-%d %H:%M")
        context.user_data['deadline_data']['datetime'] = update.message.text.strip()
        await update.message.reply_text(
            "📄 Введите описание дедлайна (необязательно):",
            reply_markup=get_main_keyboard()
        )
        return ADD_DEADLINE_DESCRIPTION
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат даты. Используйте: <b>ГГГГ-ММ-ДД ЧЧ:ММ</b>\n"
            "Например: 2024-12-25 10:00",
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
        return ADD_DEADLINE_DATETIME

async def add_deadline_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет описание и запрашивает время напоминания."""
    context.user_data['deadline_data']['description'] = update.message.text.strip()
    await update.message.reply_text(
        "⏰ За сколько минут до дедлайна напомнить?\n"
        "Введите число (например, 60):",
        reply_markup=get_main_keyboard()
    )
    return ADD_DEADLINE_REMINDER

async def add_deadline_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет время напоминания и добавляет запись в БД."""
    try:
        reminder_minutes = int(update.message.text.strip())
        context.user_data['deadline_data']['reminderBefore'] = reminder_minutes
        user_id = str(update.message.from_user.id)
        
        user_data = await load_user_data(user_id)
        user_data['deadlines'].append(context.user_data['deadline_data'])
        await save_user_data(user_id, user_data['schedule'], user_data['deadlines'])
        
        await update.message.reply_text(
            "✅ Дедлайн успешно добавлен!",
            reply_markup=get_main_keyboard()
        )
        
        logger.info(f"✅ Добавлен дедлайн для пользователя {user_id}")
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введите числовое значение.",
            reply_markup=get_main_keyboard()
        )
        return ADD_DEADLINE_REMINDER

# ==================== ПОКАЗ ДАННЫХ ====================

async def get_schedule(user_id):
    """Получает расписание пользователя."""
    user_data = await load_user_data(user_id)
    return user_data.get('schedule', [])

async def get_deadlines(user_id):
    """Получает дедлайны пользователя."""
    user_data = await load_user_data(user_id)
    return user_data.get('deadlines', [])

async def manage_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает расписание пользователя."""
    user_id = str(update.effective_user.id)
    items = await get_schedule(user_id)
    
    logger.info(f"📊 Запрос расписания от пользователя {user_id}, элементов: {len(items)}")
    
    if not items:
        await update.message.reply_text(
            "📭 Ваше расписание пусто.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    # Группируем по дням
    grouped = defaultdict(list)
    for item in items:
        if isinstance(item, dict) and 'day' in item:
            grouped[item['day']].append(item)
    
    text = "📅 Ваше расписание:\n\n"
    keyboard = []
    
    # Сортируем дни по порядку недели
    for day in WEEKDAYS:
        if day in grouped:
            text += f"<b>{day.capitalize()}</b>:\n"
            day_items = grouped[day]
            # Сортируем по времени
            try:
                day_items.sort(key=lambda x: x.get('time', ''))
            except:
                pass
            
            for i, item in enumerate(day_items, 1):
                text += f"{i}. {item.get('className', 'Без названия')}"
                if item.get('time'):
                    text += f" ({item['time']})"
                if item.get('professor'):
                    text += f" - {item['professor']}"
                text += "\n"
            
            keyboard.append([
                InlineKeyboardButton(f"✏️ {day.capitalize()}", callback_data=f"edit_day_{day}"),
            ])
            text += "\n"
    
    if len(text.strip()) <= 20:  # Если только заголовок
        await update.message.reply_text(
            "📭 Ваше расписание пусто.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        text, 
        parse_mode='HTML', 
        reply_markup=reply_markup
    )
    return EDIT_SCHEDULE_DAY

async def manage_deadlines(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает дедлайны пользователя."""
    user_id = str(update.effective_user.id)
    items = await get_deadlines(user_id)
    
    logger.info(f"📊 Запрос дедлайнов от пользователя {user_id}, элементов: {len(items)}")
    
    if not items:
        await update.message.reply_text(
            "📭 У вас нет дедлайнов.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    # Фильтруем валидные элементы
    valid_items = []
    for item in items:
        if isinstance(item, dict) and 'datetime' in item:
            try:
                datetime.strptime(item['datetime'], "%Y-%m-%d %H:%M")
                valid_items.append(item)
            except:
                continue
    
    if not valid_items:
        await update.message.reply_text(
            "📭 У вас нет дедлайнов.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    # Сортируем по дате
    try:
        valid_items.sort(key=lambda x: datetime.strptime(x['datetime'], "%Y-%m-%d %H:%M"))
    except Exception as e:
        logger.error(f"Ошибка сортировки дедлайнов: {e}")
    
    text = "📝 Ваши дедлайны:\n\n"
    keyboard = []
    
    for i, item in enumerate(valid_items, 1):
        try:
            deadline_dt = datetime.strptime(item['datetime'], "%Y-%m-%d %H:%M")
            formatted_date = deadline_dt.strftime('%d.%m.%Y %H:%M')
            
            text += f"{i}. <b>{item.get('name', 'Без названия')}</b> - до {formatted_date}\n"
            if item.get('description'):
                text += f"   Описание: {item['description']}\n"
            
            keyboard.append([
                InlineKeyboardButton(f"✏️ {item.get('name', 'Дедлайн')}", callback_data=f"edit_deadline_{i-1}"),
                InlineKeyboardButton(f"🗑️ {item.get('name', 'Дедлайн')}", callback_data=f"delete_deadline_{i-1}"),
            ])
        except Exception as e:
            logger.error(f"Ошибка форматирования дедлайна {item}: {e}")
            continue

    if len(text.strip()) <= 20:
        await update.message.reply_text(
            "📭 У вас нет дедлайнов.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        text, 
        parse_mode='HTML', 
        reply_markup=reply_markup
    )
    return EDIT_DEADLINE_FIELD

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def add_item(user_id, collection_name, item):
    """Добавляет элемент в коллекцию."""
    user_data = await load_user_data(user_id)
    user_data[collection_name].append(item)
    await save_user_data(user_id, user_data['schedule'], user_data['deadlines'])

async def update_item(user_id, collection_name, item_index, item):
    """Обновляет элемент в коллекции."""
    user_data = await load_user_data(user_id)
    user_data[collection_name][item_index] = item
    await save_user_data(user_id, user_data['schedule'], user_data['deadlines'])

async def delete_item(user_id, collection_name, item_index):
    """Удаляет элемент из коллекции."""
    user_data = await load_user_data(user_id)
    if 0 <= item_index < len(user_data[collection_name]):
        del user_data[collection_name][item_index]
        await save_user_data(user_id, user_data['schedule'], user_data['deadlines'])
        return True
    return False

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущий диалог."""
    await update.message.reply_text(
        "❌ Действие отменено.",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# ==================== РЕДАКТИРОВАНИЕ РАСПИСАНИЯ ====================

async def edit_schedule_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает пары выбранного дня для редактирования."""
    query = update.callback_query
    await query.answer()
    
    selected_day = query.data.split('_')[2]
    user_id = str(query.from_user.id)
    items = await get_schedule(user_id)
    
    day_items = [item for item in items if item['day'] == selected_day]
    day_items.sort(key=lambda x: x['time'])
    
    if not day_items:
        await query.edit_message_text(f"В {selected_day} у вас нет пар.")
        return ConversationHandler.END

    text = f"📅 Пары на {selected_day.capitalize()}:\n\n"
    keyboard = []
    
    for i, item in enumerate(day_items):
        text += f"{i+1}. {item['className']} ({item['time']}) - {item['professor']}\n"
        
        # Находим оригинальный индекс
        original_index = items.index(item)
        keyboard.append([
            InlineKeyboardButton(f"✏️ {item['className']}", callback_data=f"edit_schedule_{original_index}"),
            InlineKeyboardButton(f"🗑️ {item['className']}", callback_data=f"delete_schedule_{original_index}"),
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)
    return EDIT_SCHEDULE_FIELD

async def edit_schedule_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбирает поле для редактирования пары."""
    query = update.callback_query
    await query.answer()
    
    item_index = int(query.data.split('_')[2])
    context.user_data['schedule_index'] = item_index

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

async def edit_schedule_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает новое значение для выбранного поля пары."""
    query = update.callback_query
    await query.answer()

    context.user_data['schedule_field'] = query.data.split('_')[1]
    await query.edit_message_text("Введите новое значение:")
    
    return EDIT_SCHEDULE_VALUE

async def update_schedule_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обновляет значение пары."""
    user_id = str(update.effective_user.id)
    item_index = context.user_data['schedule_index']
    field = context.user_data['schedule_field']
    new_value = update.message.text.strip()
    
    if field == 'reminderBefore':
        try:
            new_value = int(new_value)
        except ValueError:
            await update.message.reply_text(
                "Пожалуйста, введите число для напоминания.",
                reply_markup=get_main_keyboard()
            )
            return EDIT_SCHEDULE_VALUE
    
    user_data = await load_user_data(user_id)
    if 0 <= item_index < len(user_data['schedule']):
        user_data['schedule'][item_index][field] = new_value
        await save_user_data(user_id, user_data['schedule'], user_data['deadlines'])
        await update.message.reply_text(
            "✅ Расписание обновлено!",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Ошибка: элемент не найден.",
            reply_markup=get_main_keyboard()
        )
    
    return ConversationHandler.END

# ==================== РЕДАКТИРОВАНИЕ ДЕДЛАЙНОВ ====================

async def edit_deadline_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбирает поле для редактирования дедлайна."""
    query = update.callback_query
    await query.answer()
    
    item_index = int(query.data.split('_')[2])
    context.user_data['deadline_index'] = item_index

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
    """Запрашивает новое значение для выбранного поля дедлайна."""
    query = update.callback_query
    await query.answer()

    context.user_data['deadline_field'] = query.data.split('_')[1]
    await query.edit_message_text("Введите новое значение:")
    
    return EDIT_DEADLINE_VALUE

async def update_deadline_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обновляет значение дедлайна."""
    user_id = str(update.effective_user.id)
    item_index = context.user_data['deadline_index']
    field = context.user_data['deadline_field']
    new_value = update.message.text.strip()
    
    if field == 'datetime':
        try:
            datetime.strptime(new_value, "%Y-%m-%d %H:%M")
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты. Используйте ГГГГ-ММ-ДД ЧЧ:ММ",
                reply_markup=get_main_keyboard()
            )
            return EDIT_DEADLINE_VALUE
    elif field == 'reminderBefore':
        try:
            new_value = int(new_value)
        except ValueError:
            await update.message.reply_text(
                "❌ Пожалуйста, введите число для напоминания.",
                reply_markup=get_main_keyboard()
            )
            return EDIT_DEADLINE_VALUE

    user_data = await load_user_data(user_id)
    if 0 <= item_index < len(user_data['deadlines']):
        user_data['deadlines'][item_index][field] = new_value
        await save_user_data(user_id, user_data['schedule'], user_data['deadlines'])
        await update.message.reply_text(
            "✅ Дедлайн обновлен!",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Ошибка: дедлайн не найден.",
            reply_markup=get_main_keyboard()
        )
    
    return ConversationHandler.END

# ==================== УДАЛЕНИЕ ====================

async def delete_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет элемент по нажатию кнопки."""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    parts = query.data.split('_')
    item_type = parts[1]
    item_index = int(parts[2])
    
    collection_name = 'schedule' if item_type == 'schedule' else 'deadlines'
    item_name = 'пару' if item_type == 'schedule' else 'дедлайн'
    
    success = await delete_item(user_id, collection_name, item_index)
    
    if success:
        await query.message.reply_text(
            f"✅ {item_name.capitalize()} успешно удален(а)!",
            reply_markup=get_main_keyboard()
        )
    else:
        await query.message.reply_text(
            "❌ Ошибка при удалении.",
            reply_markup=get_main_keyboard()
        )

# ==================== ОБРАБОТЧИКИ ОШИБОК ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"🚨 ОШИБКА: {context.error}")

# ==================== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ====================

def register_handlers():
    """
    🔥 ВАЖНО: Правильный порядок регистрации обработчиков
    1. Сначала обработчики callback'ов
    2. Потом команды
    3. В конце ConversationHandler
    """
    
    # 🔥 ШАГ 1: Регистрируем обработчики CALLBACK'ОВ ПЕРВЫМИ
    # Глобальный обработчик для всех callback'ов (должен быть первым)
    application.add_handler(CallbackQueryHandler(global_callback_handler, pattern=".*"))
    
    # Конкретные обработчики callback'ов
    application.add_handler(CallbackQueryHandler(add_schedule_day_callback, pattern="^day_"))
    application.add_handler(CallbackQueryHandler(delete_item_callback, pattern="^delete_schedule_"))
    application.add_handler(CallbackQueryHandler(delete_item_callback, pattern="^delete_deadline_"))
    
    # 🔥 ШАГ 2: Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    
    # 🔥 ШАГ 3: Регистрируем ConversationHandler ПОСЛЕДНИМИ
    
    # Добавление расписания
    conv_handler_add_schedule = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Добавить расписание$"), start_add_schedule)],
        states={
            ADD_SCHEDULE_DAY: [
                # 🔥 УБИРАЕМ CallbackQueryHandler отсюда - он уже зарегистрирован выше
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_schedule_day)
            ],
            ADD_SCHEDULE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_schedule_time)],
            ADD_SCHEDULE_CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_schedule_class)],
            ADD_SCHEDULE_PROFESSOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_schedule_professor)],
            ADD_SCHEDULE_REMINDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_schedule_reminder)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Добавление дедлайна
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

    # Редактирование расписания
    conv_handler_edit_schedule = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Мое расписание$"), manage_schedule)],
        states={
            EDIT_SCHEDULE_DAY: [CallbackQueryHandler(edit_schedule_day_callback, pattern="^edit_day_")],
            EDIT_SCHEDULE_FIELD: [CallbackQueryHandler(edit_schedule_item_callback, pattern="^edit_schedule_")],
            EDIT_SCHEDULE_VALUE: [
                CallbackQueryHandler(edit_schedule_field, pattern="^field_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_schedule_value)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Редактирование дедлайнов
    conv_handler_edit_deadline = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Мои дедлайны$"), manage_deadlines)],
        states={
            EDIT_DEADLINE_FIELD: [CallbackQueryHandler(edit_deadline_callback, pattern="^edit_deadline_")],
            EDIT_DEADLINE_VALUE: [
                CallbackQueryHandler(edit_deadline_field, pattern="^field_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_deadline_value)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Регистрируем ConversationHandler
    application.add_handler(conv_handler_add_schedule)
    application.add_handler(conv_handler_add_deadline)
    application.add_handler(conv_handler_edit_schedule)
    application.add_handler(conv_handler_edit_deadline)
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)

# ==================== FLASK WEBHOOK ====================

@app.route('/')
def index():
    return "🤖 Bot is running on Railway!"

@app.route('/webhook/' + TOKEN, methods=['POST'])
def webhook():
    """Endpoint для webhook."""
    try:
        json_data = request.get_json()
        
        # 🔥 ЛОГИРУЕМ ВХОДЯЩИЕ ДАННЫЕ
        if json_data and 'callback_query' in json_data:
            logger.info(f"📨 CALLBACK WEBHOOK: {json_data['callback_query']['data']}")
        elif json_data and 'message' in json_data:
            logger.info(f"📨 MESSAGE WEBHOOK: {json_data['message'].get('text', 'No text')}")
        
        if not json_data:
            logger.error("❌ Empty JSON in webhook")
            return 'empty json', 400
            
        update = Update.de_json(json_data, application.bot)
        
        # Обрабатываем update асинхронно
        async def process_update():
            await application.process_update(update)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_update())
        loop.close()
        
        return 'ok'
        
    except Exception as e:
        logger.error(f"🚨 Webhook error: {str(e)}")
        return 'error', 500

# ==================== ЗАПУСК ПРИЛОЖЕНИЯ ====================

if __name__ == '__main__':
    import threading
    
    def run_async_tasks():
        """Запускает асинхронные задачи в отдельном потоке."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Инициализация БД
            logger.info("🔄 Initializing database...")
            loop.run_until_complete(init_database())
            
            # Инициализация приложения
            logger.info("🔄 Initializing application...")
            loop.run_until_complete(application.initialize())
            
            # Установка webhook
            logger.info("🔄 Setting up webhook...")
            
            async def set_webhook_async():
                railway_url = os.environ.get('RAILWAY_STATIC_URL')
                if not railway_url:
                    logger.error("❌ RAILWAY_STATIC_URL not found!")
                    return False
                    
                if not railway_url.startswith('https://'):
                    railway_url = f"https://{railway_url}"
                    
                webhook_url = f"{railway_url}/webhook/{TOKEN}"
                logger.info(f"🌐 Setting webhook to: {webhook_url}")
                
                await application.bot.delete_webhook()
                result = await application.bot.set_webhook(webhook_url)
                logger.info(f"✅ Webhook set result: {result}")
                return True
            
            success = loop.run_until_complete(set_webhook_async())
            if success:
                logger.info("✅ Bot started with webhooks")
            else:
                logger.error("❌ Failed to setup webhook")
                
        except Exception as e:
            logger.error(f"❌ Failed to start bot: {e}")
    
    # Запускаем асинхронные задачи в отдельном потоке
    async_thread = threading.Thread(target=run_async_tasks, daemon=True)
    async_thread.start()
    
    # Регистрируем обработчики
    register_handlers()
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🚀 Starting Flask on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)