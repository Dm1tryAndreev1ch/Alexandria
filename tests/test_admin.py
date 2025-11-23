"""Тесты для админ-панели"""
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
def admin_user(app):
    """Создание администратора"""
    with app.app_context():
        admin = User(
            username='admin',
            is_active=True,
            is_admin=True
        )
        admin.set_full_name('Администратор Админ Админович')
        admin.set_password('adminpass')
        db.session.add(admin)
        db.session.commit()
        return admin


@pytest.fixture
def regular_user(app):
    """Создание обычного пользователя"""
    with app.app_context():
        user = User(
            username='user1',
            is_active=True,
            is_admin=False
        )
        user.set_full_name('Пользователь Пользователь Пользователевич')
        user.set_password('userpass')
        db.session.add(user)
        db.session.commit()
        return user


def test_admin_users_page_access_denied(client, regular_user):
    """Тест: обычный пользователь не может получить доступ к админ-панели"""
    client.post('/auth/login', data={
        'username': 'user1',
        'password': 'userpass'
    })
    
    response = client.get('/admin/users', follow_redirects=True)
    assert response.status_code == 200
    data_lower = response.data.lower()
    assert 'нет прав'.encode('utf-8') in data_lower or 'доступ'.encode('utf-8') in data_lower


def test_admin_users_page_access_granted(client, admin_user):
    """Тест: администратор может получить доступ к админ-панели"""
    client.post('/auth/login', data={
        'username': 'admin',
        'password': 'adminpass'
    })
    
    response = client.get('/admin/users')
    assert response.status_code == 200
    data_lower = response.data.lower()
    assert 'пользовател'.encode('utf-8') in data_lower or 'управление'.encode('utf-8') in data_lower


def test_admin_delete_user(client, admin_user, regular_user, app):
    """Тест: администратор может удалить пользователя"""
    client.post('/auth/login', data={
        'username': 'admin',
        'password': 'adminpass'
    })
    
    with app.app_context():
        user_id = User.query.filter_by(username='user1').first().id
    
    response = client.post(f'/admin/users/{user_id}/delete', follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        deleted_user = User.query.filter_by(username='user1').first()
        assert deleted_user is None


def test_admin_cannot_delete_self(client, admin_user, app):
    """Тест: администратор не может удалить самого себя"""
    client.post('/auth/login', data={
        'username': 'admin',
        'password': 'adminpass'
    })
    
    with app.app_context():
        admin_id = User.query.filter_by(username='admin').first().id
    
    response = client.post(f'/admin/users/{admin_id}/delete', follow_redirects=True)
    assert response.status_code == 200
    data_lower = response.data.lower()
    assert 'не можете удалить'.encode('utf-8') in data_lower or 'собственный'.encode('utf-8') in data_lower


def test_admin_toggle_active(client, admin_user, regular_user, app):
    """Тест: администратор может активировать/деактивировать пользователя"""
    client.post('/auth/login', data={
        'username': 'admin',
        'password': 'adminpass'
    })
    
    with app.app_context():
        user_id = User.query.filter_by(username='user1').first().id
    
    # Деактивируем пользователя
    response = client.post(f'/admin/users/{user_id}/toggle_active', follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        user = User.query.filter_by(username='user1').first()
        assert user.is_active == False
    
    # Активируем обратно
    response = client.post(f'/admin/users/{user_id}/toggle_active', follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        user = User.query.filter_by(username='user1').first()
        assert user.is_active == True


def test_admin_toggle_admin(client, admin_user, regular_user, app):
    """Тест: администратор может назначить/снять права администратора"""
    client.post('/auth/login', data={
        'username': 'admin',
        'password': 'adminpass'
    })
    
    with app.app_context():
        user_id = User.query.filter_by(username='user1').first().id
    
    # Назначаем администратором
    response = client.post(f'/admin/users/{user_id}/toggle_admin', follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        user = User.query.filter_by(username='user1').first()
        assert user.is_admin == True
    
    # Снимаем права
    response = client.post(f'/admin/users/{user_id}/toggle_admin', follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        user = User.query.filter_by(username='user1').first()
        assert user.is_admin == False


def test_admin_reset_password(client, admin_user, regular_user, app):
    """Тест: администратор может сбросить пароль пользователя"""
    client.post('/auth/login', data={
        'username': 'admin',
        'password': 'adminpass'
    })
    
    with app.app_context():
        user_id = User.query.filter_by(username='user1').first().id
    
    response = client.post(f'/admin/users/{user_id}/reset_password', follow_redirects=True)
    assert response.status_code == 200
    data_lower = response.data.lower()
    assert 'сброшен'.encode('utf-8') in data_lower or 'пароль'.encode('utf-8') in data_lower


def test_admin_users_list_shows_all_users(client, admin_user, regular_user, app):
    """Тест: список пользователей показывает всех пользователей"""
    client.post('/auth/login', data={
        'username': 'admin',
        'password': 'adminpass'
    })
    
    response = client.get('/admin/users')
    assert response.status_code == 200
    data = response.data.decode('utf-8')
    assert 'admin' in data
    assert 'user1' in data

