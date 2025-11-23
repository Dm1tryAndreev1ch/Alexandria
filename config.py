import os
from dotenv import load_dotenv

# Загружаем .env файл с обработкой ошибок кодировки
# BOM (Byte Order Mark) символы будут автоматически обработаны
try:
    load_dotenv(encoding='utf-8-sig')  # utf-8-sig автоматически удаляет BOM
except Exception:
    # Если utf-8-sig не поддерживается, пробуем обычный utf-8
    try:
        load_dotenv(encoding='utf-8')
    except Exception:
        # В крайнем случае пробуем без указания кодировки
        load_dotenv()


class Config:
    """Базовая конфигурация приложения"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Ключ шифрования для персональных данных (ФИО)
    # Если не указан, будет автоматически сгенерирован из SECRET_KEY в encryption.py
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///bsuir_diary.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Google Calendar
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID') or \
        '7101b214c03700a0d4044eda7f8082c3fda8d10e80cf66f718274c85b88c375a@group.calendar.google.com'
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    # Admin
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME')
    
    # Upload settings
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt', 'zip'}


class DevelopmentConfig(Config):
    """Конфигурация для разработки"""
    DEBUG = True


class ProductionConfig(Config):
    """Конфигурация для продакшена"""
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

