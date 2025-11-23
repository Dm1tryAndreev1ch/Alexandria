"""Тесты для модуля шифрования"""
import pytest
from app import create_app
from app.encryption import encrypt_data, decrypt_data


@pytest.fixture
def app():
    """Создание тестового приложения"""
    app = create_app('development')
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key-for-encryption'
    
    with app.app_context():
        yield app


def test_encrypt_decrypt(app):
    """Тест шифрования и расшифровки данных"""
    with app.app_context():
        original = "Иванов Иван Иванович"
        encrypted = encrypt_data(original)
        decrypted = decrypt_data(encrypted)
        
        assert encrypted != original
        assert decrypted == original
        assert len(encrypted) > 0


def test_encrypt_empty_string(app):
    """Тест шифрования пустой строки"""
    with app.app_context():
        encrypted = encrypt_data("")
        decrypted = decrypt_data(encrypted)
        
        assert encrypted == ""
        assert decrypted == ""


def test_encrypt_cyrillic(app):
    """Тест шифрования кириллицы"""
    with app.app_context():
        test_cases = [
            "Петров Петр Петрович",
            "Сидоров Сидор Сидорович",
            "Тест Тестович"
        ]
        
        for original in test_cases:
            encrypted = encrypt_data(original)
            decrypted = decrypt_data(encrypted)
            assert decrypted == original


def test_user_full_name_encryption(app):
    """Тест шифрования ФИО пользователя"""
    from app.models import User, db
    
    with app.app_context():
        db.create_all()
        
        user = User(username='testuser', is_active=True)
        user.set_full_name('Иванов Иван Иванович')
        user.set_password('testpass')
        
        # Проверяем, что ФИО зашифровано
        assert user.full_name_encrypted != 'Иванов Иван Иванович'
        assert len(user.full_name_encrypted) > 0
        
        # Проверяем, что можем получить расшифрованное ФИО
        assert user.get_full_name() == 'Иванов Иван Иванович'
        assert user.full_name == 'Иванов Иван Иванович'
        
        db.session.add(user)
        db.session.commit()
        
        # Проверяем после сохранения в БД
        user_from_db = User.query.filter_by(username='testuser').first()
        assert user_from_db.get_full_name() == 'Иванов Иван Иванович'
        
        db.drop_all()

