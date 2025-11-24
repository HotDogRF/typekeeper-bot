import os
import asyncpg

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
    conn = await get_db_connection()
    if not conn:
        return False
        
    try:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                schedule JSONB DEFAULT '[]',
                deadlines JSONB DEFAULT '[]',
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
        user_id_int = int(user_id)
        
        # 🔥 ИСПРАВЛЕНИЕ: убираем json.dumps - asyncpg автоматически конвертирует Python объекты в JSONB
        await conn.execute('''
            INSERT INTO users (user_id, schedule, deadlines)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                schedule = EXCLUDED.schedule,
                deadlines = EXCLUDED.deadlines
        ''', user_id_int, schedule, deadlines)
        
        print(f"✅ Данные пользователя {user_id} сохранены в БД")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка сохранения данных пользователя {user_id}: {e}")
        return False
        
    finally:
        await conn.close()

async def load_user_data(user_id):
    """Загружает данные пользователя из базы данных"""
    conn = await get_db_connection()
    if not conn:
        return {'schedule': [], 'deadlines': []}
        
    try:
        user_id_int = int(user_id)
        
        result = await conn.fetchrow(
            'SELECT schedule, deadlines FROM users WHERE user_id = $1', 
            user_id_int
        )
        
        if result:
            # asyncpg автоматически конвертирует JSONB в Python объекты
            schedule = result['schedule'] or []
            deadlines = result['deadlines'] or []
            
            print(f"✅ Данные пользователя {user_id} загружены из БД")
            return {
                'schedule': schedule,
                'deadlines': deadlines
            }
        else:
            print(f"✅ Пользователь {user_id} не найден, возвращаем пустые данные")
            return {'schedule': [], 'deadlines': []}
            
    except Exception as e:
        print(f"❌ Ошибка загрузки данных пользователя {user_id}: {e}")
        return {'schedule': [], 'deadlines': []}
        
    finally:
        await conn.close()

async def clear_user_data(user_id):
    """Очищает данные пользователя (для отладки)"""
    conn = await get_db_connection()
    if not conn:
        return False
        
    try:
        user_id_int = int(user_id)
        
        await conn.execute(
            'UPDATE users SET schedule = $1, deadlines = $2 WHERE user_id = $3',
            [], [], user_id_int
        )
        
        print(f"✅ Данные пользователя {user_id} очищены")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка очистки данных пользователя {user_id}: {e}")
        return False
        
    finally:
        await conn.close()

async def get_all_users():
    """Получает список всех пользователей (для администрирования)"""
    conn = await get_db_connection()
    if not conn:
        return []
        
    try:
        rows = await conn.fetch('SELECT user_id FROM users')
        user_ids = [row['user_id'] for row in rows]
        
        print(f"✅ Получен список пользователей: {len(user_ids)} пользователей")
        return user_ids
        
    except Exception as e:
        print(f"❌ Ошибка получения списка пользователей: {e}")
        return []
        
    finally:
        await conn.close()