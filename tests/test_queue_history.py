"""Тесты для очереди с датами для истории"""
import os
import pytest
from datetime import datetime, date, timedelta
from app import create_app, db
from app.models import User, QueueEntry, CalendarEvent

# Устанавливаем SQLite для тестов
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'


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
def history_event(app):
    """Создание тестового события по истории"""
    with app.app_context():
        event_date = datetime.utcnow() + timedelta(days=7)
        event = CalendarEvent(
            event_id='history_event_123',
            title='История Беларуси (ПЗ)',  # Добавляем (ПЗ) для распознавания как истории
            start_time=event_date,
            end_time=event_date + timedelta(hours=2),
            description='Занятие по истории',
            location='Аудитория 101'
        )
        db.session.add(event)
        db.session.commit()
        return event


def test_history_queue_requires_date(client, user, app, history_event):
    """Тест: очередь по истории требует дату"""
    with app.app_context():
        client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'testpass'
        })
        
        # Попытка добавиться без даты
        response = client.post('/queue/add', data={
            'subject': 'История'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        data_lower = response.data.lower()
        assert 'дату'.encode('utf-8') in data_lower or 'дата'.encode('utf-8') in data_lower


def test_history_queue_with_valid_date(client, user, app, history_event):
    """Тест: добавление в очередь по истории с валидной датой"""
    with app.app_context():
        client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'testpass'
        })
        
        # Получаем событие из БД в контексте
        event = CalendarEvent.query.filter_by(event_id='history_event_123').first()
        event_date = event.start_time.date()
        
        response = client.post('/queue/add', data={
            'subject': 'История',
            'event_date': event_date.strftime('%Y-%m-%d')
        }, follow_redirects=True)
        
        assert response.status_code == 200
        data_lower = response.data.lower()
        assert 'добавлен'.encode('utf-8') in data_lower or 'успешн'.encode('utf-8') in data_lower
        
        # Проверяем, что запись создана с датой
        user_from_db = User.query.filter_by(username='testuser').first()
        entry = QueueEntry.query.filter_by(
            user_id=user_from_db.id,
            subject='История'
        ).first()
        assert entry is not None
        assert entry.event_date == event_date


def test_history_queue_with_invalid_date(client, user, app, history_event):
    """Тест: попытка добавиться на дату без истории"""
    with app.app_context():
        client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'testpass'
        })
        
        # Дата без истории (завтра)
        invalid_date = (datetime.utcnow() + timedelta(days=1)).date()
        response = client.post('/queue/add', data={
            'subject': 'История',
            'event_date': invalid_date.strftime('%Y-%m-%d')
        }, follow_redirects=True)
        
        assert response.status_code == 200
        data_lower = response.data.lower()
        assert 'нет занятий'.encode('utf-8') in data_lower or 'не найдено'.encode('utf-8') in data_lower


def test_oaip_queue_no_date_required(client, user, app):
    """Тест: очередь по ОАиП не требует дату"""
    with app.app_context():
        client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'testpass'
        })
        
        response = client.post('/queue/add', data={
            'subject': 'ОАиП'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        data_lower = response.data.lower()
        assert 'добавлен'.encode('utf-8') in data_lower or 'успешн'.encode('utf-8') in data_lower
        
        # Проверяем, что запись создана без даты
        user_from_db = User.query.filter_by(username='testuser').first()
        entry = QueueEntry.query.filter_by(
            user_id=user_from_db.id,
            subject='ОАиП'
        ).first()
        assert entry is not None
        assert entry.event_date is None


def test_history_queue_multiple_dates(client, user, app):
    """Тест: пользователь может быть в очереди на разные даты"""
    with app.app_context():
        client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'testpass'
        })
        
        # Создаем два события по истории на разные даты
        date1 = datetime.utcnow() + timedelta(days=7)
        date2 = datetime.utcnow() + timedelta(days=14)
        
        event1 = CalendarEvent(
            event_id='history_event_1',
            title='История Беларуси (ПЗ)',  # Добавляем (ПЗ) для распознавания
            start_time=date1,
            end_time=date1 + timedelta(hours=2)
        )
        event2 = CalendarEvent(
            event_id='history_event_2',
            title='История Беларуси (ПЗ)',  # Добавляем (ПЗ) для распознавания
            start_time=date2,
            end_time=date2 + timedelta(hours=2)
        )
        db.session.add(event1)
        db.session.add(event2)
        db.session.commit()
        
        # Добавляемся на первую дату
        response1 = client.post('/queue/add', data={
            'subject': 'История',
            'event_date': date1.date().strftime('%Y-%m-%d')
        }, follow_redirects=True)
        assert response1.status_code == 200
        
        # Добавляемся на вторую дату
        response2 = client.post('/queue/add', data={
            'subject': 'История',
            'event_date': date2.date().strftime('%Y-%m-%d')
        }, follow_redirects=True)
        assert response2.status_code == 200
        
        # Проверяем, что обе записи созданы
        user_from_db = User.query.filter_by(username='testuser').first()
        entries = QueueEntry.query.filter_by(
            user_id=user_from_db.id,
            subject='История',
            has_answered=False
        ).all()
        assert len(entries) == 2


def test_get_history_dates(app, history_event):
    """Тест функции получения дат с историей"""
    from app.queue_routes import get_history_dates
    
    with app.app_context():
        dates = get_history_dates()
        # Получаем событие из БД в контексте
        event = CalendarEvent.query.filter_by(event_id='history_event_123').first()
        event_date = event.start_time.date()
        assert event_date in dates
        assert len(dates) > 0

