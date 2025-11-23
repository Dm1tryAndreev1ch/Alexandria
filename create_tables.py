"""
Простой скрипт для создания всех таблиц базы данных

Использование:
    python create_tables.py
"""
import os
import sys

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
# Импортируем все модели для их регистрации
from app.models import User, QueueEntry, CalendarEvent, Task, File

def create_tables():
    """Создание всех таблиц в базе данных"""
    # Создаем приложение
    app = create_app(os.getenv('FLASK_ENV', 'production'))
    
    with app.app_context():
        try:
            print("Создание таблиц в базе данных...")
            db.create_all()
            print("✓ Все таблицы успешно созданы!")
            print("\nСозданные таблицы:")
            print("  - users")
            print("  - queue_entries")
            print("  - calendar_events")
            print("  - tasks")
            print("  - files")
            print("  - alembic_version")
        except Exception as e:
            print(f"✗ Ошибка при создании таблиц: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    create_tables()

