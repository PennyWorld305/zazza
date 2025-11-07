#!/usr/bin/env python3
"""
Скрипт для проверки последних сообщений в PostgreSQL базе данных
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, TicketMessage, Employee
from sqlalchemy.orm import Session

def check_recent_messages():
    """Проверка последних сообщений"""
    db = SessionLocal()
    try:
        print("🔍 Проверяю последние 5 сообщений:")
        messages = db.query(TicketMessage).order_by(TicketMessage.created_at.desc()).limit(5).all()
        
        for msg in messages:
            print(f"ID: {msg.id}, Ticket: {msg.ticket_id}, User: {msg.telegram_user_id}, "
                  f"Content: {msg.content[:30]}..., is_from_admin: {msg.is_from_admin}, "
                  f"Created: {msg.created_at}")
        
        print("\n👥 Проверяю сотрудников:")
        employees = db.query(Employee).all()
        for emp in employees:
            print(f"ID: {emp.id}, Login: {emp.login}, Name: {emp.name}, Role: {emp.role}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_recent_messages()