"""
Все клавиатуры бота
"""
from telegram import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# Упорядоченные дни недели
WEEKDAYS = [
    "понедельник", "вторник", "среда", 
    "четверг", "пятница", "суббота", "воскресенье"
]

def get_main_keyboard():
    """Основная клавиатура"""
    keyboard = [
        [
            KeyboardButton("📅 Добавить расписание"),
            KeyboardButton("⏰ Добавить дедлайн"),
        ],
        [
            KeyboardButton("📋 Мое расписание"),
            KeyboardButton("📝 Мои дедлайны"),
        ],
        [
            KeyboardButton("🔄 Сбросить состояние"),
            KeyboardButton("ℹ️ Помощь"),
        ]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_weekday_keyboard(prefix="day_"):
    """Инлайн-клавиатура для выбора дня недели"""
    keyboard = []
    for day in WEEKDAYS:
        keyboard.append([
            InlineKeyboardButton(
                day.capitalize(),
                callback_data=f"{prefix}{day}"
            )
        ])
    return InlineKeyboardMarkup(keyboard)

def get_edit_schedule_keyboard(day: str, items_count: int):
    """Клавиатура для редактирования расписания на день"""
    keyboard = []
    for i in range(items_count):
        keyboard.append([
            InlineKeyboardButton(
                f"✏️ Пара {i+1}",
                callback_data=f"edit_schedule_{day}_{i}"
            ),
            InlineKeyboardButton(
                f"🗑️ Пара {i+1}",
                callback_data=f"delete_schedule_{day}_{i}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_schedule")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_edit_deadline_keyboard(deadline_index: int):
    """Клавиатура для редактирования дедлайна"""
    keyboard = [
        [
            InlineKeyboardButton("📝 Название", callback_data=f"edit_deadline_name_{deadline_index}"),
            InlineKeyboardButton("📅 Дата", callback_data=f"edit_deadline_date_{deadline_index}")
        ],
        [
            InlineKeyboardButton("📄 Описание", callback_data=f"edit_deadline_desc_{deadline_index}"),
            InlineKeyboardButton("⏰ Напоминание", callback_data=f"edit_deadline_reminder_{deadline_index}")
        ],
        [
            InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_deadline_{deadline_index}"),
            InlineKeyboardButton("🔙 Назад", callback_data="back_to_deadlines")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard():
    """Клавиатура для отмены действия"""
    keyboard = [[KeyboardButton("❌ Отменить")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)