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
        await conn.execute('''DROP TABLE IF EXISTS users''')
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
            
        # 🔥 ПРЕОБРАЗУЕМ В JSON СТРОКИ
        empty_schedule_json = json.dumps([])
        empty_deadlines_json = json.dumps([])
            
        await conn.execute('''
            INSERT INTO users (user_id, schedule, deadlines)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO NOTHING
        ''', user_id, empty_schedule_json, empty_deadlines_json)
        
        print(f"✅ Пользователь {user_id} гарантированно существует в БД")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания пользователя {user_id}: {e}")
        return False
        
    finally:
        if conn:
            await conn.close()

async def save_user_data(user_id: int, schedule: List[Dict], deadlines: List[Dict]) -> bool:
    """Сохраняет данные пользователя в базу данных"""
    conn = None
    try:
        await create_user_if_not_exists(user_id)
        conn = await get_db_connection()
        if not conn:
            return False
        
        print(f"🔍 DEBUG save_user_data:")
        print(f"   user_id: {user_id}")
        print(f"   schedule type: {type(schedule)}")
        print(f"   schedule: {schedule}")
        print(f"   deadlines type: {type(deadlines)}")
        print(f"   deadlines: {deadlines}")
        
        # 🔥 ПРЕОБРАЗУЕМ В JSON СТРОКИ
        schedule_json = json.dumps(schedule, ensure_ascii=False)
        deadlines_json = json.dumps(deadlines, ensure_ascii=False)
        
        await conn.execute('''
            UPDATE users 
            SET schedule = $2, deadlines = $3
            WHERE user_id = $1
        ''', user_id, schedule_json, deadlines_json)
        
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
        await create_user_if_not_exists(user_id)
        conn = await get_db_connection()
        if not conn:
            return {'schedule': [], 'deadlines': []}
        
        result = await conn.fetchrow(
            'SELECT schedule, deadlines FROM users WHERE user_id = $1', 
            user_id
        )
        
        if result:
            schedule_data = result['schedule']
            deadlines_data = result['deadlines']
            
            # 🔥 ПРЕОБРАЗУЕМ JSON СТРОКИ ОБРАТНО В СПИСКИ
            def parse_json_field(data):
                if data is None:
                    return []
                elif isinstance(data, str):
                    try:
                        return json.loads(data)
                    except json.JSONDecodeError:
                        print(f"⚠️ Ошибка парсинга JSON: {data}")
                        return []
                elif isinstance(data, list):
                    return data
                else:
                    print(f"⚠️ Неизвестный тип данных: {type(data)}")
                    return []
            
            schedule = parse_json_field(schedule_data)
            deadlines = parse_json_field(deadlines_data)
            
            print(f"✅ Данные пользователя {user_id} загружены:")
            print(f"   schedule: {len(schedule)} элементов")
            print(f"   deadlines: {len(deadlines)} элементов")
            
            return {
                'schedule': schedule,
                'deadlines': deadlines
            }
        else:
            print(f"⚠️ Пользователь {user_id} не найден")
            return {'schedule': [], 'deadlines': []}
            
    except Exception as e:
        print(f"❌ Ошибка загрузки данных пользователя {user_id}: {e}")
        return {'schedule': [], 'deadlines': []}
        
    finally:
        if conn:
            await conn.close()