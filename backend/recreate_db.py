#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для пересоздания базы данных с новыми полями
"""

import os
from database import engine, Base

def recreate_database():
    """Пересоздает базу данных"""
    print("🔄 Пересоздание базы данных...")
    
    # Удаляем существующую БД
    db_file = "zaza_admin.db"
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"✅ Удалена старая БД: {db_file}")
    
    # Создаем новую БД с обновленными моделями
    Base.metadata.create_all(bind=engine)
    print("✅ Создана новая база данных с обновленными полями")
    print("📝 Добавлены поля: sender_role, sender_name в TicketMessage")

if __name__ == "__main__":
    recreate_database()