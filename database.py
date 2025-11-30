import os
import asyncpg
import json
from typing import Dict, List, Any

async def get_db_connection():
    """Асинхронное подключение к PostgreSQL"""
    try:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL не установлена")
            return None
            
        conn = await asyncpg.connect(database_url)
        print("✅ Успешно подключились к PostgreSQL")
        return conn
        
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return None

async def init_database():
    """Создает таблицу если её нет"""
    conn = None
    try:
        conn = await get_db_connection()
        if not conn:
            print("❌ Не удалось подключиться к БД для инициализации")
            return False
            
        # Создаем таблицу если не существует
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                schedule JSONB DEFAULT '[]',
                deadlines JSONB DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Таблица users создана/проверена")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return False
        
    finally:
        if conn:
            await conn.close()

async def create_user_if_not_exists(user_id: int) -> bool:
    """Создает пользователя если не существует"""
    conn = None
    try:
        conn = await get_db_connection()
        if not conn:
            return False
            
        # Пробуем вставить пользователя, игнорируем если уже существует
        await conn.execute('''
            INSERT INTO users (user_id, schedule, deadlines)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO NOTHING
        ''', user_id, [], [])
        
        print(f"✅ Пользователь {user_id} гарантированно существует в БД")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания пользователя {user_id}: {e}")
        return False
        
    finally:
        if conn:
            await conn.close()

async def save_user_data(user_id: str, schedule: List[Dict], deadlines: List[Dict]) -> bool:
    """Сохраняет данные пользователя в базу данных"""
    conn = None
    try:
        # Сначала гарантируем, что пользователь существует
        await create_user_if_not_exists(user_id)
        
        conn = await get_db_connection()
        if not conn:
            return False
        
        print(f"🔍 DEBUG save_user_data:")
        print(f"   user_id: {user_id}")
        print(f"   schedule: {schedule}")
        print(f"   deadlines: {deadlines}")
        
        # Обновляем данные пользователя
        await conn.execute('''
            UPDATE users 
            SET schedule = $2, deadlines = $3
            WHERE user_id = $1
        ''', int(user_id), schedule, deadlines)
        
        print(f"✅ Данные пользователя {user_id} сохранены в БД")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка сохранения данных пользователя {user_id}: {e}")
        import traceback
        print(f"📋 Детали ошибки: {traceback.format_exc()}")
        return False
        
    finally:
        if conn:
            await conn.close()

async def load_user_data(user_id: int) -> Dict[str, List]:
    """Загружает данные пользователя из базы данных"""
    conn = None
    try:
        # Гарантируем, что пользователь существует
        await create_user_if_not_exists(user_id)
        
        conn = await get_db_connection()
        if not conn:
            return {'schedule': [], 'deadlines': []}
        
        result = await conn.fetchrow(
            'SELECT schedule, deadlines FROM users WHERE user_id = $1', 
            user_id
        )
        
        if result:
            schedule = result['schedule'] if result['schedule'] else []
            deadlines = result['deadlines'] if result['deadlines'] else []
            
            print(f"✅ Данные пользователя {user_id} загружены из БД")
            return {
                'schedule': schedule,
                'deadlines': deadlines
            }
        else:
            # Это не должно происходить, так как мы создали пользователя выше
            print(f"⚠️ Неожиданно: пользователь {user_id} не найден после create_user_if_not_exists")
            return {'schedule': [], 'deadlines': []}
            
    except Exception as e:
        print(f"❌ Ошибка загрузки данных пользователя {user_id}: {e}")
        return {'schedule': [], 'deadlines': []}
        
    finally:
        if conn:
            await conn.close()