import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Получаем токен
TOKEN = os.getenv('BOT_TOKEN')
print("=== НАЧАЛО РАБОТЫ ===")
print(f"Токен получен: {'ДА' if TOKEN else 'НЕТ'}")

if not TOKEN:
    print("❌ ОШИБКА: Токен не найден!")
    exit(1)

print("✅ Токен есть, создаю приложение...")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("✅ Кто-то написал /start!")
    await update.message.reply_text("🎉 Тестовый бот РАБОТАЕТ! Если видишь это - все ок!")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"✅ Получено сообщение: {update.message.text}")
    await update.message.reply_text(f"Вы сказали: {update.message.text}")

def main():
    print("🟡 Запускаю основную функцию...")
    
    try:
        application = Application.builder().token(TOKEN).build()
        print("✅ Приложение создано")
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
        print("✅ Обработчики добавлены")
        
        print("🚀 ЗАПУСКАЮ БОТА...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()