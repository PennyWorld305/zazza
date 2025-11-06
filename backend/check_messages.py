#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для проверки данных сообщений в базе данных
"""

import os
import sys
from database import SessionLocal, TicketMessage
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_messages():
    """Проверяет данные сообщений в базе"""
    try:
        session = SessionLocal()
        
        # Найдем последние сообщения
        messages = session.query(TicketMessage).order_by(TicketMessage.created_at.desc()).limit(10).all()
        
        logger.info(f"Найдено {len(messages)} сообщений:")
        
        for msg in messages:
            logger.info(f"""
ID: {msg.id}
Тикет: {msg.ticket_id}  
Тип: {msg.message_type}
Содержание: {msg.content[:50]}...
File ID: {msg.file_id}
Local path: {msg.local_file_path}
Original filename: {msg.original_filename}
File size: {msg.file_size}
От админа: {msg.is_from_admin}
Дата: {msg.created_at}
---
""")
        
        # Найдем сообщения с file_id
        photo_messages = session.query(TicketMessage).filter(TicketMessage.file_id.isnot(None)).all()
        logger.info(f"Сообщений с файлами: {len(photo_messages)}")
        
        session.close()
        
    except Exception as e:
        logger.error(f"Ошибка проверки сообщений: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_messages()