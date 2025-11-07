#!/usr/bin/env python3
"""
Скрипт для создания тестового курьера
"""
import requests
import json

# Конфигурация
API_URL = "http://localhost:8000"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

def login_admin():
    """Логин администратора и получение токена"""
    login_data = {
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    }
    
    response = requests.post(f"{API_URL}/api/login", json=login_data)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Ошибка авторизации: {response.text}")

def create_courier(token):
    """Создание курьера"""
    courier_data = {
        "login": "courier1",
        "password": "courier123",
        "name": "Курьер Иванов",
        "role": "courier"
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(f"{API_URL}/api/employees", json=courier_data, headers=headers)
    if response.status_code == 200:
        print("✅ Курьер успешно создан!")
        print(f"Логин: {courier_data['login']}")
        print(f"Пароль: {courier_data['password']}")
        return response.json()
    else:
        print(f"❌ Ошибка создания курьера: {response.text}")
        return None

def main():
    try:
        print("🔐 Авторизация администратора...")
        token = login_admin()
        print("✅ Авторизация успешна!")
        
        print("👥 Создание курьера...")
        courier = create_courier(token)
        
        if courier:
            print("\n📋 Данные курьера:")
            print(json.dumps(courier, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()