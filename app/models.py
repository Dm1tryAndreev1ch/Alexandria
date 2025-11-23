from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    full_name_encrypted = db.Column(db.Text, nullable=False)  # Зашифрованное ФИО
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    telegram_id = db.Column(db.String(50), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    queue_entries = db.relationship('QueueEntry', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    files = db.relationship('File', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Установка пароля"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Проверка пароля"""
        return check_password_hash(self.password_hash, password)
    
    def set_full_name(self, full_name: str):
        """Установка ФИО с шифрованием"""
        from app.encryption import encrypt_data
        self.full_name_encrypted = encrypt_data(full_name)
    
    def get_full_name(self) -> str:
        """Получение расшифрованного ФИО"""
        from app.encryption import decrypt_data
        return decrypt_data(self.full_name_encrypted)
    
    @property
    def full_name(self) -> str:
        """Свойство для получения ФИО"""
        return self.get_full_name()
    
    def __repr__(self):
        return f'<User {self.username}>'


class CalendarEvent(db.Model):
    """Модель события календаря (кэш событий Google Calendar)"""
    __tablename__ = 'calendar_events'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(255), unique=True, nullable=False, index=True)  # ID из Google Calendar
    title = db.Column(db.String(255), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, index=True)
    end_time = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    files = db.relationship('File', backref='calendar_event', lazy='dynamic')
    
    def __repr__(self):
        return f'<CalendarEvent {self.title}>'


class QueueEntry(db.Model):
    """Модель записи в очереди ответов"""
    __tablename__ = 'queue_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(50), nullable=False)  # ОАиП или История
    event_date = db.Column(db.Date, nullable=True)  # Дата занятия (для истории обязательна)
    calendar_event_id = db.Column(db.Integer, db.ForeignKey('calendar_events.id'), nullable=True)  # Связь с событием календаря
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    has_answered = db.Column(db.Boolean, default=False, nullable=False)
    
    # Связь с событием календаря
    calendar_event = db.relationship('CalendarEvent', backref='queue_entries')
    
    __table_args__ = (db.Index('idx_user_subject', 'user_id', 'subject'),)
    
    def __repr__(self):
        return f'<QueueEntry {self.user_id} - {self.subject}>'


class Task(db.Model):
    """Модель задачи (To-Do)"""
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True, index=True)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Task {self.title}>'


class File(db.Model):
    """Модель загруженного файла"""
    __tablename__ = 'files'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    calendar_event_id = db.Column(db.Integer, db.ForeignKey('calendar_events.id'), nullable=True)
    filename = db.Column(db.String(255), nullable=False)  # Имя файла на диске
    original_filename = db.Column(db.String(255), nullable=False)  # Оригинальное имя
    file_type = db.Column(db.String(50), nullable=False)  # image, document, etc.
    upload_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    file_size = db.Column(db.Integer, nullable=True)  # Размер в байтах
    
    def __repr__(self):
        return f'<File {self.original_filename}>'
