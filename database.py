"""
Асинхронный пул подключений к PostgreSQL
"""
import os
import asyncpg
import json
from typing import List, Dict, Any, Optional

class Database:
    """Класс для работы с базой данных через пул подключений"""
    
    _pool: Optional[asyncpg.Pool] = None
    
    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        """Получаем или создаем пул подключений"""
        if cls._pool is None or cls._pool._closed:
            database_url = os.environ.get('DATABASE_URL')
            if not database_url:
                raise ValueError("DATABASE_URL not set")
            
            # Парсим URL для Railway (может быть с postgresql:// или postgres://)
            if database_url.startswith('postgresql://'):
                database_url = database_url.replace('postgresql://', 'postgres://', 1)
            
            cls._pool = await asyncpg.create_pool(
                dsn=database_url,
                min_size=1,
                max_size=10,  # Ограничиваем подключения
                max_queries=50000,
                max_inactive_connection_lifetime=300,  # 5 минут
                command_timeout=60,  # 60 секунд на запрос
            )
        
        return cls._pool
    
    @classmethod
    async def close_pool(cls):
        """Закрываем пул подключений"""
        if cls._pool and not cls._pool._closed:
            await cls._pool.close()
            cls._pool = None
    
    @classmethod
    async def init_database(cls):
        """Инициализация таблиц"""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    schedule JSONB DEFAULT '[]',
                    deadlines JSONB DEFAULT '[]',
                    state JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_users_updated 
                ON users(updated_at DESC);
            ''')
    
    @classmethod
    async def create_user_if_not_exists(cls, user_id: int) -> bool:
        """Создает пользователя если не существует"""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                try:
                    await conn.execute('''
                        INSERT INTO users (user_id, schedule, deadlines, state)
                        VALUES ($1, '[]', '[]', '{}')
                        ON CONFLICT (user_id) DO NOTHING
                    ''', user_id)
                    return True
                except Exception:
                    return False
    
    @classmethod
    async def save_user_data(
        cls, 
        user_id: int, 
        schedule: List[Dict], 
        deadlines: List[Dict],
        state: Optional[Dict] = None
    ) -> bool:
        """Сохраняет все данные пользователя в транзакции"""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                try:
                    schedule_json = json.dumps(schedule, ensure_ascii=False)
                    deadlines_json = json.dumps(deadlines, ensure_ascii=False)
                    state_json = json.dumps(state or {}, ensure_ascii=False)
                    
                    await conn.execute('''
                        INSERT INTO users (user_id, schedule, deadlines, state, updated_at)
                        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
                        ON CONFLICT (user_id) DO UPDATE 
                        SET schedule = EXCLUDED.schedule,
                            deadlines = EXCLUDED.deadlines,
                            state = EXCLUDED.state,
                            updated_at = CURRENT_TIMESTAMP
                    ''', user_id, schedule_json, deadlines_json, state_json)
                    
                    return True
                except Exception as e:
                    print(f"❌ Ошибка сохранения данных: {e}")
                    return False
    
    @classmethod
    async def load_user_data(cls, user_id: int) -> Dict[str, Any]:
        """Загружает все данные пользователя"""
        await cls.create_user_if_not_exists(user_id)
        
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT schedule, deadlines, state 
                FROM users WHERE user_id = $1
            ''', user_id)
            
            if row:
                def parse_json(data):
                    if isinstance(data, str):
                        try:
                            return json.loads(data)
                        except:
                            return []
                    return data or []
                
                return {
                    'schedule': parse_json(row['schedule']),
                    'deadlines': parse_json(row['deadlines']),
                    'state': parse_json(row['state'])
                }
            
            return {'schedule': [], 'deadlines': [], 'state': {}}
    
    @classmethod
    async def update_user_state(cls, user_id: int, state: Dict) -> bool:
        """Обновляет только состояние пользователя"""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                try:
                    state_json = json.dumps(state, ensure_ascii=False)
                    await conn.execute('''
                        UPDATE users 
                        SET state = $2, updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = $1
                    ''', user_id, state_json)
                    return True
                except Exception:
                    return False
    
    @classmethod
    async def get_user_state(cls, user_id: int) -> Dict:
        """Получает состояние пользователя"""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT state FROM users WHERE user_id = $1
            ''', user_id)
            
            if row and row['state']:
                if isinstance(row['state'], str):
                    try:
                        return json.loads(row['state'])
                    except:
                        return {}
                return row['state']
            
            return {}