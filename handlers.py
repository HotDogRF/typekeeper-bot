"""
Все обработчики команд бота
"""
import logging
import re
from datetime import datetime
from typing import Dict, List

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from keyboards import (
    get_main_keyboard, 
    get_weekday_keyboard,
    get_cancel_keyboard,
    WEEKDAYS
)
from storage import user_storage

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
(
    ADD_SCHEDULE_DAY,
    ADD_SCHEDULE_TIME,
    ADD_SCHEDULE_CLASS,
    ADD_SCHEDULE_PROFESSOR,
    ADD_SCHEDULE_REMINDER,
    ADD_DEADLINE_NAME,
    ADD_DEADLINE_DATE,
    ADD_DEADLINE_DESC,
    ADD_DEADLINE_REMINDER
) = range(9)

# ==================== УПРОЩЕННЫЕ ОБРАБОТЧИКИ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user_id = update.effective_user.id
    
    # Создаем пользователя если нет
    await user_storage.update_user_data(user_id)
    
    await update.message.reply_text(
        "👋 Привет! Я бот-напоминалка для студентов.\n"
        "Я помогу не забыть о парах и дедлайнах.\n\n"
        "Выбери действие на клавиатуре:",
        reply_markup=get_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = """
📚 **Доступные команды:**

**Основные действия:**
📅 Добавить расписание - Добавить новую пару в расписание
⏰ Добавить дедлайн - Добавить новый дедлайн
📋 Мое расписание - Посмотреть и редактировать расписание
📝 Мои дедлайны - Посмотреть и редактировать дедлайны

**Дополнительные команды:**
/start - Перезапустить бота
/help - Показать это сообщение
/reset - Сбросить все данные

**Форматы данных:**
- День недели: понедельник, вторник и т.д.
- Время пары: 14:30-16:00
- Дата и время дедлайна: 2024-12-31 23:59
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс всех данных пользователя"""
    user_id = update.effective_user.id
    await user_storage.update_user_data(user_id, schedule=[], deadlines=[])
    await user_storage.clear_user_state(user_id)
    
    await update.message.reply_text(
        "✅ Все данные сброшены. Вы можете начать заново.",
        reply_markup=get_main_keyboard()
    )

# ==================== ДОБАВЛЕНИЕ РАСПИСАНИЯ ====================

async def start_add_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало добавления расписания"""
    # Инициализируем данные
    context.user_data['schedule_data'] = {}
    
    await update.message.reply_text(
        "📅 Выберите день недели для пары:",
        reply_markup=get_weekday_keyboard()
    )
    return ADD_SCHEDULE_DAY

async def add_schedule_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора дня через callback"""
    query = update.callback_query
    await query.answer()
    
    day = query.data.split('_')[1]
    
    # Сохраняем день в данных
    context.user_data['schedule_data']['day'] = day
    
    # Удаляем старое сообщение с инлайн-клавиатурой
    await query.delete_message()
    
    # Отправляем новое сообщение с reply-клавиатурой
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            f"📅 День: **{day.capitalize()}**\n\n"
            f"🕐 Введите время начала и конца пары:\n"
            f"Формат: **ЧЧ:ММ-ЧЧ:ММ**\n"
            f"Пример: *14:30-16:00*"
        ),
        parse_mode='Markdown',
        reply_markup=get_cancel_keyboard()
    )
    return ADD_SCHEDULE_TIME

async def add_schedule_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод времени пары"""
    time_input = update.message.text.strip()
    
    # Проверяем формат
    if not re.match(r'^\d{2}:\d{2}-\d{2}:\d{2}$', time_input):
        await update.message.reply_text(
            "❌ Неверный формат времени.\n"
            "Используйте: **ЧЧ:ММ-ЧЧ:ММ**\n"
            "Пример: *09:00-10:30*",
            parse_mode='Markdown',
            reply_markup=get_cancel_keyboard()
        )
        return ADD_SCHEDULE_TIME
    
    context.user_data['schedule_data']['time'] = time_input
    
    await update.message.reply_text(
        "📚 Введите название предмета:",
        reply_markup=get_cancel_keyboard()
    )
    return ADD_SCHEDULE_CLASS

async def add_schedule_class(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод названия предмета"""
    class_name = update.message.text.strip()
    context.user_data['schedule_data']['className'] = class_name
    
    await update.message.reply_text(
        "👨‍🏫 Введите имя преподавателя:",
        reply_markup=get_cancel_keyboard()
    )
    return ADD_SCHEDULE_PROFESSOR

