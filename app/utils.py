import os
from werkzeug.utils import secure_filename
from flask import current_app


def allowed_file(filename):
    """Проверка разрешённого расширения файла"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def get_secure_filename(filename):
    """Получение безопасного имени файла"""
    return secure_filename(filename)

