import psycopg2
from urllib.parse import urlparse
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
parsed = urlparse(DATABASE_URL)

conn_params = {
    'host': parsed.hostname,
    'port': parsed.port,
    'user': parsed.username,
    'password': parsed.password,
    'database': parsed.path[1:]
}

try:
    conn = psycopg2.connect(**conn_params)
    cursor = conn.cursor()
    
    print("🔍 Проверка сотрудников в БД...")
    cursor.execute('SELECT id, login, hashed_password FROM employees LIMIT 5')
    rows = cursor.fetchall()
    
    print(f"Найдено сотрудников: {len(rows)}")
    for row in rows:
        hash_preview = row[2][:50] + "..." if row[2] and len(row[2]) > 50 else row[2]
        hash_type = "bcrypt" if row[2] and row[2].startswith("$2b$") else "other/unknown"
        print(f"ID: {row[0]}, Login: {row[1]}, Hash type: {hash_type}")
        print(f"  Hash preview: {hash_preview}")
        print()
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Ошибка: {e}")