async def add_schedule_professor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод имени преподавателя"""
    professor = update.message.text.strip()
    context.user_data['schedule_data']['professor'] = professor
    
    await update.message.reply_text(
        "⏰ За сколько минут до начала пары напомнить?\n"
        "Введите число (например, 15):",
        reply_markup=get_cancel_keyboard()
    )
    return ADD_SCHEDULE_REMINDER

async def add_schedule_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод времени напоминания и сохранение"""
    user_id = update.effective_user.id
    
    try:
        reminder = int(update.message.text.strip())
        context.user_data['schedule_data']['reminderBefore'] = reminder
        
        # Загружаем текущее расписание
        user_data = await user_storage.get_user_data(user_id)
        schedule = user_data['schedule']
        
        # Добавляем новую запись
        schedule.append(context.user_data['schedule_data'])
        
        # Сохраняем
        await user_storage.update_user_data(
            user_id,
            schedule=schedule
        )
        
        # Очищаем временные данные
        context.user_data.pop('schedule_data', None)
        
        await update.message.reply_text(
            "✅ Пара успешно добавлена в расписание!",
            reply_markup=get_main_keyboard()
        )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введите целое число.",
            reply_markup=get_cancel_keyboard()
        )
        return ADD_SCHEDULE_REMINDER

# ==================== ДОБАВЛЕНИЕ ДЕДЛАЙНА ====================

async def start_add_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало добавления дедлайна"""
    context.user_data['deadline_data'] = {}
    
    await update.message.reply_text(
        "📝 Введите название дедлайна:",
        reply_markup=get_cancel_keyboard()
    )
    return ADD_DEADLINE_NAME

async def add_deadline_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод названия дедлайна"""
    name = update.message.text.strip()
    context.user_data['deadline_data']['name'] = name
    
    await update.message.reply_text(
        "📅 Введите дату и время дедлайна:\n"
        "Формат: **ГГГГ-ММ-ДД ЧЧ:ММ**\n"
        "Пример: *2024-12-31 23:59*",
        parse_mode='Markdown',
        reply_markup=get_cancel_keyboard()
    )
    return ADD_DEADLINE_DATE

async def add_deadline_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод даты дедлайна"""
    date_input = update.message.text.strip()
    
    try:
        # Проверяем формат
        datetime.strptime(date_input, "%Y-%m-%d %H:%M")
        context.user_data['deadline_data']['datetime'] = date_input
        
        await update.message.reply_text(
            "📄 Введите описание дедлайна (необязательно):\n"
            "Или отправьте '-' чтобы пропустить",
            reply_markup=get_cancel_keyboard()
        )
        return ADD_DEADLINE_DESC
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат даты.\n"
            "Используйте: **ГГГГ-ММ-ДД ЧЧ:ММ**\n"
            "Пример: *2024-12-31 23:59*",
            parse_mode='Markdown',
            reply_markup=get_cancel_keyboard()
        )
        return ADD_DEADLINE_DATE

async def add_deadline_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод описания дедлайна"""
    description = update.message.text.strip()
    if description == '-':
        description = ""
    
    context.user_data['deadline_data']['description'] = description
    
    await update.message.reply_text(
        "⏰ За сколько минут до дедлайна напомнить?\n"
        "Введите число (например, 60):",
        reply_markup=get_cancel_keyboard()
    )
    return ADD_DEADLINE_REMINDER

