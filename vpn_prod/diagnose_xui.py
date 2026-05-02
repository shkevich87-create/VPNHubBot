#!/usr/bin/env python3
"""
Скрипт для диагностики проблем с X-UI сервером
Проверяет доступность API и тестирует добавление клиента
"""

import requests
import json
import sys
from urllib3.exceptions import InsecureRequestWarning

# Отключаем предупреждение о самоподписанных сертификатах
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class XUIDiagnostics:
    def __init__(self, url, port, secret_path, username, password):
        self.base_url = f"http://{url}:{port}/{secret_path}"
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.verify = False
        self.token = None
        
    def test_connection(self):
        """Проверка базового подключения к серверу"""
        print("=" * 60)
        print("1️⃣  ПРОВЕРКА ПОДКЛЮЧЕНИЯ К СЕРВЕРУ")
        print("=" * 60)
        
        try:
            response = self.session.get(f"{self.base_url}/", timeout=5)
            print(f"✅ Сервер доступен (статус: {response.status_code})")
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False
    
    def test_login(self):
        """Проверка авторизации"""
        print("\n" + "=" * 60)
        print("2️⃣  ПРОВЕРКА АВТОРИЗАЦИИ")
        print("=" * 60)
        
        try:
            login_url = f"{self.base_url}/login"
            data = {
                "username": self.username,
                "password": self.password
            }
            
            response = self.session.post(login_url, json=data, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.token = result.get('data', {}).get('token')
                    if self.token:
                        self.session.headers.update({'Authorization': self.token})
                        print(f"✅ Успешная авторизация")
                        return True
                    else:
                        print(f"❌ Токен не получен: {result}")
                        return False
                else:
                    print(f"❌ Авторизация не удалась: {result}")
                    return False
            else:
                print(f"❌ Ошибка {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Исключение: {e}")
            return False
    
    def get_inbounds(self):
        """Получение списка inbound'ов"""
        print("\n" + "=" * 60)
        print("3️⃣  ПОЛУЧЕНИЕ СПИСКА INBOUND'ОВ")
        print("=" * 60)
        
        try:
            inbounds_url = f"{self.base_url}/api/inbounds/list"
            response = self.session.get(inbounds_url, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    inbounds = result.get('obj', [])
                    print(f"✅ Найдено inbound'ов: {len(inbounds)}")
                    for inbound in inbounds:
                        print(f"\n   ID: {inbound.get('id')}, Protocol: {inbound.get('protocol')}")
                    return inbounds
                else:
                    print(f"❌ Ошибка: {result}")
                    return []
            else:
                print(f"❌ Ошибка {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Исключение: {e}")
            return []
    
    def test_add_client(self, inbound_id):
        """Тестирование добавления клиента"""
        print(f"\n📌 Тест inbound ID: {inbound_id}")
        
        try:
            add_client_url = f"{self.base_url}/api/inbounds/addClient"
            
            test_client = {
                "id": "test-uuid-12345",
                "email": "test@example.com",
                "enable": True,
                "flow": "",
                "tg_id": "test_user",
                "total_gb": 0,
                "expiry_time": 9999999999000,
                "limit_ip": 0,
                "reset": 0
            }
            
            data = {
                "inbound_id": inbound_id,
                "clients": [test_client]
            }
            
            response = self.session.post(add_client_url, json=data, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print(f"✅ Клиент добавлен успешно")
                    return True
                else:
                    print(f"❌ Ошибка: {result}")
                    return False
            else:
                print(f"❌ Ошибка {response.status_code}: {response.text[:100]}")
                return False
                
        except Exception as e:
            print(f"❌ Исключение: {e}")
            return False
    
    def run_diagnostics(self):
        """Запуск диагностики"""
        print("\n╔" + "=" * 58 + "╗")
        print("║" + "X-UI DIAGNOSTICS".center(58) + "║")
        print("╚" + "=" * 58 + "╝")
        
        if not self.test_connection():
            return
        
        if not self.test_login():
            return
        
        inbounds = self.get_inbounds()
        if not inbounds:
            return
        
        print("\n" + "=" * 60)
        print("4️⃣  ТЕСТИРОВАНИЕ ДОБАВЛЕНИЯ КЛИЕНТА")
        print("=" * 60)
        
        for inbound in inbounds:
            self.test_add_client(inbound.get('id'))
        
        print("\n" + "=" * 60)
        print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
        print("=" * 60)

if __name__ == "__main__":
    print("\n🔧 Диагностика X-UI\n")
    
    url = input("IP адрес (например 38.244.194.128): ").strip()
    port = input("Порт (например 2456): ").strip()
    path = input("Secret path (например 8cbKRDfZN0t2BBcmK2): ").strip()
    user = input("Логин (обычно admin): ").strip()
    pwd = input("Пароль: ").strip()
    
    diag = XUIDiagnostics(url, port, path, user, pwd)
    diag.run_diagnostics()
