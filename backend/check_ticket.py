#!/usr/bin/env python3
"""
Проверка назначения курьера к тикету
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, ActiveTicket

def check_ticket_courier():
    """Проверка назначения курьера"""
    db = SessionLocal()
    try:
        ticket = db.query(ActiveTicket).filter(ActiveTicket.id == 19).first()
        if ticket:
            print(f"Тикет 19:")
            print(f"  Subject: {ticket.subject}")
            print(f"  Courier ID: {ticket.courier_id}")
        else:
            print("Тикет 19 не найден")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_ticket_courier()