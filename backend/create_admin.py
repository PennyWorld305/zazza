"""
Скрипт для создания админа ZAZA
"""
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Добавляем путь к модулям
sys.path.append(os.path.dirname(__file__))

from database import User, Base
from auth import get_password_hash

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def create_admin():
    # Создаем подключение к БД
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Создаем таблицы если их нет
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Проверяем, есть ли уже админ
        existing_admin = db.query(User).filter(User.username == "admin").first()
        if existing_admin:
            print("Пользователь 'admin' уже существует!")
            return
        
        # Создаем админа
        password = "admin123"[:72]  # Ограничиваем длину пароля для bcrypt
        hashed_password = get_password_hash(password)
        admin_user = User(
            username="admin",
            hashed_password=hashed_password,
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        
        print("✅ Админ создан успешно!")
        print("Логин: admin")
        print("Пароль: admin123")
        print("\n⚠️ ВАЖНО: Смените пароль после первого входа!")
        
    except Exception as e:
        print(f"❌ Ошибка при создании админа: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()