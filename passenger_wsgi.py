"""
WSGI entry point for Passenger (production server)

This file is used by Passenger to serve the Flask application.
Passenger looks for a variable named 'application' in this file.
"""
import os
import sys
import locale

# Устанавливаем UTF-8 кодировку для работы с переменными окружения
# Это решает проблему с UnicodeEncodeError при чтении .env файла
if sys.platform != 'win32':
    # Для Linux/Unix систем
    os.environ.setdefault('LC_ALL', 'en_US.UTF-8')
    os.environ.setdefault('LANG', 'en_US.UTF-8')
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
        except locale.Error:
            pass

# Устанавливаем UTF-8 для стандартных потоков
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

# Добавляем текущую директорию в путь Python
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Импортируем приложение из main.py
# В main.py уже определена переменная 'application = app'
try:
    from main import application
except Exception as e:
    # Выводим ошибку для отладки
    import traceback
    error_msg = f"Error importing application: {e}\n{traceback.format_exc()}"
    try:
        sys.stderr.write(error_msg)
    except:
        print(error_msg)
    raise

# Passenger ищет переменную 'application'
__all__ = ['application']
