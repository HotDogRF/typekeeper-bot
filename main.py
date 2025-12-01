"""Главный файл бота - точка входа"""
import os
import logging
import asyncio
from datetime import datetime

import aiohttp
from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

from database import Database
from storage import user_storage
from keyboards import get_main_keyboard

# Импортируем состояния и обработчики из handlers
from handlers import (
    start, help_command, reset_command, cancel, error_handler,
    show_schedule, show_deadlines,
    start_add_schedule, add_schedule_day_callback, add_schedule_time,
    add_schedule_class, add_schedule_professor, add_schedule_reminder,
    start_add_deadline, add_deadline_name, add_deadline_date,
    add_deadline_description, add_deadline_reminder,
    ADD_SCHEDULE_DAY, ADD_SCHEDULE_TIME, ADD_SCHEDULE_CLASS,
    ADD_SCHEDULE_PROFESSOR, ADD_SCHEDULE_REMINDER,
    ADD_DEADLINE_NAME, ADD_DEADLINE_DATE, ADD_DEADLINE_DESC,
    ADD_DEADLINE_REMINDER
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен")

PORT = int(os.environ.get('PORT', 8080))
WEBHOOK_URL = os.environ.get('RAILWAY_STATIC_URL', '')

if WEBHOOK_URL and not WEBHOOK_URL.startswith('https://'):
    WEBHOOK_URL = f"https://{WEBHOOK_URL}"

# Создаем application
application = Application.builder().token(TOKEN).build()

def setup_handlers():
    """Настройка всех обработчиков"""
    
    # Основные команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("reset", reset_command))
    
    # Обработчик кнопки отмены
    application.add_handler(MessageHandler(
        filters.Regex("^❌ Отменить$"),
        cancel
    ))
    
    # Добавление расписания
    conv_handler_schedule = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^📅 Добавить расписание$"),
                start_add_schedule
            )
        ],
        states={
            ADD_SCHEDULE_DAY: [
                CallbackQueryHandler(
                    add_schedule_day_callback,
                    pattern="^day_"
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    cancel  # Если ввели текст вместо кнопки
                )
            ],
            ADD_SCHEDULE_TIME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_schedule_time
                )
            ],
            ADD_SCHEDULE_CLASS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_schedule_class
                )
            ],
            ADD_SCHEDULE_PROFESSOR: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_schedule_professor
                )
            ],
            ADD_SCHEDULE_REMINDER: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_schedule_reminder
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^❌ Отменить$"), cancel)
        ],
    )
    
    # Добавление дедлайна
    conv_handler_deadline = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^⏰ Добавить дедлайн$"),
                start_add_deadline
            )
        ],
        states={
            ADD_DEADLINE_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_deadline_name
                )
            ],
            ADD_DEADLINE_DATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_deadline_date
                )
            ],
            ADD_DEADLINE_DESC: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_deadline_description
                )
            ],
            ADD_DEADLINE_REMINDER: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_deadline_reminder
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^❌ Отменить$"), cancel)
        ],
    )
    
    # Показ расписания и дедлайнов
    application.add_handler(MessageHandler(
        filters.Regex("^📋 Мое расписание$"),
        show_schedule
    ))
    
    application.add_handler(MessageHandler(
        filters.Regex("^📝 Мои дедлайны$"),
        show_deadlines
    ))
    
    # Команды помощи и сброса
    application.add_handler(MessageHandler(
        filters.Regex("^🔄 Сбросить состояние$"),
        reset_command
    ))
    
    application.add_handler(MessageHandler(
        filters.Regex("^ℹ️ Помощь$"),
        help_command
    ))
    
    # Регистрируем ConversationHandler
    application.add_handler(conv_handler_schedule)
    application.add_handler(conv_handler_deadline)
    
    # Глобальный обработчик ошибок
    application.add_error_handler(error_handler)

async def set_webhook():
    """Установка вебхука"""
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await application.bot.delete_webhook()
        await application.bot.set_webhook(webhook_url)
        logger.info(f"🌐 Вебхук установлен: {webhook_url}")
    else:
        logger.warning("⚠️ WEBHOOK_URL не установлен, бот будет работать в polling режиме")

async def health_check(request):
    """Проверка здоровья сервера"""
    return web.Response(text="✅ Бот работает")

async def handle_webhook(request):
    """Обработка входящих вебхуков"""
    try:
        # Парсим обновление
        data = await request.json()
        update = Update.de_json(data, application.bot)
        
        # Логируем входящий запрос
        if update.message:
            logger.info(f"📨 Сообщение от {update.effective_user.id}: {update.message.text}")
        elif update.callback_query:
            logger.info(f"📨 Callback от {update.effective_user.id}: {update.callback_query.data}")
        
        # Обрабатываем обновление
        await application.process_update(update)
        
        return web.Response(text="OK")
        
    except Exception as e:
        logger.error(f"🚨 Ошибка в обработке вебхука: {e}")
        return web.Response(text="ERROR", status=500)

async def startup(app):
    """Запуск приложения"""
    logger.info("🚀 Запуск бота...")
    
    # Инициализация БД
    try:
        await Database.init_database()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
    
    # Настройка обработчиков
    setup_handlers()
    
    # Запуск бота
    await application.initialize()
    
    # Установка вебхука
    await set_webhook()
    
    logger.info(f"✅ Бот запущен на порту {PORT}")

async def shutdown(app):
    """Завершение работы"""
    logger.info("🛑 Остановка бота...")
    
    # Останавливаем бота
    await application.stop()
    await application.shutdown()
    
    # Закрываем пул БД
    await Database.close_pool()
    
    logger.info("✅ Бот остановлен")

async def polling_mode():
    """Режим polling для разработки"""
    logger.info("🔄 Запуск в режиме polling...")
    
    # Инициализация БД
    try:
        await Database.init_database()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return
    
    # Настройка обработчиков
    setup_handlers()
    
    # Запуск бота
    await application.initialize()
    await application.start()
    
    # Начинаем polling
    try:
        await application.updater.start_polling()
        logger.info("✅ Бот запущен в режиме polling")
        
        # Бесконечное ожидание
        await asyncio.Event().wait()
        
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Получен сигнал остановки")
    finally:
        await application.stop()
        await application.shutdown()
        await Database.close_pool()

def create_app():
    """Создание aiohttp приложения"""
    app = web.Application()
    
    # Регистрация маршрутов
    app.router.add_get('/', health_check)
    app.router.add_post('/webhook', handle_webhook)
    app.router.add_get('/health', health_check)
    
    # Регистрация событий жизненного цикла
    app.on_startup.append(startup)
    app.on_shutdown.append(shutdown)
    
    return app

def main():
    """Главная функция"""
    # Проверяем, нужен ли вебхук
    if WEBHOOK_URL:
        # Режим с вебхуком (продакшн)
        app = create_app()
        web.run_app(app, host='0.0.0.0', port=PORT)
    else:
        # Режим polling (разработка)
        asyncio.run(polling_mode())

if __name__ == '__main__':
    main()