from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import os
import hashlib
import bcrypt
from dotenv import load_dotenv
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

def verify_password(plain_password, hashed_password):
    """Проверка пароля с поддержкой bcrypt и резервным механизмом"""
    try:
        # Обрезаем пароль до 72 байт если нужно для bcrypt
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        
        # Проверяем bcrypt хеш
        if hashed_password.startswith('$2b$') or hashed_password.startswith('$2a$'):
            return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))
        else:
            # Для других типов хешей (если есть)
            return False
    except Exception as e:
        print(f"Ошибка проверки пароля: {e}")
        return False

def get_password_hash(password):
    """Создание bcrypt хеша пароля"""
    try:
        # Обрезаем пароль до 72 байт если нужно
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        
        # Создаем bcrypt хеш
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    except Exception as e:
        print(f"Ошибка создания хеша: {e}")
        return None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None

# Security scheme for FastAPI
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Dependency function для проверки JWT токена в заголовке Authorization
    """
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_type: str = payload.get("type", "user")
        user_id: int = payload.get("id")
        role: str = payload.get("role")
        
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        return {
            "username": username, 
            "type": user_type, 
            "id": user_id,
            "role": role
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")