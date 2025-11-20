import os
import asyncpg
import json

async def get_db_connection():
    """Асинхронное подключение к PostgreSQL"""
    try:
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            conn = await asyncpg.connect(database_url)
            print("✅ Успешно подключились к PostgreSQL асинхронно")
            return conn
        else:
            print("❌ DATABASE_URL не установлена")
            return None
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return None

async def init_database():
    """Создает таблицу если её нет"""
    conn = await get_db_connection()
    if not conn:
        return False
        
    try:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                schedule JSONB,
                deadlines JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Таблица users создана или уже существует")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания таблицы: {e}")
        return False
    finally:
        await conn.close()

async def save_user_data(user_id, schedule, deadlines):
    """Сохраняет данные пользователя в базу данных"""
    conn = await get_db_connection()
    if not conn:
        return False
        
    try:
        await conn.execute('''
            INSERT INTO users (user_id, schedule, deadlines)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                schedule = EXCLUDED.schedule,
                deadlines = EXCLUDED.deadlines
        ''', user_id, json.dumps(schedule), json.dumps(deadlines))
        
        print(f"✅ Данные пользователя {user_id} сохранены в БД")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False
    finally:
        await conn.close()

async def load_user_data(user_id):
    """Загружает данные пользователя из базы данных"""
    conn = await get_db_connection()
    if not conn:
        return {'schedule': [], 'deadlines': []}
        
    try:
        result = await conn.fetchrow(
            'SELECT schedule, deadlines FROM users WHERE user_id = $1', 
            user_id
        )
        
        if result:
            schedule = result['schedule'] if result['schedule'] else []
            deadlines = result['deadlines'] if result['deadlines'] else []
            print(f"✅ Данные пользователя {user_id} загружены из БД")
            return {'schedule': schedule, 'deadlines': deadlines}
        else:
            print(f"✅ Пользователь {user_id} не найден, возвращаем пустые данные")
            return {'schedule': [], 'deadlines': []}
            
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return {'schedule': [], 'deadlines': []}
    finally:
        await conn.close()