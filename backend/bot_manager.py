#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ZAZA Bot Manager - Менеджер запуска ботов
Автоматически запускает всех активных ботов из базы данных
"""

import asyncio
import logging
import signal
import sys
from typing import Dict, List
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker

from database import TelegramBot
from bot import ZAZABot

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_manager.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BotManager:
    """Менеджер для управления несколькими ботами"""
    
    def __init__(self):
        self.running_bots: Dict[int, ZAZABot] = {}
        self.tasks: Dict[int, asyncio.Task] = {}
        self.engine = None
        self.async_session = None
        self.setup_database()
        
    def setup_database(self):
        """Настройка подключения к БД"""
        # Используем ту же настройку, что и админка
        from database import engine
        self.engine = engine
        self.session_maker = sessionmaker(
            bind=self.engine, expire_on_commit=False
        )
    
    def load_active_bots(self) -> List[TelegramBot]:
        """Загружает список активных ботов из БД"""
        try:
            with self.session_maker() as session:
                # Сначала проверим всех ботов
                all_query = select(TelegramBot)
                all_result = session.execute(all_query)
                all_bots = all_result.scalars().all()
                logger.info(f"Всего ботов в БД: {len(all_bots)}")
                
                for bot in all_bots:
                    try:
                        bot_name = bot.name.encode('utf-8', errors='replace').decode('utf-8') if bot.name else "Unknown"
                        logger.info(f"Бот: {bot_name}, Активен: {bot.is_active}, ID: {bot.id}")
                    except Exception as e:
                        logger.warning(f"Ошибка отображения имени бота ID {bot.id}: {e}")
                
                # Теперь получим только активных
                query = select(TelegramBot).where(TelegramBot.is_active == True)
                result = session.execute(query)
                bots = result.scalars().all()
                
                logger.info(f"Найдено {len(bots)} активных ботов в БД")
                return list(bots)  # Конвертируем в список
                
        except Exception as e:
            logger.error(f"Ошибка загрузки ботов из БД: {e}")
            return []
    
    async def start_bot_instance(self, bot_data: TelegramBot):
        """Запускает экземпляр бота"""
        try:
            logger.info(f"Запуск бота '{bot_data.name}' (ID: {bot_data.id}, токен: {bot_data.token[:10]}...)")
            
            # Создаем экземпляр бота
            bot_instance = ZAZABot(bot_data.token, bot_data.id)
            self.running_bots[bot_data.id] = bot_instance
            
            # Запускаем бота
            await bot_instance.start_bot()
            
        except Exception as e:
            logger.error(f"Ошибка запуска бота {bot_data.name}: {e}")
            if bot_data.id in self.running_bots:
                del self.running_bots[bot_data.id]
    
    async def stop_bot_instance(self, bot_id: int):
        """Останавливает экземпляр бота"""
        if bot_id in self.running_bots:
            try:
                logger.info(f"Остановка бота ID: {bot_id}")
                await self.running_bots[bot_id].stop_bot()
                del self.running_bots[bot_id]
                
                if bot_id in self.tasks:
                    self.tasks[bot_id].cancel()
                    del self.tasks[bot_id]
                    
            except Exception as e:
                logger.error(f"Ошибка остановки бота {bot_id}: {e}")
    
    async def start_all_bots(self):
        """Запускает всех активных ботов"""
        active_bots = self.load_active_bots()
        
        if not active_bots:
            logger.warning("Нет активных ботов для запуска!")
            return
        
        # Запускаем каждого бота в отдельной задаче
        for bot_data in active_bots:
            try:
                task = asyncio.create_task(
                    self.start_bot_instance(bot_data),
                    name=f"bot_{bot_data.id}_{bot_data.name}"
                )
                self.tasks[bot_data.id] = task
                
                # Даем время на запуск
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Ошибка создания задачи для бота {bot_data.name}: {e}")
        
        logger.info(f"Запущено {len(self.tasks)} ботов")
    
    async def stop_all_bots(self):
        """Останавливает всех ботов"""
        logger.info("Остановка всех ботов...")
        
        # Останавливаем все боты
        stop_tasks = []
        for bot_id in list(self.running_bots.keys()):
            stop_tasks.append(self.stop_bot_instance(bot_id))
        
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        # Отменяем все задачи
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
        
        self.tasks.clear()
        self.running_bots.clear()
        
        logger.info("Все боты остановлены")
    
    async def reload_bots(self):
        """Перезагружает ботов (останавливает старых, запускает новых активных)"""
        logger.info("Перезагрузка ботов...")
        
        # Получаем список активных ботов из БД
        active_bots = self.load_active_bots()
        active_bot_ids = {bot.id for bot in active_bots}
        current_bot_ids = set(self.running_bots.keys())
        
        # Останавливаем ботов, которые больше не активны
        bots_to_stop = current_bot_ids - active_bot_ids
        for bot_id in bots_to_stop:
            await self.stop_bot_instance(bot_id)
        
        # Запускаем новых активных ботов
        bots_to_start = active_bot_ids - current_bot_ids
        for bot_data in active_bots:
            if bot_data.id in bots_to_start:
                try:
                    task = asyncio.create_task(
                        self.start_bot_instance(bot_data),
                        name=f"bot_{bot_data.id}_{bot_data.name}"
                    )
                    self.tasks[bot_data.id] = task
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Ошибка запуска нового бота {bot_data.name}: {e}")
        
        logger.info(f"Перезагрузка завершена. Активных ботов: {len(self.running_bots)}")
    
    async def monitor_bots(self):
        """Мониторинг состояния ботов"""
        while True:
            try:
                # Проверяем каждые 30 секунд
                await asyncio.sleep(30)
                
                # Проверяем статус задач
                dead_tasks = []
                for bot_id, task in self.tasks.items():
                    if task.done():
                        dead_tasks.append(bot_id)
                        if task.exception():
                            logger.error(f"Бот {bot_id} завершился с ошибкой: {task.exception()}")
                        else:
                            logger.warning(f"Бот {bot_id} завершился без ошибок")
                
                # Удаляем мертвые задачи
                for bot_id in dead_tasks:
                    if bot_id in self.tasks:
                        del self.tasks[bot_id]
                    if bot_id in self.running_bots:
                        del self.running_bots[bot_id]
                
                # Перезагружаем ботов раз в 5 минут
                current_time = asyncio.get_event_loop().time()
                if not hasattr(self, 'last_reload') or (current_time - self.last_reload) > 300:
                    await self.reload_bots()
                    self.last_reload = current_time
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка мониторинга: {e}")
    
    async def run(self):
        """Основной цикл работы менеджера"""
        logger.info("🤖 ZAZA Bot Manager запущен")
        
        try:
            # Запускаем всех ботов
            await self.start_all_bots()
            
            # Запускаем мониторинг
            monitor_task = asyncio.create_task(self.monitor_bots())
            
            # Ждем сигнала завершения
            await monitor_task
            
        except KeyboardInterrupt:
            logger.info("Получен сигнал завершения...")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
        finally:
            await self.stop_all_bots()
            if self.engine:
                self.engine.dispose()

# Глобальная переменная для менеджера
bot_manager = None

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    logger.info(f"Получен сигнал {signum}")
    if bot_manager:
        asyncio.create_task(bot_manager.stop_all_bots())
    sys.exit(0)

async def main():
    """Основная функция"""
    global bot_manager
    
    # Устанавливаем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        bot_manager = BotManager()
        await bot_manager.run()
    except Exception as e:
        logger.error(f"Ошибка запуска менеджера: {e}")

if __name__ == "__main__":
    print("🤖 Запуск ZAZA Bot Manager...")
    print("📋 Загрузка активных ботов из базы данных...")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot Manager остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")