import pytest
from app import create_app, db
from app.models import User, CalendarEvent
from datetime import datetime, timedelta


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


@pytest.fixture
def calendar_event(app):
    """Создание тестового события календаря"""
    with app.app_context():
        event = CalendarEvent(
            event_id='test_event_123',
            title='Тестовое занятие',
            start_time=datetime.utcnow() + timedelta(days=1),
            end_time=datetime.utcnow() + timedelta(days=1, hours=2),
            description='Описание занятия'
        )
        db.session.add(event)
        db.session.commit()
        return event


def test_cached_events(client, user, calendar_event):
    """Тест получения кэшированных событий"""
    client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'testpass'
    })
    
    response = client.get('/calendar/events/cached')
    
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) > 0
    assert data[0]['title'] == 'Тестовое занятие'


def test_files_by_event(client, user, calendar_event, app):
    """Тест получения файлов по событию"""
    client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'testpass'
    })
    
    # Получаем ID события через новый запрос
    with app.app_context():
        from app.models import CalendarEvent
        event = CalendarEvent.query.first()
        event_id = event.id
        db.session.expunge_all()
    
    response = client.get(f'/upload/files/event/{event_id}')
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'event' in data
    assert 'files' in data
    assert data['event']['id'] == event_id

