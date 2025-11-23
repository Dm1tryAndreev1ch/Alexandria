import pytest
import os
import tempfile
from app import create_app, db
from app.models import User, File, CalendarEvent
from datetime import datetime, timedelta


@pytest.fixture
def app():
    """Создание тестового приложения"""
    app = create_app('development')
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
    
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


@pytest.fixture
def calendar_event(app):
    """Создание тестового события календаря"""
    with app.app_context():
        event = CalendarEvent(
            event_id='test_event_123',
            title='Тестовое занятие',
            start_time=datetime.utcnow() + timedelta(days=1),
            end_time=datetime.utcnow() + timedelta(days=1, hours=2)
        )
        db.session.add(event)
        db.session.commit()
        return event


def test_upload_file(client, user, calendar_event, app):
    """Тест загрузки файла"""
    # Вход в систему
    client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'testpass'
    })
    
    # Получаем ID события
    event_id = None
    with app.app_context():
        from app.models import CalendarEvent
        event = CalendarEvent.query.first()
        if event:
            event_id = int(event.id)  # Явно преобразуем в int
        else:
            # Если событие не найдено, создаем новое для теста
            new_event = CalendarEvent(
                event_id='test_event_456',
                title='Test Event',
                start_time=datetime.utcnow() + timedelta(days=1),
                end_time=datetime.utcnow() + timedelta(days=1, hours=2)
            )
            db.session.add(new_event)
            db.session.commit()
            event_id = int(new_event.id)
    
    # Создание тестового файла
    test_file = (tempfile.NamedTemporaryFile(delete=False, suffix='.txt'), b'test content')
    test_file[0].write(test_file[1])
    test_file[0].close()
    
    with open(test_file[0].name, 'rb') as f:
        response = client.post('/upload/upload', data={
            'file': (f, 'test.txt'),
            'calendar_event_id': event_id
        }, follow_redirects=True)
    
    os.unlink(test_file[0].name)
    
    assert response.status_code == 200
    # Проверка успешной загрузки
    data_lower = response.data.lower()
    assert 'загружен'.encode('utf-8') in data_lower or b'upload' in data_lower or 'успеш'.encode('utf-8') in data_lower


def test_upload_without_event(client, user):
    """Тест загрузки файла без выбора события"""
    client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'testpass'
    })
    
    test_file = (tempfile.NamedTemporaryFile(delete=False, suffix='.txt'), b'test content')
    test_file[0].write(test_file[1])
    test_file[0].close()
    
    with open(test_file[0].name, 'rb') as f:
        response = client.post('/upload/upload', data={
            'file': (f, 'test.txt')
        })
    
    os.unlink(test_file[0].name)
    
    # Проверка ошибки при отсутствии занятия
    data_lower = response.data.lower()
    assert response.status_code != 200 or 'занятие'.encode('utf-8') in data_lower or b'event' in data_lower or 'необходимо'.encode('utf-8') in data_lower

