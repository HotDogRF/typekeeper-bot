import os
import sys

print("=== DEBUG: Проверка ВСЕХ возможных переменных ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

print("\n=== ПРОВЕРКА ВСЕХ ВАРИАНТОВ ТОКЕНОВ ===")
token_variants = [
    'BOT_TOKEN',
    'TELEGRAM_BOT_TOKEN', 
    'TG_BOT_TOKEN',
    'BOT_API_TOKEN',
    'TELEGRAM_TOKEN',
    'TG_TOKEN'
]

found_tokens = []

for var_name in token_variants:
    token = os.getenv(var_name)
    if token:
        print(f"✅ {var_name}: НАЙДЕН (длина: {len(token)})")
        found_tokens.append((var_name, token))
    else:
        print(f"❌ {var_name}: не найден")

print(f"\n=== РЕЗУЛЬТАТ ===")
if found_tokens:
    print(f"🎉 Найдено переменных: {len(found_tokens)}")
    for name, token in found_tokens:
        print(f"   {name}: {token[:10]}...")
else:
    print("😞 Ни одна переменная не найдена")
    print("\n=== ВСЕ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===")
    for key, value in sorted(os.environ.items()):
        if any(word in key.upper() for word in ['BOT', 'TOKEN', 'TELEGRAM', 'TG']):
            print(f"   {key}: {value}")

print(f"\n=== РЕКОМЕНДАЦИЯ ===")
if found_tokens:
    print(f"Используйте переменную: {found_tokens[0][0]}")
else:
    print("1. Создайте переменную в Railway с одним из имен выше")
    print("2. Убедитесь что она привязана к сервису")
    print("3. Перезапустите сервис")