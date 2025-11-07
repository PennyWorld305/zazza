import psycopg2
import os
from dotenv import load_dotenv

# Загрузим переменные окружения
load_dotenv()

# Получим параметры подключения из DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")  # postgresql://postgres:axe305@localhost:5432/zaza

# Извлечем параметры из URL
# postgresql://postgres:axe305@localhost:5432/zaza
from urllib.parse import urlparse
parsed = urlparse(DATABASE_URL)

conn_params = {
    'host': parsed.hostname,
    'port': parsed.port,
    'user': parsed.username,
    'password': parsed.password,
    'database': parsed.path[1:]  # убираем первый слэш
}

def migrate_database():
    """Добавляет новые поля в таблицу ticket_messages для PostgreSQL"""
    try:
        # Подключение к PostgreSQL
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        # Проверяем, существуют ли уже поля
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='ticket_messages' AND column_name IN ('sender_role', 'sender_name')
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        if 'sender_role' not in existing_columns:
            print("Добавляем поле sender_role...")
            cursor.execute("ALTER TABLE ticket_messages ADD COLUMN sender_role VARCHAR")
            print("✓ Поле sender_role добавлено")
        else:
            print("✓ Поле sender_role уже существует")
            
        if 'sender_name' not in existing_columns:
            print("Добавляем поле sender_name...")
            cursor.execute("ALTER TABLE ticket_messages ADD COLUMN sender_name VARCHAR")
            print("✓ Поле sender_name добавлено")
        else:
            print("✓ Поле sender_name уже существует")
        
        # Сохраняем изменения
        conn.commit()
        print("\n🎉 Миграция успешно завершена!")
        
        # Проверяем структуру таблицы
        cursor.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name='ticket_messages' 
            ORDER BY ordinal_position
        """)
        
        print("\nТекущая структура таблицы ticket_messages:")
        print("Поле\t\t\tТип\t\tNull?")
        print("-" * 50)
        for row in cursor.fetchall():
            print(f"{row[0]:<20}\t{row[1]:<15}\t{row[2]}")
        
    except psycopg2.Error as e:
        print(f"❌ Ошибка PostgreSQL: {e}")
    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("🔄 Запуск миграции PostgreSQL базы данных...")
    print(f"Подключение к: {conn_params['host']}:{conn_params['port']}/{conn_params['database']}")
    migrate_database()