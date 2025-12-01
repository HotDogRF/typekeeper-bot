"""
Хранилище состояний пользователей с блокировками
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from database import Database

class UserStateStorage:
    """Потокобезопасное хранилище состояний пользователей"""
    
    def __init__(self):
        self._user_locks: Dict[int, asyncio.Lock] = {}
        self._lock = asyncio.Lock()
        self._cache: Dict[int, Dict[str, Any]] = {}
        self._cache_ttl = timedelta(minutes=5)
        self._cache_timestamps: Dict[int, datetime] = {}
    
    async def _get_user_lock(self, user_id: int) -> asyncio.Lock:
        """Получаем блокировку для конкретного пользователя"""
        async with self._lock:
            if user_id not in self._user_locks:
                self._user_locks[user_id] = asyncio.Lock()
            return self._user_locks[user_id]
    
    async def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """Получаем данные пользователя с блокировкой"""
        # Проверяем кэш
        if user_id in self._cache:
            if datetime.now() - self._cache_timestamps[user_id] < self._cache_ttl:
                return self._cache[user_id].copy()
        
        # Блокируем по пользователю
        user_lock = await self._get_user_lock(user_id)
        async with user_lock:
            data = await Database.load_user_data(user_id)
            # Кэшируем
            self._cache[user_id] = data.copy()
            self._cache_timestamps[user_id] = datetime.now()
            return data
    
    async def update_user_data(
        self, 
        user_id: int, 
        schedule: Optional[List[Dict]] = None,
        deadlines: Optional[List[Dict]] = None,
        state: Optional[Dict] = None
    ) -> bool:
        """Обновляем данные пользователя с блокировкой"""
        user_lock = await self._get_user_lock(user_id)
        async with user_lock:
            # Загружаем текущие данные
            current_data = await Database.load_user_data(user_id)
            
            # Обновляем только указанные поля
            new_schedule = schedule if schedule is not None else current_data['schedule']
            new_deadlines = deadlines if deadlines is not None else current_data['deadlines']
            new_state = state if state is not None else current_data['state']
            
            # Сохраняем
            success = await Database.save_user_data(
                user_id, 
                new_schedule, 
                new_deadlines, 
                new_state
            )
            
            if success:
                # Обновляем кэш
                self._cache[user_id] = {
                    'schedule': new_schedule,
                    'deadlines': new_deadlines,
                    'state': new_state
                }
                self._cache_timestamps[user_id] = datetime.now()
            
            return success
    
    async def update_user_state(self, user_id: int, **kwargs) -> bool:
        """Обновляет только состояние пользователя"""
        user_lock = await self._get_user_lock(user_id)
        async with user_lock:
            # Получаем текущее состояние
            current_state = await Database.get_user_state(user_id)
            
            # Обновляем поля
            current_state.update(kwargs)
            
            # Сохраняем
            success = await Database.update_user_state(user_id, current_state)
            
            if success and user_id in self._cache:
                self._cache[user_id]['state'] = current_state.copy()
                self._cache_timestamps[user_id] = datetime.now()
            
            return success
    
    async def get_user_state_value(self, user_id: int, key: str, default=None):
        """Получает конкретное значение из состояния"""
        data = await self.get_user_data(user_id)
        return data['state'].get(key, default)
    
    async def clear_user_state(self, user_id: int) -> bool:
        """Очищает состояние пользователя"""
        return await self.update_user_state(user_id, **{})

# Глобальный экземпляр хранилища
user_storage = UserStateStorage()