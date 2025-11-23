"""Маршруты для администратора"""
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import User, QueueEntry, Task, File

bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """Декоратор для проверки прав администратора"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('У вас нет прав для доступа к этой странице.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@admin_required
def index():
    """Главная страница админ-панели"""
    return redirect(url_for('admin.users'))


@bp.route('/users')
@admin_required
def users():
    """Список всех пользователей"""
    users_list = User.query.order_by(User.created_at.desc()).all()
    
    # Подсчет статистики для каждого пользователя
    users_data = []
    for user in users_list:
        queue_count = QueueEntry.query.filter_by(user_id=user.id, has_answered=False).count()
        tasks_count = Task.query.filter_by(user_id=user.id, completed=False).count()
        files_count = File.query.filter_by(user_id=user.id).count()
        
        users_data.append({
            'user': user,
            'queue_count': queue_count,
            'tasks_count': tasks_count,
            'files_count': files_count
        })
    
    return render_template('admin/users.html', title='Управление пользователями', users_data=users_data)


@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Удаление пользователя"""
    user = User.query.get_or_404(user_id)
    
    # Нельзя удалить самого себя
    if user.id == current_user.id:
        flash('Вы не можете удалить свой собственный аккаунт.', 'danger')
        return redirect(url_for('admin.users'))
    
    # Нельзя удалить последнего администратора
    admin_count = User.query.filter_by(is_admin=True).count()
    if user.is_admin and admin_count <= 1:
        flash('Нельзя удалить последнего администратора.', 'danger')
        return redirect(url_for('admin.users'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'Пользователь {username} успешно удален.', 'success')
    return redirect(url_for('admin.users'))


@bp.route('/users/<int:user_id>/toggle_active', methods=['POST'])
@admin_required
def toggle_active(user_id):
    """Активация/деактивация пользователя"""
    user = User.query.get_or_404(user_id)
    
    # Нельзя деактивировать самого себя
    if user.id == current_user.id:
        flash('Вы не можете деактивировать свой собственный аккаунт.', 'danger')
        return redirect(url_for('admin.users'))
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'активирован' if user.is_active else 'деактивирован'
    flash(f'Пользователь {user.username} {status}.', 'success')
    return redirect(url_for('admin.users'))


@bp.route('/users/<int:user_id>/toggle_admin', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    """Назначение/снятие прав администратора"""
    user = User.query.get_or_404(user_id)
    
    # Нельзя снять права администратора у самого себя
    if user.id == current_user.id:
        flash('Вы не можете снять права администратора у самого себя.', 'danger')
        return redirect(url_for('admin.users'))
    
    # Нельзя снять права у последнего администратора
    admin_count = User.query.filter_by(is_admin=True).count()
    if user.is_admin and admin_count <= 1:
        flash('Нельзя снять права у последнего администратора.', 'danger')
        return redirect(url_for('admin.users'))
    
    user.is_admin = not user.is_admin
    db.session.commit()
    
    status = 'назначен администратором' if user.is_admin else 'лишен прав администратора'
    flash(f'Пользователь {user.username} {status}.', 'success')
    return redirect(url_for('admin.users'))


@bp.route('/users/<int:user_id>/reset_password', methods=['POST'])
@admin_required
def reset_password(user_id):
    """Сброс пароля пользователя (установка временного пароля)"""
    user = User.query.get_or_404(user_id)
    
    # Генерируем временный пароль
    import secrets
    import string
    temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    
    user.set_password(temp_password)
    db.session.commit()
    
    flash(f'Пароль для пользователя {user.username} сброшен. Новый временный пароль: {temp_password}', 'info')
    return redirect(url_for('admin.users'))

