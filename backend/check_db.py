#!/usr/bin/env python3
"""
Скрипт для проверки тикетов в базе данных PostgreSQL
"""
import sys
import os
sys.path.append('.')

from database import get_db, ActiveTicket
from sqlalchemy.orm import Session

def check_tickets():
    """Проверяем тикеты в базе данных"""
    db = next(get_db())
    
    try:
        # Получаем все тикеты
        all_tickets = db.query(ActiveTicket).all()
        print(f"📊 Всего тикетов в базе: {len(all_tickets)}")
        print("=" * 50)
        
        if not all_tickets:
            print("❌ Тикеты не найдены")
            return
            
        # Группируем по статусам
        status_counts = {}
        for ticket in all_tickets:
            status = ticket.status or "null"
            status_counts[status] = status_counts.get(status, 0) + 1
            
        print("📈 Статистика по статусам:")
        for status, count in status_counts.items():
            print(f"  {status}: {count} тикет(ов)")
        
        print("\n🎫 Детали тикетов:")
        print("-" * 80)
        
        for ticket in all_tickets:
            print(f"ID: {ticket.id}")
            print(f"  Тема: {ticket.subject}")
            print(f"  Категория: {ticket.category}")
            print(f"  Статус: {ticket.status}")
            print(f"  Решение: {ticket.resolution}")
            print(f"  Создан: {ticket.created_at}")
            print(f"  Обновлен: {ticket.updated_at}")
            print("-" * 40)
            
    except Exception as e:
        print(f"❌ Ошибка при проверке базы данных: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_tickets()