from flask import Flask, request
import os
import asyncio

# Создаем application напрямую вместо импорта
from telegram.ext import Application

app = Flask(__name__)

# Создаем application глобально
TOKEN = os.environ.get('BOT_TOKEN', '8240746309:AAEqhznhHLgSd2K0QMpmdBQHMHIyJNdrYG8')
application = Application.builder().token(TOKEN).build()

# Импортируем и регистрируем обработчики из TypeKeeper
import TypeKeeper
TypeKeeper.register_handlers(application)

@app.route('/')
def index():
    return "Bot is running!"

@app.route('/webhook/' + TOKEN, methods=['POST'])
def webhook():
    """Endpoint для получения обновлений от Telegram"""
    update = request.get_json()
    asyncio.create_task(process_update(update))
    return 'ok'

async def process_update(update_dict):
    """Асинхронная обработка обновления"""
    from telegram import Update
    update = Update.de_json(update_dict, application.bot)
    await application.process_update(update)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))