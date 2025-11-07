import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Получаем параметры подключения из .env
DATABASE_URL = os.getenv("DATABASE_URL")

def run_migration():
    try:
        # Парсим DATABASE_URL для psycopg2
        if DATABASE_URL.startswith("postgresql://"):
            url = DATABASE_URL.replace("postgresql://", "")
        else:
            url = DATABASE_URL.replace("postgres://", "")
        
        # Разбираем URL: user:password@host:port/database
        auth_part, host_part = url.split("@")
        user, password = auth_part.split(":")
        host_db = host_part.split("/")
        host_port = host_db[0]
        database = host_db[1]
        
        if ":" in host_port:
            host, port = host_port.split(":")
        else:
            host = host_port
            port = "5432"
        
        # Подключаемся к базе
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        cursor = conn.cursor()
        
        print("🔧 Начинаем миграцию базы данных...")
        
        # 1. Добавляем поле hashed_password и is_active в employees
        print("📝 Обновляем таблицу employees...")
        try:
            cursor.execute("ALTER TABLE employees ADD COLUMN hashed_password VARCHAR;")
            print("✅ Добавлено поле hashed_password")
        except psycopg2.errors.DuplicateColumn:
            print("ℹ️ Поле hashed_password уже существует")
        
        try:
            cursor.execute("ALTER TABLE employees ADD COLUMN is_active BOOLEAN DEFAULT true;")
            print("✅ Добавлено поле is_active")
        except psycopg2.errors.DuplicateColumn:
            print("ℹ️ Поле is_active уже существует")
        
        # 2. Добавляем courier_id в active_tickets
        print("📝 Обновляем таблицу active_tickets...")
        try:
            cursor.execute("ALTER TABLE active_tickets ADD COLUMN courier_id INTEGER REFERENCES employees(id);")
            print("✅ Добавлено поле courier_id в active_tickets")
        except psycopg2.errors.DuplicateColumn:
            print("ℹ️ Поле courier_id в active_tickets уже существует")
        
        # 3. Добавляем courier_id в archive_tickets
        print("📝 Обновляем таблицу archive_tickets...")
        try:
            cursor.execute("ALTER TABLE archive_tickets ADD COLUMN courier_id INTEGER REFERENCES employees(id);")
            print("✅ Добавлено поле courier_id в archive_tickets")
        except psycopg2.errors.DuplicateColumn:
            print("ℹ️ Поле courier_id в archive_tickets уже существует")
        
        # 4. Очищаем тестовых сотрудников (кроме админа)
        print("🧹 Удаляем тестовых сотрудников...")
        cursor.execute("SELECT id, login, name, role FROM employees;")
        employees = cursor.fetchall()
        print(f"Найдено сотрудников: {len(employees)}")
        
        for emp in employees:
            emp_id, login, name, role = emp
            print(f"  - {emp_id}: {login} ({name}) - {role}")
        
        # Удаляем всех сотрудников кроме админа
        cursor.execute("DELETE FROM employees WHERE role != 'admin' OR role IS NULL;")
        deleted_count = cursor.rowcount
        print(f"🗑️ Удалено {deleted_count} тестовых сотрудников")
        
        # 5. Обновляем роль админа если нужно
        cursor.execute("UPDATE employees SET role = 'admin' WHERE role IS NULL OR role = '';")
        updated_count = cursor.rowcount
        if updated_count > 0:
            print(f"📋 Обновлено ролей админа: {updated_count}")
        
        # Сохраняем изменения
        conn.commit()
        print("✅ Миграция завершена успешно!")
        
        # Показываем итоговое состояние
        cursor.execute("SELECT id, login, name, role FROM employees;")
        final_employees = cursor.fetchall()
        print(f"\n📊 Итоговое состояние сотрудников ({len(final_employees)}):")
        for emp in final_employees:
            emp_id, login, name, role = emp
            print(f"  - {emp_id}: {login} ({name}) - {role}")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    run_migration()