#!/usr/bin/env python3
"""
Скрипт для детальной проверки сообщений с ролями
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, TicketMessage, Employee
from sqlalchemy.orm import Session

def check_messages_with_roles():
    """Проверка сообщений с информацией о ролях"""
    db = SessionLocal()
    try:
        print("🔍 Проверяю последние 5 сообщений с ролями:")
        messages = db.query(TicketMessage).order_by(TicketMessage.created_at.desc()).limit(5).all()
        
        for msg in messages:
            # Определяем роль как в коде
            sender_name = "Клиент"
            sender_role = "client"
            
            if msg.is_from_admin:
                if msg.telegram_user_id == "admin":
                    sender_name = "Админ"
                    sender_role = "admin"
                elif msg.telegram_user_id.startswith("employee_"):
                    employee_id = msg.telegram_user_id.replace("employee_", "")
                    try:
                        employee = db.query(Employee).filter(Employee.id == int(employee_id)).first()
                        if employee:
                            sender_name = employee.name
                            sender_role = employee.role
                        else:
                            sender_name = "Сотрудник"
                            sender_role = "employee"
                    except:
                        sender_name = "Сотрудник"
                        sender_role = "employee"
            
            print(f"ID: {msg.id}")
            print(f"  Ticket: {msg.ticket_id}")
            print(f"  telegram_user_id: {msg.telegram_user_id}")
            print(f"  is_from_admin: {msg.is_from_admin}")
            print(f"  sender_name: {sender_name}")
            print(f"  sender_role: {sender_role}")
            print(f"  content: {msg.content[:30]}...")
            print(f"  created: {msg.created_at}")
            print("---")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_messages_with_roles()