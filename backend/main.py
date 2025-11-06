from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import timedelta
import uvicorn
import requests
import asyncio
import logging

from database import get_db, User, TelegramBot, Employee, ActiveTicket, ArchiveTicket, EmployeeChat, Note, TicketMessage, create_tables
from auth import verify_password, get_password_hash, create_access_token, verify_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES

app = FastAPI(title="ZAZA Admin Panel API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
import os
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

# Security управляется в auth.py

# Настройка логирования
logger = logging.getLogger(__name__)

# Функция для отправки сообщений в Telegram
def send_telegram_message(user_id: str, message: str, db: Session) -> bool:
    """Отправляет сообщение пользователю в Telegram через API бота"""
    try:
        # Получаем активного бота из БД (берем первого активного)
        bot = db.query(TelegramBot).filter(TelegramBot.is_active == True).first()
        if not bot:
            logger.error("Не найден активный бот для отправки сообщения")
            return False
        
        # URL для Telegram Bot API
        url = f"https://api.telegram.org/bot{bot.token}/sendMessage"
        
        # Данные для отправки
        data = {
            "chat_id": user_id,
            "text": message,
            "parse_mode": "HTML"  # Поддержка HTML форматирования
        }
        
        # Отправляем запрос к Telegram API
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"Сообщение отправлено пользователю {user_id}")
            return True
        else:
            logger.error(f"Ошибка отправки сообщения: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Исключение при отправке сообщения: {e}")
        return False

# Models
class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# Telegram Bot models
class TelegramBotCreate(BaseModel):
    name: str
    telegram_name: str
    token: str

class TelegramBotUpdate(BaseModel):
    name: str
    telegram_name: str
    token: str

class TelegramBotResponse(BaseModel):
    id: int
    name: str
    telegram_name: str
    token: str
    is_active: bool
    created_at: str
    updated_at: str
    
    class Config:
        orm_mode = True

# Используем get_current_user из auth.py

# Routes
@app.get("/")
async def read_root():
    return FileResponse(os.path.join(frontend_path, "login.html"))

@app.get("/dashboard.html")
async def dashboard():
    return FileResponse(os.path.join(frontend_path, "dashboard.html"))

@app.get("/tgbot.html")
async def tgbot():
    return FileResponse(os.path.join(frontend_path, "tgbot.html"))

