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
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional

from database import get_db, User, TelegramBot, Employee, ActiveTicket, ArchiveTicket, EmployeeChat, Note, TicketMessage, Client, create_tables
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

# Media files - попробуем простой подход
@app.get("/media/{file_path:path}")
def serve_media_files(file_path: str):
    """Прямая отдача медиа файлов"""
    backend_dir = Path(__file__).parent
    full_path = backend_dir / "media" / file_path
    
    if full_path.exists() and full_path.is_file():
        return FileResponse(full_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")

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

# Функции для работы с медиафайлами
async def download_telegram_file(file_id: str, file_type: str, db: Session) -> Optional[dict]:
    """Скачивает файл из Telegram и сохраняет на сервере"""
    try:
        # Получаем активного бота из БД
        bot = db.query(TelegramBot).filter(TelegramBot.is_active == True).first()
        if not bot:
            logger.error("Не найден активный бот для скачивания файла")
            return None
        
        # Получаем информацию о файле
        get_file_url = f"https://api.telegram.org/bot{bot.token}/getFile"
        get_file_response = requests.get(get_file_url, params={"file_id": file_id})
        
        if get_file_response.status_code != 200:
            logger.error(f"Ошибка получения информации о файле: {get_file_response.text}")
            return None
        
        file_info = get_file_response.json()["result"]
        file_path = file_info["file_path"]
        file_size = file_info.get("file_size", 0)
        
        # Создаем уникальное имя файла
        file_extension = Path(file_path).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Определяем папку для сохранения
        media_folder = {
            "photo": "photos",
            "video": "videos", 
            "document": "documents"
        }.get(file_type, "documents")
        
        # Создаем путь для сохранения
        save_dir = Path("media") / media_folder
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / unique_filename
        
        # Скачиваем файл
        download_url = f"https://api.telegram.org/file/bot{bot.token}/{file_path}"
        download_response = requests.get(download_url, stream=True)
        
        if download_response.status_code != 200:
            logger.error(f"Ошибка скачивания файла: {download_response.text}")
            return None
        
        # Сохраняем файл
        with open(save_path, "wb") as f:
            shutil.copyfileobj(download_response.raw, f)
        
        return {
            "local_path": f"{media_folder}/{unique_filename}",  # Относительный путь от media/
            "original_filename": Path(file_path).name,
            "file_size": file_size
        }
        
    except Exception as e:
        logger.error(f"Исключение при скачивании файла: {e}")
        return None

def get_media_url(local_file_path: str) -> str:
    """Генерирует URL для доступа к медиафайлу"""
    if not local_file_path:
        return ""
    # Преобразуем путь в URL для API
    return f"/api/media/{local_file_path.replace(os.sep, '/')}"

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

class UserProfileUpdate(BaseModel):
    display_name: str

class UserPasswordChange(BaseModel):
    current_password: str
    new_password: str

class UserProfile(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    is_active: bool
    
    class Config:
        orm_mode = True

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

@app.get("/profile.html")
async def profile():
    return FileResponse(os.path.join(frontend_path, "profile.html"))

@app.get("/static/profile.html")
async def static_profile():
    return FileResponse(os.path.join(frontend_path, "profile.html"))

@app.post("/api/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    # Сначала ищем среди User (админов)
    user = db.query(User).filter(User.username == user_data.username).first()
    if user and verify_password(user_data.password, user.hashed_password):
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "type": "user", "id": user.id}, 
            expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    
    # Если не найден среди User, ищем среди Employee (сотрудников)
    employee = db.query(Employee).filter(Employee.login == user_data.username).first()
    if employee and employee.is_active and verify_password(user_data.password, employee.hashed_password):
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": employee.login, "type": "employee", "id": employee.id, "role": employee.role}, 
            expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    
    # Если никого не найдено
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверный логин или пароль",
        headers={"WWW-Authenticate": "Bearer"},
    )

# Убираем эндпоинт регистрации - создаем пользователей только через админа

@app.get("/api/me")
def read_users_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user["type"] == "user":
        user = db.query(User).filter(User.username == current_user["username"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name or user.username,
            "is_active": user.is_active,
            "type": "user",
            "role": "admin"
        }
    
    elif current_user["type"] == "employee":
        employee = db.query(Employee).filter(Employee.login == current_user["username"]).first()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        return {
            "id": employee.id,
            "username": employee.login,
            "display_name": employee.name,
            "is_active": employee.is_active,
            "type": "employee",
            "role": employee.role
        }
    
    else:
        raise HTTPException(status_code=404, detail="User not found")

@app.put("/api/profile/update")
def update_profile(
    profile_data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == current_user["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Обновляем отображаемое имя
    user.display_name = profile_data.display_name.strip()
    
    try:
        db.commit()
        db.refresh(user)
        return {"message": "Profile updated successfully", "display_name": user.display_name}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update profile")

@app.put("/api/profile/change-password")
def change_password(
    password_data: UserPasswordChange,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == current_user["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверяем текущий пароль
    if not verify_password(password_data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Проверяем длину нового пароля
    if len(password_data.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters long")
    
    # Обновляем пароль
    user.hashed_password = get_password_hash(password_data.new_password)
    
    try:
        db.commit()
        return {"message": "Password changed successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to change password")

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
    query = db.query(ActiveTicket).filter(ActiveTicket.status != "archive")
    
    # Если пользователь - курьер, показываем только те тикеты, куда он приглашен
    if current_user["type"] == "employee":
        employee = db.query(Employee).filter(Employee.login == current_user["username"]).first()
        if employee and employee.role == "courier":
            query = query.filter(ActiveTicket.courier_id == employee.id)
    
    tickets = query.all()
    
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

@app.get("/api/tickets/archive")
def get_archive_tickets(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Получить список архивных тикетов"""
    query = db.query(ActiveTicket).filter(ActiveTicket.status == "archive")
    
    # Если пользователь - курьер, показываем только те тикеты, куда он приглашен
    if current_user["type"] == "employee":
        employee = db.query(Employee).filter(Employee.login == current_user["username"]).first()
        if employee and employee.role == "courier":
            query = query.filter(ActiveTicket.courier_id == employee.id)
    
    tickets = query.all()
    
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
    
    # Если пользователь - курьер, проверяем доступ к тикету
    if current_user["type"] == "employee":
        employee = db.query(Employee).filter(Employee.login == current_user["username"]).first()
        if employee and employee.role == "courier":
            if ticket.courier_id != employee.id:
                raise HTTPException(status_code=403, detail="Доступ запрещен. Вы не приглашены к этому тикету")
    
    # Получаем сообщения тикета
    messages = db.query(TicketMessage).filter(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.created_at).all()
    
    messages_data = []
    for msg in messages:
        # Определяем имя отправителя и роль
        sender_name = "Клиент"
        sender_role = "client"
        
        if msg.is_from_admin:
            if msg.telegram_user_id == "admin":
                sender_name = "Админ"
                sender_role = "admin"
            elif msg.telegram_user_id.startswith("employee_"):
                # Извлекаем ID сотрудника и получаем его имя и роль
                employee_id = msg.telegram_user_id.replace("employee_", "")
                try:
                    employee = db.query(Employee).filter(Employee.id == int(employee_id)).first()
                    if employee:
                        sender_name = employee.name
                        sender_role = employee.role  # admin, operator, courier
                    else:
                        sender_name = "Сотрудник"
                        sender_role = "employee"
                except:
                    sender_name = "Сотрудник" 
                    sender_role = "employee"
        
        messages_data.append({
            "id": msg.id,
            "telegram_user_id": msg.telegram_user_id,
            "message_type": msg.message_type,
            "content": msg.content,
            "file_id": msg.file_id,
            "local_file_path": msg.local_file_path,
            "original_filename": msg.original_filename,
            "file_size": msg.file_size,
            "is_from_admin": msg.is_from_admin,
            "sender_name": sender_name,
            "sender_role": sender_role,
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
    
    # Если пользователь - курьер, запрещаем обновление тикета
    if current_user["type"] == "employee":
        employee = db.query(Employee).filter(Employee.login == current_user["username"]).first()
        if employee and employee.role == "courier":
            raise HTTPException(status_code=403, detail="Доступ запрещен. Курьеры не могут изменять тикеты")
    
    # Сохраняем старый статус для проверки изменений
    old_status = ticket.status
    
    if request.note is not None:
        ticket.note = request.note
    if request.status is not None:
        ticket.status = request.status
    if request.resolution is not None:
        ticket.resolution = request.resolution
    
    db.commit()
    db.refresh(ticket)
    
    # Если тикет был закрыт (изменен на archive), отправляем уведомление клиенту
    if old_status != "archive" and ticket.status == "archive":
        # Определяем текст уведомления в зависимости от решения
        if ticket.resolution == "refuse":
            notification_message = f"""
❌ **Тикет #{ticket.id} закрыт**

Решение: **Отказ**

По вашему обращению принято решение об отказе.

Если у вас есть новые вопросы, вы можете создать новое обращение с помощью команды /start.

🤖 С уважением, служба поддержки ZAZA
"""
        elif ticket.resolution == "refund":
            notification_message = f"""
💰 **Тикет #{ticket.id} закрыт**

Решение: **Возврат**

По вашему обращению произведен возврат средств.

Если у вас есть новые вопросы, вы можете создать новое обращение с помощью команды /start.

🤖 С уважением, служба поддержки ZAZA
"""
        else:
            resolution_text = ticket.resolution or "Тикет закрыт, решение принято"
            notification_message = f"""
✅ **Тикет #{ticket.id} закрыт**

{resolution_text}

Спасибо за обращение! Если у вас есть новые вопросы, вы можете создать новое обращение с помощью команды /start.

🤖 С уважением, служба поддержки ZAZA
"""
        
        # Отправляем уведомление пользователю
        send_telegram_message(ticket.telegram_user_id, notification_message, db)
    
    return {"message": "Тикет обновлен успешно"}

class SendMessageRequest(BaseModel):
    content: str
    message_type: str = "text"
    
@app.post("/api/tickets/{ticket_id}/messages")
def send_message_to_ticket(ticket_id: int, request: SendMessageRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Отправить сообщение в тикет от админа или сотрудника"""
    ticket = db.query(ActiveTicket).filter(ActiveTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    # Если пользователь - курьер, проверяем доступ к тикету
    if current_user["type"] == "employee":
        employee = db.query(Employee).filter(Employee.login == current_user["username"]).first()
        if employee and employee.role == "courier":
            if ticket.courier_id != employee.id:
                raise HTTPException(status_code=403, detail="Доступ запрещен. Вы не приглашены к этому тикету")
    
    # Определяем отправителя сообщения и роль
    sender_role = None
    sender_name = None
    
    if current_user["type"] == "user":
        # Сообщение от админа
        sender_id = "admin"
        sender_role = "admin"
        sender_name = "Админ"
        is_from_admin = True
    else:
        # Сообщение от сотрудника
        employee = db.query(Employee).filter(Employee.login == current_user["username"]).first()
        if employee:
            sender_id = f"employee_{employee.id}"
            sender_role = employee.role
            sender_name = employee.name
            is_from_admin = True
        else:
            sender_id = current_user["username"]
            sender_role = "admin"  # fallback
            sender_name = "Админ"
            is_from_admin = True
    
    # Формируем сообщение с указанием роли для клиента
    role_display = {
        "admin": "Админ",
        "operator": "Оператор", 
        "courier": "Курьер"
    }.get(sender_role, "Сотрудник")
    
    formatted_message = f"{role_display}:\n\n{request.content}"
    
    # Создаем сообщение в БД
    message = TicketMessage(
        ticket_id=ticket_id,
        telegram_user_id=sender_id,
        message_type=request.message_type,
        content=request.content,
        is_from_admin=is_from_admin,
        sender_role=sender_role,
        sender_name=sender_name
    )
    
    db.add(message)
    db.commit()
    
    # Отправляем форматированное сообщение пользователю через Telegram Bot API
    success = send_telegram_message(ticket.telegram_user_id, formatted_message, db)
    
    if success:
        return {"message": "Сообщение отправлено"}
    else:
        raise HTTPException(status_code=500, detail="Ошибка отправки сообщения в Telegram")

@app.get("/api/media/{file_path:path}")
def get_media_file(file_path: str):
    """Отдает медиафайлы (фото, видео, документы)"""
    try:
        # Безопасно формируем путь к файлу в backend/media/
        backend_dir = Path(__file__).parent
        file_full_path = backend_dir / "media" / file_path
        media_dir = backend_dir / "media"
        
        # Проверяем, что файл существует и находится в папке media
        if not file_full_path.exists() or not str(file_full_path.resolve()).startswith(str(media_dir.resolve())):
            raise HTTPException(status_code=404, detail="Файл не найден")
        
        # Определяем MIME-type
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg', 
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.mp4': 'video/mp4',
            '.avi': 'video/avi',
            '.mov': 'video/quicktime',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        
        file_extension = file_full_path.suffix.lower()
        media_type = mime_types.get(file_extension, 'application/octet-stream')
        
        return FileResponse(
            path=str(file_full_path),
            media_type=media_type,
            filename=file_full_path.name
        )
        
    except Exception as e:
        logger.error(f"Ошибка при отдаче медиафайла {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@app.get("/backend/media/{file_path:path}")
def get_backend_media_file(file_path: str):
    """Альтернативный маршрут для медиафайлов через /backend/media/"""
    return get_media_file(file_path)

# === КЛИЕНТЫ ===

@app.get("/api/clients")
def get_clients(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Получить список всех клиентов с количеством тикетов"""
    
    # Получаем всех уникальных клиентов из тикетов
    clients_from_tickets = db.query(
        ActiveTicket.telegram_user_id,
        ActiveTicket.telegram_username
    ).distinct().all()
    
    clients_data = []
    
    for client_ticket in clients_from_tickets:
        # Проверяем есть ли клиент в таблице clients
        client = db.query(Client).filter(Client.telegram_user_id == client_ticket.telegram_user_id).first()
        
        # Если нет - создаем
        if not client:
            client = Client(
                telegram_user_id=client_ticket.telegram_user_id,
                telegram_username=client_ticket.telegram_username,
                is_blocked=False
            )
            db.add(client)
            db.commit()
            db.refresh(client)
        
        # Считаем количество тикетов клиента
        tickets_count = db.query(ActiveTicket).filter(ActiveTicket.telegram_user_id == client.telegram_user_id).count()
        
        clients_data.append({
            "id": client.id,
            "telegram_user_id": client.telegram_user_id,
            "telegram_username": client.telegram_username or "Не указан",
            "first_name": client.first_name,
            "last_name": client.last_name,
            "is_blocked": client.is_blocked,
            "tickets_count": tickets_count,
            "created_at": client.created_at.isoformat() if client.created_at else None,
            "updated_at": client.updated_at.isoformat() if client.updated_at else None
        })
    
    return {"clients": clients_data}

@app.get("/api/clients/{client_id}")
def get_client_details(client_id: int, page: int = 1, limit: int = 10, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Получить детали клиента с его тикетами"""
    
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    
    # Получаем общее количество тикетов
    total_tickets = db.query(ActiveTicket).filter(ActiveTicket.telegram_user_id == client.telegram_user_id).count()
    
    # Получаем тикеты с пагинацией
    offset = (page - 1) * limit
    tickets = db.query(ActiveTicket).filter(ActiveTicket.telegram_user_id == client.telegram_user_id).order_by(ActiveTicket.created_at.desc()).offset(offset).limit(limit).all()
    
    # Подсчитываем статистику по всем тикетам клиента
    all_tickets = db.query(ActiveTicket).filter(ActiveTicket.telegram_user_id == client.telegram_user_id).all()
    
    # Статистика по категориям
    category_stats = {}
    resolution_stats = {}
    
    for t in all_tickets:
        # Статистика категорий
        if t.category:
            category_stats[t.category] = category_stats.get(t.category, 0) + 1
        
        # Статистика резолюций
        if t.resolution:
            resolution_stats[t.resolution] = resolution_stats.get(t.resolution, 0) + 1
    
    tickets_data = []
    for ticket in tickets:
        # Получаем сообщения для каждого тикета
        messages = db.query(TicketMessage).filter(TicketMessage.ticket_id == ticket.id).order_by(TicketMessage.created_at).all()
        
        messages_data = []
        for msg in messages:
            messages_data.append({
                "id": msg.id,
                "telegram_user_id": msg.telegram_user_id,
                "message_type": msg.message_type,
                "content": msg.content,
                "file_id": msg.file_id,
                "local_file_path": msg.local_file_path,
                "original_filename": msg.original_filename,
                "file_size": msg.file_size,
                "is_from_admin": msg.is_from_admin,
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            })
        
        tickets_data.append({
            "id": ticket.id,
            "subject": ticket.subject,
            "category": ticket.category,
            "description": ticket.description,
            "status": ticket.status,
            "resolution": ticket.resolution,
            "priority": ticket.priority,
            "note": ticket.note,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
            "messages": messages_data
        })
    
    return {
        "client": {
            "id": client.id,
            "telegram_user_id": client.telegram_user_id,
            "telegram_username": client.telegram_username,
            "first_name": client.first_name,
            "last_name": client.last_name,
            "is_blocked": client.is_blocked,
            "created_at": client.created_at.isoformat() if client.created_at else None,
            "updated_at": client.updated_at.isoformat() if client.updated_at else None
        },
        "tickets": tickets_data,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total_tickets,
            "pages": (total_tickets + limit - 1) // limit
        },
        "statistics": {
            "categories": category_stats,
            "resolutions": resolution_stats,
            "total_tickets": total_tickets
        }
    }

@app.put("/api/clients/{client_id}/block")
def toggle_client_block(client_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Заблокировать/разблокировать клиента"""
    
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    
    # Переключаем статус блокировки
    client.is_blocked = not client.is_blocked
    db.commit()
    
    action = "заблокирован" if client.is_blocked else "разблокирован"
    
    return {
        "message": f"Клиент {action} успешно",
        "is_blocked": client.is_blocked
    }

# === ЗАМЕТКИ ===

class NoteCreate(BaseModel):
    title: str
    content: str

class NoteUpdate(BaseModel):
    title: str
    content: str

@app.get("/api/notes")
def get_notes(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Получить все заметки текущего пользователя"""
    
    # Для User используем user_id, для Employee - тоже id (но будем хранить в user_id)
    user_id = current_user["id"]
    notes = db.query(Note).filter(Note.user_id == user_id).order_by(Note.updated_at.desc()).all()
    
    notes_data = []
    for note in notes:
        notes_data.append({
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "updated_at": note.updated_at.isoformat() if note.updated_at else None
        })
    
    return {"notes": notes_data}

@app.post("/api/notes")
def create_note(note_data: NoteCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Создать новую заметку"""
    
    user_id = current_user["id"]
    note = Note(
        user_id=user_id,
        title=note_data.title,
        content=note_data.content
    )
    
    db.add(note)
    db.commit()
    db.refresh(note)
    
    return {
        "message": "Заметка создана успешно",
        "note": {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "updated_at": note.updated_at.isoformat() if note.updated_at else None
        }
    }

@app.put("/api/notes/{note_id}")
def update_note(note_id: int, note_data: NoteUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Обновить заметку"""
    
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user["id"]).first()
    if not note:
        raise HTTPException(status_code=404, detail="Заметка не найдена")
    
    note.title = note_data.title
    note.content = note_data.content
    db.commit()
    db.refresh(note)
    
    return {
        "message": "Заметка обновлена успешно",
        "note": {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "updated_at": note.updated_at.isoformat() if note.updated_at else None
        }
    }

@app.delete("/api/notes/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Удалить заметку"""
    
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user["id"]).first()
    if not note:
        raise HTTPException(status_code=404, detail="Заметка не найдена")
    
    db.delete(note)
    db.commit()
    
    return {"message": "Заметка удалена успешно"}

# === СОТРУДНИКИ ===

class EmployeeCreate(BaseModel):
    login: str
    name: str
    role: str
    password: str

class EmployeeUpdate(BaseModel):
    login: Optional[str] = None
    name: str
    role: str
    is_active: bool
    password: Optional[str] = None

class EmployeePasswordUpdate(BaseModel):
    password: str

@app.get("/api/employees")
def get_employees(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Получить список всех сотрудников (только для админов)"""
    
    # Проверяем права доступа - админы и операторы могут видеть список сотрудников
    if current_user["type"] == "employee":
        employee = db.query(Employee).filter(Employee.login == current_user["username"]).first()
        if employee and employee.role == "courier":
            raise HTTPException(status_code=403, detail="Доступ запрещен. Курьеры не могут просматривать список сотрудников.")
    elif current_user["type"] != "user":
        raise HTTPException(status_code=403, detail="Доступ запрещен. Требуются права администратора или оператора.")
    
    # Получаем всех сотрудников
    employees = db.query(Employee).order_by(Employee.created_at.desc()).all()
    
    employees_data = []
    for employee in employees:
        employees_data.append({
            "id": employee.id,
            "login": employee.login,
            "name": employee.name,
            "role": employee.role,
            "is_active": employee.is_active,
            "created_at": employee.created_at.isoformat() if employee.created_at else None,
            "updated_at": employee.updated_at.isoformat() if employee.updated_at else None
        })
    
    return {"employees": employees_data}

@app.post("/api/employees")
def create_employee(employee_data: EmployeeCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Создать нового сотрудника (админы - всех, операторы - только курьеров)"""
    
    # Проверяем права доступа
    if current_user["type"] == "employee":
        employee = db.query(Employee).filter(Employee.login == current_user["username"]).first()
        if employee and employee.role == "operator":
            # Операторы могут создавать только курьеров
            if employee_data.role != "courier":
                raise HTTPException(status_code=403, detail="Операторы могут создавать только курьеров")
        elif employee and employee.role == "courier":
            raise HTTPException(status_code=403, detail="Курьеры не могут создавать сотрудников")
    elif current_user["type"] != "user":
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    # Проверяем, что логин уникален
    existing_employee = db.query(Employee).filter(Employee.login == employee_data.login).first()
    if existing_employee:
        raise HTTPException(status_code=400, detail="Сотрудник с таким логином уже существует")
    
    # Валидация роли
    if employee_data.role not in ["admin", "operator", "courier"]:
        raise HTTPException(status_code=400, detail="Недопустимая роль. Доступны: admin, operator, courier")
    
    # Хэшируем пароль
    hashed_password = get_password_hash(employee_data.password)
    
    # Создаем сотрудника
    employee = Employee(
        login=employee_data.login,
        name=employee_data.name,
        role=employee_data.role,
        hashed_password=hashed_password,
        is_active=True
    )
    
    db.add(employee)
    db.commit()
    db.refresh(employee)
    
    return {
        "message": "Сотрудник создан успешно",
        "employee": {
            "id": employee.id,
            "login": employee.login,
            "name": employee.name,
            "role": employee.role,
            "is_active": employee.is_active,
            "created_at": employee.created_at.isoformat() if employee.created_at else None
        }
    }

@app.put("/api/employees/{employee_id}")
def update_employee(employee_id: int, employee_data: EmployeeUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Обновить данные сотрудника (админы - всех, операторы - только курьеров)"""
    
    # Проверяем права доступа
    if current_user["type"] == "employee":
        current_employee = db.query(Employee).filter(Employee.login == current_user["username"]).first()
        if current_employee and current_employee.role == "operator":
            # Операторы могут редактировать только курьеров
            target_employee = db.query(Employee).filter(Employee.id == employee_id).first()
            if target_employee and target_employee.role != "courier":
                raise HTTPException(status_code=403, detail="Операторы могут редактировать только курьеров")
            # Операторы не могут изменять роль на не-курьера
            if employee_data.role and employee_data.role != "courier":
                raise HTTPException(status_code=403, detail="Операторы могут устанавливать только роль курьера")
        elif current_employee and current_employee.role == "courier":
            raise HTTPException(status_code=403, detail="Курьеры не могут редактировать сотрудников")
    elif current_user["type"] != "user":
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    # Находим сотрудника
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    
    # Валидация роли
    if employee_data.role not in ["admin", "operator", "courier"]:
        raise HTTPException(status_code=400, detail="Недопустимая роль. Доступны: admin, operator, courier")
    
    # Проверяем уникальность логина, если он изменяется
    if employee_data.login and employee_data.login != employee.login:
        existing_employee = db.query(Employee).filter(Employee.login == employee_data.login, Employee.id != employee_id).first()
        if existing_employee:
            raise HTTPException(status_code=400, detail="Сотрудник с таким логином уже существует")
        employee.login = employee_data.login
    
    # Обновляем данные
    employee.name = employee_data.name
    employee.role = employee_data.role
    employee.is_active = employee_data.is_active
    
    # Обновляем пароль если он передан
    if employee_data.password:
        employee.hashed_password = get_password_hash(employee_data.password)
    
    db.commit()
    db.refresh(employee)
    
    return {
        "message": "Данные сотрудника обновлены успешно",
        "employee": {
            "id": employee.id,
            "login": employee.login,
            "name": employee.name,
            "role": employee.role,
            "is_active": employee.is_active,
            "updated_at": employee.updated_at.isoformat() if employee.updated_at else None
        }
    }

@app.put("/api/employees/{employee_id}/password")
def update_employee_password(employee_id: int, password_data: EmployeePasswordUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Обновить пароль сотрудника (только для админов)"""
    
    # Проверяем права доступа
    if not (current_user["type"] == "user"):
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    # Находим сотрудника
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    
    # Хэшируем новый пароль
    employee.hashed_password = get_password_hash(password_data.password)
    
    db.commit()
    
    return {"message": "Пароль сотрудника обновлен успешно"}

@app.delete("/api/employees/{employee_id}")
def delete_employee(employee_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Удалить сотрудника (только для админов)"""
    
    # Проверяем права доступа
    if not (current_user["type"] == "user"):
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    # Находим сотрудника
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    
    # Не даем удалить админа
    if employee.role == "admin":
        raise HTTPException(status_code=400, detail="Нельзя удалить администратора")
    
    # Удаляем сотрудника
    db.delete(employee)
    db.commit()
    
    return {"message": "Сотрудник удален успешно"}

@app.get("/api/employees/active-couriers")
def get_active_couriers(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Получить список активных курьеров для приглашения в тикет"""
    
    couriers = db.query(Employee).filter(
        Employee.role == "courier",
        Employee.is_active == True
    ).order_by(Employee.name).all()
    
    couriers_data = []
    for courier in couriers:
        couriers_data.append({
            "id": courier.id,
            "name": courier.name,
            "login": courier.login
        })
    
    return {"couriers": couriers_data}

@app.post("/api/tickets/{ticket_id}/invite-courier")
def invite_courier_to_ticket(
    ticket_id: int, 
    courier_data: dict,
    db: Session = Depends(get_db), 
    current_user: dict = Depends(get_current_user)
):
    """Пригласить курьера в тикет (только для операторов и админов)"""
    
    # Проверяем, что пользователь не курьер
    if current_user["type"] == "employee":
        employee = db.query(Employee).filter(Employee.login == current_user["username"]).first()
        if employee and employee.role == "courier":
            raise HTTPException(status_code=403, detail="Доступ запрещен. Курьеры не могут приглашать других курьеров")
    
    # Находим тикет
    ticket = db.query(ActiveTicket).filter(ActiveTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    # Проверяем курьера
    courier_id = courier_data.get("courier_id")
    courier = db.query(Employee).filter(
        Employee.id == courier_id,
        Employee.role == "courier",
        Employee.is_active == True
    ).first()
    
    if not courier:
        raise HTTPException(status_code=404, detail="Курьер не найден или неактивен")
    
    # Приглашаем курьера
    ticket.courier_id = courier_id
    db.commit()
    
    # Отправляем уведомление клиенту о назначении курьера
    try:
        # Определяем кто назначает курьера для правильного отображения роли
        if current_user["type"] == "user":
            role_display = "Админ"
        else:
            employee = db.query(Employee).filter(Employee.login == current_user["username"]).first()
            if employee and employee.role == "operator":
                role_display = "Оператор"
            else:
                role_display = "Админ"
        
        notification_message = f"{role_display}:\n\n📦 К вашему тикету #{ticket_id} был назначен курьер для решения проблемы.\n\nКурьер свяжется с вами в ближайшее время."
        
        send_telegram_message(
            user_id=ticket.telegram_user_id,
            message=notification_message,
            db=db
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления клиенту о назначении курьера: {e}")
    
    return {
        "message": f"Курьер {courier.name} приглашен в тикет #{ticket_id}",
        "courier": {
            "id": courier.id,
            "name": courier.name
        }
    }

if __name__ == "__main__":
    create_tables()
    uvicorn.run(app, host="0.0.0.0", port=8000)