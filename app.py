from flask import Flask, request
from TypeKeeper import application
import os

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

@app.route('/webhook/' + os.environ.get('BOT_TOKEN'), methods=['POST'])
def webhook():
    """Endpoint для получения обновлений от Telegram"""
    update = Update.de_json(request.get_json(), application.bot)
    application.process_update(update)
    return 'ok'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))