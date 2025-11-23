"""
Скрипт для создания таблиц базы данных и применения миграций

Использование:
    python setup_database.py
"""
import os
import sys

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from flask_migrate import upgrade, init, migrate

def setup_database():
    """Создание таблиц и применение миграций"""
    # Создаем приложение
    app = create_app(os.getenv('FLASK_ENV', 'production'))
    
    with app.app_context():
        try:
            # Проверяем, инициализированы ли миграции
            migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
            if not os.path.exists(migrations_dir) or not os.listdir(migrations_dir):
                print("Инициализация миграций...")
                init()
                print("Создание начальной миграции...")
                migrate(message="Initial migration")
            
            print("Применение миграций...")
            upgrade()
            print("✓ Миграции успешно применены!")
            
        except Exception as e:
            # Если миграции не работают, создаем таблицы напрямую
            print(f"Ошибка при применении миграций: {e}")
            print("Попытка создать таблицы напрямую...")
            try:
                db.create_all()
                print("✓ Таблицы успешно созданы!")
            except Exception as e2:
                print(f"✗ Ошибка при создании таблиц: {e2}")
                sys.exit(1)

if __name__ == '__main__':
    setup_database()

