from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "client_encoding": "utf8",
        "connect_timeout": 10
    },
    echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    display_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class TelegramBot(Base):
    __tablename__ = "telegram_bots"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    telegram_name = Column(String, nullable=False)
    token = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Employee(Base):
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, index=True)
    login = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ActiveTicket(Base):
    __tablename__ = "active_tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False)  # Тема тикета
    category = Column(String, nullable=False)  # Категория (dispute, crypto_payment, etc.)
    description = Column(Text)
    telegram_user_id = Column(String, nullable=False)  # ID пользователя в Telegram
    telegram_username = Column(String)  # Username пользователя в Telegram
    assigned_to = Column(Integer, ForeignKey("employees.id"))
    status = Column(String, default="active")  # active, in_work, archive
    resolution = Column(String, default="in_work")  # in_work, refuse, refund
    note = Column(Text)  # Заметка админа
    priority = Column(String, default="medium")
    bot_id = Column(Integer, ForeignKey("telegram_bots.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    employee = relationship("Employee")
    bot = relationship("TelegramBot")

class ArchiveTicket(Base):
    __tablename__ = "archive_tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    assigned_to = Column(Integer, ForeignKey("employees.id"))
    status = Column(String, default="closed")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    employee = relationship("Employee")

class EmployeeChat(Base):
    __tablename__ = "employee_chat"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    employee = relationship("Employee")

class Note(Base):
    __tablename__ = "notes"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    employee = relationship("Employee")

class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("active_tickets.id"), nullable=False)
    telegram_user_id = Column(String, nullable=False)
    message_type = Column(String, nullable=False)  # text, photo, video, document
    content = Column(Text)  # Текст сообщения или описание
    file_id = Column(String)  # ID файла в Telegram (для медиа)
    local_file_path = Column(String)  # Локальный путь к сохраненному файлу на сервере
    original_filename = Column(String)  # Оригинальное имя файла
    file_size = Column(Integer)  # Размер файла в байтах
    is_from_admin = Column(Boolean, default=False)  # Сообщение от админа или клиента
    created_at = Column(DateTime, default=datetime.utcnow)
    
    ticket = relationship("ActiveTicket")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    Base.metadata.create_all(bind=engine)