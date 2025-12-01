"""
Промежуточное ПО для обработки запросов
"""
import logging
import time
from typing import Callable, Dict, Any
from telegram import Update
from telegram.ext import ContextTypes
from storage import user_storage

logger = logging.getLogger(__name__)

class UserLockMiddleware:
    """Middleware для блокировки запросов одного пользователя"""
    
    def __init__(self):
        self.user_locks = {}
    
    async def __call__(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE,
        next_handler: Callable
    ):
        user_id = update.effective_user.id
        
        # Блокируем по пользователю
        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()
        
        async with self.user_locks[user_id]:
            # Логируем начало обработки
            start_time = time.time()
            logger.info(f"🚀 Начало обработки для user {user_id}")
            
            try:
                # Вызываем следующий обработчик
                result = await next_handler(update, context)
                return result
            finally:
                # Логируем конец обработки
                elapsed = time.time() - start_time
                logger.info(f"✅ Обработка завершена для user {user_id} за {elapsed:.2f} сек")

class StateManagementMiddleware:
    """Middleware для управления состоянием пользователя"""
    
    async def __call__(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE,
        next_handler: Callable
    ):
        user_id = update.effective_user.id
        
        # Загружаем состояние пользователя в context
        user_data = await user_storage.get_user_data(user_id)
        
        # Сохраняем в context для совместимости со старым кодом
        context.user_data = {
            'schedule': user_data['schedule'],
            'deadlines': user_data['deadlines'],
            'state': user_data['state']
        }
        
        try:
            # Вызываем обработчик
            result = await next_handler(update, context)
            
            # Автоматически сохраняем состояние после обработки
            await user_storage.update_user_data(
                user_id,
                schedule=context.user_data.get('schedule'),
                deadlines=context.user_data.get('deadlines'),
                state=context.user_data.get('state', {})
            )
            
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка в обработчике для user {user_id}: {e}")
            raise

# Инициализация middleware
user_lock_middleware = UserLockMiddleware()
state_middleware = StateManagementMiddleware()

async def apply_middlewares(update: Update, context: ContextTypes.DEFAULT_TYPE, handler: Callable):
    """Применяет все middleware к обработчику"""
    # Порядок важен!
    async def with_state(update, context):
        async def with_lock(update, context):
            return await handler(update, context)
        return await user_lock_middleware(update, context, with_lock)
    
    return await state_middleware(update, context, with_state)