async def add_deadline_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод напоминания и сохранение дедлайна"""
    user_id = update.effective_user.id
    
    try:
        reminder = int(update.message.text.strip())
        context.user_data['deadline_data']['reminderBefore'] = reminder
        
        # Загружаем текущие дедлайны
        user_data = await user_storage.get_user_data(user_id)
        deadlines = user_data['deadlines']
        
        # Добавляем новую запись
        deadlines.append(context.user_data['deadline_data'])
        
        # Сохраняем
        await user_storage.update_user_data(
            user_id,
            deadlines=deadlines
        )
        
        # Очищаем временные данные
        context.user_data.pop('deadline_data', None)
        
        await update.message.reply_text(
            "✅ Дедлайн успешно добавлен!",
            reply_markup=get_main_keyboard()
        )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введите целое число.",
            reply_markup=get_cancel_keyboard()
        )
        return ADD_DEADLINE_REMINDER

# ==================== ПОКАЗ РАСПИСАНИЯ ====================

async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ расписания пользователя"""
    user_id = update.effective_user.id
    user_data = await user_storage.get_user_data(user_id)
    schedule = user_data['schedule']
    
    if not schedule:
        await update.message.reply_text(
            "📭 Ваше расписание пусто.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Группируем по дням
    schedule_by_day = {day: [] for day in WEEKDAYS}
    for item in schedule:
        if isinstance(item, dict) and 'day' in item:
            day = item['day']
            if day in schedule_by_day:
                schedule_by_day[day].append(item)
    
    # Формируем сообщение
    message = "📅 **Ваше расписание:**\n\n"
    
    for day in WEEKDAYS:
        items = schedule_by_day[day]
        if items:
            # Сортируем по времени
            items.sort(key=lambda x: x.get('time', ''))
            
            message += f"**{day.capitalize()}:**\n"
            for i, item in enumerate(items, 1):
                message += f"{i}. {item.get('className', 'Без названия')}"
                if 'time' in item:
                    message += f" ({item['time']})"
                if 'professor' in item:
                    message += f" - {item['professor']}"
                message += "\n"
            message += "\n"
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )

# ==================== ПОКАЗ ДЕДЛАЙНОВ ====================

async def show_deadlines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ дедлайнов пользователя"""
    user_id = update.effective_user.id
    user_data = await user_storage.get_user_data(user_id)
    deadlines = user_data['deadlines']
    
    if not deadlines:
        await update.message.reply_text(
            "📭 У вас нет дедлайнов.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Фильтруем валидные дедлайны
    valid_deadlines = []
    for item in deadlines:
        if isinstance(item, dict) and 'datetime' in item:
            try:
                datetime.strptime(item['datetime'], "%Y-%m-%d %H:%M")
                valid_deadlines.append(item)
            except ValueError:
                continue
    
    if not valid_deadlines:
        await update.message.reply_text(
            "📭 У вас нет валидных дедлайнов.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Сортируем по дате
    valid_deadlines.sort(
        key=lambda x: datetime.strptime(x['datetime'], "%Y-%m-%d %H:%M")
    )
    
    # Формируем сообщение
    message = "📝 **Ваши дедлайны:**\n\n"
    
    for i, item in enumerate(valid_deadlines, 1):
        deadline_dt = datetime.strptime(item['datetime'], "%Y-%m-%d %H:%M")
        formatted_date = deadline_dt.strftime('%d.%m.%Y %H:%M')
        
        message += f"{i}. **{item.get('name', 'Без названия')}**\n"
        message += f"   📅 До: {formatted_date}\n"
        if item.get('description'):
            message += f"   📄 {item['description']}\n"
        message += f"   ⏰ Напоминание за {item.get('reminderBefore', 0)} мин.\n\n"
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )

# ==================== ОБЩИЕ ФУНКЦИИ ====================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена текущего действия"""
    # Очищаем временные данные
    context.user_data.pop('schedule_data', None)
    context.user_data.pop('deadline_data', None)
    
    await update.message.reply_text(
        "❌ Действие отменено.",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

async def handle_cancel_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия кнопки отмены"""
    # Проверяем, является ли сообщение кнопкой отмены
    if update.message.text == "❌ Отменить":
        return await cancel(update, context)
    
    # Если это не кнопка отмены, пропускаем
    return None

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок"""
    logger.error(f"🚨 Ошибка в обработчике: {context.error}")
    
    if update and update.effective_user:
        try:
            await update.message.reply_text(
                "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
                reply_markup=get_main_keyboard()
            )
        except:
            pass