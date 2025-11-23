from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User
from app.forms import LoginForm, RegistrationForm
from app.telegram_notify import send_notification_to_admins

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Ваш аккаунт не активирован. Ожидайте подтверждения администратором.', 'warning')
                return redirect(url_for('auth.login'))
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('main.index')
            return redirect(next_page)
        flash('Неверное имя пользователя или пароль.', 'danger')
    return render_template('login.html', title='Вход', form=form)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Страница регистрации"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            is_active=False  # Требует подтверждения админом
        )
        user.set_full_name(form.full_name.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        # Отправка уведомления администраторам
        try:
            message = (
                f"🔔 Новый пользователь зарегистрирован!\n\n"
                f"Имя пользователя: {user.username}\n"
                f"ФИО: {user.get_full_name()}\n\n"
                f"Используйте кнопки ниже для подтверждения или команду:\n"
                f"/approve {user.username}"
            )
            send_notification_to_admins(message, user.username)
        except Exception as e:
            print(f"Error sending notification to admins: {e}")
        
        flash('Регистрация успешна! Ожидайте подтверждения администратором.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html', title='Регистрация', form=form)


@bp.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('main.index'))

