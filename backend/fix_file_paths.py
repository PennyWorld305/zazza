#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для исправления путей к файлам в базе данных
"""

import os
import sys
from database import SessionLocal, TicketMessage
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_file_paths():
    """Исправляет пути к файлам в базе данных"""
    try:
        session = SessionLocal()
        
        # Найдем все сообщения с local_file_path, которые начинаются с media\
        messages = session.query(TicketMessage).filter(
            TicketMessage.local_file_path.like('media%')
        ).all()
        
        logger.info(f"Найдено {len(messages)} сообщений для исправления путей:")
        
        for msg in messages:
            old_path = msg.local_file_path
            # Удаляем media\ или media/ из начала пути
            new_path = old_path.replace('media\\', '').replace('media/', '')
            msg.local_file_path = new_path
            
            logger.info(f"ID {msg.id}: '{old_path}' -> '{new_path}'")
        
        session.commit()
        session.close()
        
        logger.info("✅ Исправление путей завершено!")
        
    except Exception as e:
        logger.error(f"Ошибка исправления путей: {e}")
        sys.exit(1)

if __name__ == "__main__":
    fix_file_paths()