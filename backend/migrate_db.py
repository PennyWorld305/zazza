#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт миграции БД для добавления полей медиафайлов в TicketMessage
"""

import os
import sys
from sqlalchemy import create_engine, text
from database import DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """Добавляет новые поля в таблицу ticket_messages"""
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Проверяем, существует ли уже поле local_file_path
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='ticket_messages' 
                AND column_name='local_file_path'
            """))
            
            if not result.fetchone():
                logger.info("Добавляем новые поля в таблицу ticket_messages...")
                
                # Добавляем новые поля
                conn.execute(text("ALTER TABLE ticket_messages ADD COLUMN local_file_path VARCHAR"))
                conn.execute(text("ALTER TABLE ticket_messages ADD COLUMN original_filename VARCHAR"))
                conn.execute(text("ALTER TABLE ticket_messages ADD COLUMN file_size INTEGER"))
                
                conn.commit()
                logger.info("✅ Миграция завершена успешно!")
            else:
                logger.info("Поля уже существуют, миграция не требуется")
                
    except Exception as e:
        logger.error(f"Ошибка миграции: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate_database()