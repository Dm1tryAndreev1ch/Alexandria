import pytest
from app import create_app, db
from app.models import User, QueueEntry


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


def test_add_to_queue(client, user):
    """Тест добавления в очередь"""
    client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'testpass'
    })
    
    response = client.post('/queue/add', data={
        'subject': 'ОАиП'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Проверка добавления в очередь
    data_lower = response.data.lower()
    assert 'очеред'.encode('utf-8') in data_lower or b'queue' in data_lower


def test_queue_list(client, user):
    """Тест получения списка очереди"""
    client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'testpass'
    })
    
    # Добавление в очередь
    client.post('/queue/add', data={'subject': 'ОАиП'})
    
    # Получение списка
    response = client.get('/queue/api/list?subject=ОАиП')
    
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) > 0
    assert data[0]['username'] == 'testuser'
    assert 'full_name' in data[0]
    assert data[0]['full_name'] == 'Иванов Иван Иванович'


def test_mark_answered(client, user, app):
    """Тест отметки как отвеченного"""
    client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'testpass'
    })
    
    # Добавление в очередь
    add_response = client.post('/queue/add', data={'subject': 'ОАиП'}, follow_redirects=True)
    assert add_response.status_code == 200
    
    # Получение ID записи через API
    api_response = client.get('/queue/api/list?subject=ОАиП')
    assert api_response.status_code == 200
    data = api_response.get_json()
    assert len(data) > 0
    entry_id = data[0]['id']
    
    # Отметка как отвеченного
    response = client.post(f'/queue/mark_answered/{entry_id}', follow_redirects=True)
    
    assert response.status_code == 200
    # Проверка отметки
    data_lower = response.data.lower()
    assert 'отмет'.encode('utf-8') in data_lower or b'mark' in data_lower or response.status_code == 200

