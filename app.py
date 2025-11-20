from flask import Flask, request
import os
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler, ContextTypes

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

TOKEN = os.environ.get('BOT_TOKEN', '8240746309:AAEqhznhHLgSd2K0QMpmdBQHMHIyJNdrYG8')

# Создаем application
application = Application.builder().token(TOKEN).build()

# Простой обработчик для теста
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение"""
    await update.message.reply_text("Привет! Бот работает через webhooks! 🚀")

# Регистрируем обработчики
application.add_handler(CommandHandler("start", start))

@app.route('/')
def index():
    return "Bot is running with webhooks!"

@app.route('/webhook/' + TOKEN, methods=['POST'])
def webhook():
    """Endpoint для получения обновлений от Telegram"""
    try:
        update = Update.de_json(request.get_json(), application.bot)
        asyncio.create_task(application.process_update(update))
        return 'ok'
    except Exception as e:
        logging.error(f"Error processing update: {e}")
        return 'error', 500

if __name__ == '__main__':
    # Запускаем webhook
    port = int(os.environ.get('PORT', 8080))
    railway_url = os.environ.get('RAILWAY_STATIC_URL')
    
    if railway_url:
        # Устанавливаем webhook
        async def set_webhook():
            await application.bot.set_webhook(f"{railway_url}/webhook/{TOKEN}")
        
        # Запускаем в event loop
        loop = asyncio.get_event_loop()
        loop.run_until_complete(set_webhook())
        logging.info(f"Webhook set to: {railway_url}/webhook/{TOKEN}")
    
    app.run(host='0.0.0.0', port=port)