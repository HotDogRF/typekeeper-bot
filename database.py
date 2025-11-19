import psycopg2
import os
import json
import logging

def get_db_connection():
    """Подключается к базе данных"""
    try:
        return psycopg2.connect(os.getenv('DATABASE_URL'))
    except Exception as e:
        logging.error(f"Ошибка подключения к БД: {e}")
        return None

def init_database():
    """Создает таблицы если их нет"""
    conn = get_db_connection()
    if not conn:
        return
        
    try:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                schedule JSONB DEFAULT '[]',
                deadlines JSONB DEFAULT '[]'
            )
        ''')
        conn.commit()
        print("✅ База данных готова")
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")
    finally:
        conn.close()

def save_user_data(user_id, schedule, deadlines):
    """Сохраняет данные пользователя"""
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
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False
    finally:
        conn.close()

def load_user_data(user_id):
    """Загружает данные пользователя"""
    conn = get_db_connection()
    if not conn:
        return {'schedule': [], 'deadlines': []}
        
    try:
        cur = conn.cursor()
        cur.execute('SELECT schedule, deadlines FROM users WHERE user_id = %s', (user_id,))
        result = cur.fetchone()
        
        if result:
            return {'schedule': result[0] or [], 'deadlines': result[1] or []}
        else:
            return {'schedule': [], 'deadlines': []}
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return {'schedule': [], 'deadlines': []}
    finally:
        conn.close()