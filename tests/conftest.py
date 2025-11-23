"""
Общие фикстуры для всех тестов
"""
import os
import pytest
from app import create_app, db

# Устанавливаем SQLite для всех тестов перед загрузкой конфигурации
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

@pytest.fixture(scope='function')
def app():
    """Создание тестового приложения с SQLite в памяти"""
    # Убеждаемся, что используется SQLite
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    
    app = create_app('development')
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['ENCRYPTION_KEY'] = 'test-encryption-key-for-testing-only'
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()
        db.session.remove()


@pytest.fixture
def client(app):
    """Тестовый клиент"""
    return app.test_client()

