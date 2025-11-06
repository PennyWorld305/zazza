#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для обновления старых записей сообщений с правильными типами
"""

import os
import sys
from sqlalchemy import create_engine, text
from database import DATABASE_URL, SessionLocal, TicketMessage
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_old_messages():
    """Обновляет старые записи сообщений с правильными типами"""
    try:
        session = SessionLocal()
        
        # Найдем все сообщения с file_id но без правильного message_type
        messages = session.query(TicketMessage).filter(
            TicketMessage.file_id.isnot(None),
            TicketMessage.message_type == 'text'  # Старые записи могли быть сохранены как text
        ).all()
        
        logger.info(f"Найдено {len(messages)} старых сообщений для обновления")
        
        for msg in messages:
            # Определяем тип по file_id (это приблизительно, но лучше чем ничего)
            if msg.file_id:
                if 'AgACAgIA' in msg.file_id:  # Обычно начинается так у фото в Telegram
                    msg.message_type = 'photo'
                elif 'BAACAgIA' in msg.file_id:  # Обычно начинается так у видео
                    msg.message_type = 'video'
                elif 'BQACAgIA' in msg.file_id:  # Документы
                    msg.message_type = 'document'
                else:
                    # Если не можем определить точно, попробуем по длине
                    if len(msg.file_id) > 100:
                        msg.message_type = 'photo'  # Фото обычно имеют длинные ID
                    else:
                        msg.message_type = 'document'
                
                logger.info(f"Обновлен тип сообщения {msg.id}: {msg.message_type}")
        
        session.commit()
        session.close()
        
        logger.info("✅ Обновление старых сообщений завершено!")
        
    except Exception as e:
        logger.error(f"Ошибка обновления старых сообщений: {e}")
        sys.exit(1)

if __name__ == "__main__":
    update_old_messages()