@app.post("/api/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Убираем эндпоинт регистрации - создаем пользователей только через админа

@app.get("/api/me")
def read_users_me(current_user: dict = Depends(get_current_user)):
    return {"username": current_user["username"]}

# Telegram Bots endpoints
@app.get("/api/bots")
def get_bots(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    bots = db.query(TelegramBot).all()
    return [
        {
            "id": bot.id,
            "name": bot.name,
            "telegram_name": bot.telegram_name,
            "token": bot.token,
            "is_active": bot.is_active,
            "created_at": bot.created_at.isoformat() if bot.created_at else None,
            "updated_at": bot.updated_at.isoformat() if bot.updated_at else None
        }
        for bot in bots
    ]

@app.post("/api/bots")
def create_bot(bot: TelegramBotCreate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_bot = TelegramBot(
        name=bot.name,
        telegram_name=bot.telegram_name,
        token=bot.token
    )
    db.add(db_bot)
    db.commit()
    db.refresh(db_bot)
    return {
        "id": db_bot.id,
        "name": db_bot.name,
        "telegram_name": db_bot.telegram_name,
        "token": db_bot.token,
        "is_active": db_bot.is_active,
        "created_at": db_bot.created_at.isoformat() if db_bot.created_at else None,
        "updated_at": db_bot.updated_at.isoformat() if db_bot.updated_at else None
    }

@app.put("/api/bots/{bot_id}")
def update_bot(bot_id: int, bot: TelegramBotUpdate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_bot = db.query(TelegramBot).filter(TelegramBot.id == bot_id).first()
    if db_bot is None:
        raise HTTPException(status_code=404, detail="Бот не найден")
    
    db_bot.name = bot.name
    db_bot.telegram_name = bot.telegram_name
    db_bot.token = bot.token
    db.commit()
    db.refresh(db_bot)
    
    return {
        "id": db_bot.id,
        "name": db_bot.name,
        "telegram_name": db_bot.telegram_name,
        "token": db_bot.token,
        "is_active": db_bot.is_active,
        "created_at": db_bot.created_at.isoformat() if db_bot.created_at else None,
        "updated_at": db_bot.updated_at.isoformat() if db_bot.updated_at else None
    }

@app.delete("/api/bots/{bot_id}")
def delete_bot(bot_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_bot = db.query(TelegramBot).filter(TelegramBot.id == bot_id).first()
    if db_bot is None:
        raise HTTPException(status_code=404, detail="Бот не найден")
    
    db.delete(db_bot)
    db.commit()
    return {"message": "Бот успешно удален"}

@app.patch("/api/bots/{bot_id}/status")
def toggle_bot_status(bot_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_bot = db.query(TelegramBot).filter(TelegramBot.id == bot_id).first()
    if db_bot is None:
        raise HTTPException(status_code=404, detail="Бот не найден")
    
    # Переключаем статус
    db_bot.is_active = not db_bot.is_active
    db.commit()
    db.refresh(db_bot)
    
    return {
        "id": db_bot.id,
        "name": db_bot.name,
        "telegram_name": db_bot.telegram_name,
        "token": db_bot.token,
        "is_active": db_bot.is_active,
        "created_at": db_bot.created_at.isoformat() if db_bot.created_at else None,
        "updated_at": db_bot.updated_at.isoformat() if db_bot.updated_at else None
    }

# === ENDPOINTS ДЛЯ ТИКЕТОВ ===

@app.get("/api/tickets")
def get_active_tickets(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Получить список активных тикетов"""
    tickets = db.query(ActiveTicket).filter(ActiveTicket.status != "archive").all()
    
    result = []
    for ticket in tickets:
        result.append({
            "id": ticket.id,
            "subject": ticket.subject,
            "category": ticket.category,
            "telegram_username": ticket.telegram_username,
            "telegram_user_id": ticket.telegram_user_id,
            "status": ticket.status,
            "resolution": ticket.resolution,
            "note": ticket.note,
            "priority": ticket.priority,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None
        })
    
    return result

@app.get("/api/tickets/test")
def get_tickets_test(db: Session = Depends(get_db)):
    """Тестовый endpoint без авторизации для проверки тикетов"""
    tickets = db.query(ActiveTicket).all()
    
    result = []
    for ticket in tickets:
        result.append({
            "id": ticket.id,
            "subject": ticket.subject,
            "category": ticket.category,
            "telegram_username": ticket.telegram_username,
            "telegram_user_id": ticket.telegram_user_id,
            "status": ticket.status,
            "resolution": ticket.resolution,
            "note": ticket.note,
            "priority": ticket.priority,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None
        })
    
    return {"tickets": result, "count": len(result)}

@app.post("/api/tickets")
def create_ticket(ticket_data: dict, db: Session = Depends(get_db)):
    """Создать новый тикет"""
    try:
        ticket = ActiveTicket(
            category=ticket_data.get('category', 'general'),
            subject=ticket_data.get('subject', ''),
            telegram_user_id=ticket_data.get('telegram_user_id'),
            telegram_username=ticket_data.get('telegram_username'),
            status=ticket_data.get('status', 'active'),
            resolution=ticket_data.get('resolution', 'in_work'),
            note=ticket_data.get('note', ''),
            priority=ticket_data.get('priority', 'medium')
        )
        
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        
        return {
            "id": ticket.id,
            "subject": ticket.subject,
            "category": ticket.category,
            "telegram_username": ticket.telegram_username,
            "telegram_user_id": ticket.telegram_user_id,
            "status": ticket.status,
            "resolution": ticket.resolution,
            "note": ticket.note,
            "priority": ticket.priority,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка создания тикета: {str(e)}")

@app.get("/api/tickets/{ticket_id}")
def get_ticket_details(ticket_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Получить детали тикета с сообщениями"""
    ticket = db.query(ActiveTicket).filter(ActiveTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    # Получаем сообщения тикета
    messages = db.query(TicketMessage).filter(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.created_at).all()
    
    messages_data = []
    for msg in messages:
        messages_data.append({
            "id": msg.id,
            "telegram_user_id": msg.telegram_user_id,
            "message_type": msg.message_type,
            "content": msg.content,
            "file_id": msg.file_id,
            "is_from_admin": msg.is_from_admin,
            "created_at": msg.created_at.isoformat() if msg.created_at else None
        })
    
    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "category": ticket.category,
        "description": ticket.description,
        "telegram_username": ticket.telegram_username,
        "telegram_user_id": ticket.telegram_user_id,
        "status": ticket.status,
        "resolution": ticket.resolution,
        "note": ticket.note,
        "priority": ticket.priority,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "messages": messages_data
    }

class UpdateTicketRequest(BaseModel):
    note: str = None
    status: str = None
    resolution: str = None

@app.put("/api/tickets/{ticket_id}")
def update_ticket(ticket_id: int, request: UpdateTicketRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Обновить тикет (заметка, статус, решение)"""
    ticket = db.query(ActiveTicket).filter(ActiveTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    if request.note is not None:
        ticket.note = request.note
    if request.status is not None:
        ticket.status = request.status
    if request.resolution is not None:
        ticket.resolution = request.resolution
    
    db.commit()
    db.refresh(ticket)
    
    return {"message": "Тикет обновлен успешно"}

class SendMessageRequest(BaseModel):
    content: str
    message_type: str = "text"
    
@app.post("/api/tickets/{ticket_id}/messages")
def send_message_to_ticket(ticket_id: int, request: SendMessageRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Отправить сообщение в тикет от админа"""
    ticket = db.query(ActiveTicket).filter(ActiveTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    # Создаем сообщение от админа
    message = TicketMessage(
        ticket_id=ticket_id,
        telegram_user_id="admin",
        message_type=request.message_type,
        content=request.content,
        is_from_admin=True
    )
    
    db.add(message)
    db.commit()
    
    # Отправляем сообщение пользователю через Telegram Bot API
    success = send_telegram_message(ticket.telegram_user_id, request.content, db)
    
    if success:
        return {"message": "Сообщение отправлено"}
    else:
        raise HTTPException(status_code=500, detail="Ошибка отправки сообщения в Telegram")

if __name__ == "__main__":
    create_tables()
    uvicorn.run(app, host="0.0.0.0", port=8000)