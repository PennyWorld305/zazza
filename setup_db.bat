@echo off
echo 🗄️ Создание новой базы данных PostgreSQL с правильной кодировкой...

REM Останавливаем PostgreSQL
net stop postgresql-x64-16

REM Запускаем PostgreSQL
net start postgresql-x64-16

REM Ждем запуска
timeout /t 3 /nobreak >nul

REM Создаем новую базу данных
echo 📝 Создаем новую базу данных...
psql -U postgres -c "DROP DATABASE IF EXISTS zaza_telegram_bot_new;"
psql -U postgres -c "CREATE DATABASE zaza_telegram_bot_new WITH ENCODING 'UTF8' LC_COLLATE='C' LC_CTYPE='C';"

echo ✅ База данных создана!

REM Создаем таблицы
echo 📋 Создаем таблицы...
psql -U postgres -d zaza_telegram_bot_new -c "
CREATE TABLE IF NOT EXISTS telegram_bots (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    telegram_name VARCHAR(100),
    description TEXT,
    token TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(100),
    category VARCHAR(50) NOT NULL,
    message TEXT,
    status VARCHAR(20) DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"

REM Добавляем тестового бота
echo 🤖 Добавляем тестового бота...
psql -U postgres -d zaza_telegram_bot_new -c "
INSERT INTO telegram_bots (name, telegram_name, token, is_active) 
VALUES ('Сливки', '@slivki_bot', '8415573993:AAFvXu0JsrMQQZz4W7jWsCoHhh_ZmImgEHo', true);
"

echo ✅ Готово! Новая база данных настроена.
pause