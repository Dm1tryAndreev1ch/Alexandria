"""
WSGI entry point - совместимость со старым passenger_wsgi.py

Этот файл создан для работы со старым passenger_wsgi.py, который использует:
    wsgi = load_source('wsgi', 'wsgi.py')
    application = wsgi.wsgi.py

Этот файл импортирует application из main.py и создает структуру wsgi.wsgi.py
"""
import os
import sys

# Добавляем текущую директорию в путь
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Импортируем application из main.py
from main import application

# Создаем структуру для совместимости со старым passenger_wsgi.py
# Старый код использует: application = wsgi.wsgi.py
class WsgiModule:
    """Обертка для совместимости со старым passenger_wsgi.py"""
    def __init__(self):
        self.py = application

# Создаем объект wsgi с атрибутом wsgi, который содержит объект с атрибутом py
wsgi = WsgiModule()
wsgi.wsgi = WsgiModule()  # wsgi.wsgi.py будет доступен

# Также экспортируем application напрямую для стандартного использования
__all__ = ['application', 'wsgi']

