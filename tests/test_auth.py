import pytest
from app import create_app, db
from app.models import User


@pytest.fixture
def app():
    """Создание тестового приложения"""
    app = create_app('development')
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Тестовый клиент"""
    return app.test_client()


@pytest.fixture
def user(app):
    """Создание тестового пользователя"""
    with app.app_context():
        user = User(
            username='testuser',
            is_active=True
        )
        user.set_full_name('Иванов Иван Иванович')
        user.set_password('testpass')
        db.session.add(user)
        db.session.commit()
        return user


def test_register(client):
    """Тест регистрации"""
    response = client.post('/auth/register', data={
        'username': 'newuser',
        'full_name': 'Петров Петр Петрович',
        'password': 'password123',
        'password2': 'password123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Проверка успешной регистрации (может быть на русском)
    data_lower = response.data.lower()
    assert 'успешн'.encode('utf-8') in data_lower or b'success' in data_lower


def test_login(client, user):
    """Тест входа"""
    response = client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'testpass'
    }, follow_redirects=True)
    
    assert response.status_code == 200


def test_login_invalid(client):
    """Тест входа с неверными данными"""
    response = client.post('/auth/login', data={
        'username': 'wronguser',
        'password': 'wrongpass'
    })
    
    assert response.status_code == 200
    data = response.data
    assert 'Неверное'.encode('utf-8') in data or b'invalid' in data.lower() or b'wrong' in data.lower()


def test_logout(client, user):
    """Тест выхода"""
    # Сначала входим
    client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'testpass'
    })
    
    # Затем выходим
    response = client.get('/auth/logout', follow_redirects=True)
    assert response.status_code == 200


def test_protected_route(client):
    """Тест защищённого маршрута"""
    response = client.get('/schedule', follow_redirects=True)
    data = response.data
    assert 'Вход'.encode('utf-8') in data or b'login' in data.lower()

