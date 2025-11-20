import os
import psycopg2
import json
from urllib.parse import urlparse

def get_db_connection():
    """Подключается к PostgreSQL через DATABASE_URL"""
    try:
        # Для Railway
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            # Парсим URL для Railway
            result = urlparse(database_url)
            conn = psycopg2.connect(
                host=result.hostname,
                database=result.path[1:],
                user=result.username,
                password=result.password,
                port=result.port,
                sslmode='require'
            )
            print("✅ Успешно подключились к PostgreSQL на Railway")
            return conn
        else:
            # Если нет DATABASE_URL, возвращаем None
            print("❌ DATABASE_URL не установлена")
            return None
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return None

# ... остальные функции (init_database, save_user_data, load_user_data) остаются как были ...
def init_database():
    """Создает таблицу если её нет"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                schedule JSONB,
                deadlines JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        print("✅ Таблица users создана или уже существует")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания таблицы: {e}")
        return False
    finally:
        conn.close()

def save_user_data(user_id, schedule, deadlines):
    """Сохраняет данные пользователя в базу данных"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO users (user_id, schedule, deadlines)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                schedule = EXCLUDED.schedule,
                deadlines = EXCLUDED.deadlines
        ''', (user_id, json.dumps(schedule), json.dumps(deadlines)))
        
        conn.commit()
        print(f"✅ Данные пользователя {user_id} сохранены в БД")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False
    finally:
        conn.close()

async def load_user_data(user_id):
    """Загружает данные пользователя из базы данных"""
    conn = get_db_connection()
    if not conn:
        return {'schedule': [], 'deadlines': []}
        
    try:
        cur = conn.cursor()
        cur.execute('SELECT schedule, deadlines FROM users WHERE user_id = %s', (user_id,))
        result = cur.fetchone()
        
        if result:
            schedule = result[0] if result[0] else []
            deadlines = result[1] if result[1] else []
            print(f"✅ Данные пользователя {user_id} загружены из БД")
            return {'schedule': schedule, 'deadlines': deadlines}
        else:
            print(f"✅ Пользователь {user_id} не найден, возвращаем пустые данные")
            return {'schedule': [], 'deadlines': []}
            
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return {'schedule': [], 'deadlines': []}
    finally:
        conn.close()