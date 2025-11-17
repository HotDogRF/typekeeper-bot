import os
import sys

print("=== DEBUG: Проверка окружения ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Files in directory: {os.listdir('.')}")

print("\n=== ВСЕ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===")
for key, value in sorted(os.environ.items()):
    print(f"{key}: {value}")

print(f"\n=== ПРОВЕРКА BOT_TOKEN ===")
token = os.getenv('BOT_TOKEN')
print(f"BOT_TOKEN exists: {bool(token)}")
print(f"BOT_TOKEN length: {len(token) if token else 0}")
print(f"BOT_TOKEN value: {token}")

if not token:
    print("❌ BOT_TOKEN НЕ НАЙДЕН!")
    sys.exit(1)
else:
    print("✅ BOT_TOKEN НАЙДЕН!")