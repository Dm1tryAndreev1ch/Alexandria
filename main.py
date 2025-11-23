import os
import threading
from app import create_app, db
from app.models import User

app = create_app(os.getenv('FLASK_ENV', 'development'))


def setup_admin():
    """Настройка первого администратора"""
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    with app.app_context():
        # Создание первого администратора, если указан ADMIN_USERNAME
        admin_username = app.config.get('ADMIN_USERNAME')
        if admin_username:
            # Убираем @ если есть
            admin_username = admin_username.lstrip('@')
            admin = User.query.filter_by(username=admin_username).first()
            if admin:
                admin.is_admin = True
                admin.is_active = True
                db.session.commit()
                print(f"User {admin_username} assigned as administrator")
            else:
                print(f"User {admin_username} not found. Create it through registration.")


def start_telegram_bot():
    """Запуск Telegram бота в отдельном потоке"""
    token = app.config.get('TELEGRAM_BOT_TOKEN')
    if not token:
        print("TELEGRAM_BOT_TOKEN not set. Telegram bot will not start.")
        print("Please check .env file and ensure TELEGRAM_BOT_TOKEN is set.")
        return
    
    try:
        import os
        import sys
        # Устанавливаем UTF-8 для вывода
        if sys.platform == 'win32':
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except:
                pass
        
        # Устанавливаем переменную окружения для бота
        os.environ['TELEGRAM_BOT_TOKEN'] = token
        print(f"TELEGRAM_BOT_TOKEN set: {token[:10]}...")
        
        from telegram_bot.bot import init_bot, run_bot_polling_sync
        
        print("Initializing Telegram bot...")
        # Передаем токен напрямую, чтобы избежать проблем с загрузкой .env
        bot_app = init_bot(token=token)
        
        if not bot_app:
            print("Failed to initialize Telegram bot.")
            return
        
        print("Starting Telegram bot in background thread...")
        
        # Запускаем бота в отдельном потоке
        # run_polling создает свой event loop, поэтому просто запускаем его в потоке
        bot_thread = threading.Thread(target=run_bot_polling_sync, daemon=True, name="TelegramBot")
        bot_thread.start()
        
        # Даем боту немного времени на инициализацию
        import time
        time.sleep(3)
        
        # Проверяем, что поток запущен
        if bot_thread.is_alive():
            print("Telegram bot started successfully in background mode.")
        else:
            print("WARNING: Telegram bot thread may have failed to start.")
    except Exception as e:
        print(f"Error starting Telegram bot: {e}")
        import traceback
        traceback.print_exc()


def update_calendar_periodically():
    """Периодическое обновление календаря в фоне"""
    import time
    while True:
        try:
            time.sleep(3600)  # Обновление каждый час
            with app.app_context():
                from app.calendar_routes import update_calendar_cache
                update_calendar_cache()
        except Exception as e:
            print(f"Error in calendar update thread: {e}")
            time.sleep(60)  # При ошибке ждем минуту


@app.before_request
def before_request():
    """Выполняется перед каждым запросом"""
    # Инициализация админа при первом запросе (один раз)
    if not hasattr(app, '_admin_setup_done'):
        try:
            setup_admin()
        except Exception as e:
            # Если таблицы еще не созданы, пропускаем инициализацию админа
            # Пользователь должен сначала применить миграции через: flask db upgrade
            error_str = str(e)
            if 'doesn\'t exist' in error_str or 'Table' in error_str or 'ProgrammingError' in error_str:
                # Это ошибка отсутствия таблиц - это нормально, миграции еще не применены
                pass
            else:
                # Другая ошибка - логируем
                import sys
                print(f"Warning: Could not setup admin: {e}", file=sys.stderr)
        app._admin_setup_done = True
    
    # Запуск Telegram бота при первом запросе (один раз)
    if not hasattr(app, '_telegram_bot_started'):
        try:
            start_telegram_bot()
        except Exception as e:
            import sys
            print(f"Warning: Could not start Telegram bot: {e}", file=sys.stderr)
        app._telegram_bot_started = True
    
    # Запуск фоновой задачи обновления календаря (один раз)
    if not hasattr(app, '_calendar_update_started'):
        calendar_thread = threading.Thread(target=update_calendar_periodically, daemon=True, name="CalendarUpdater")
        calendar_thread.start()
        
        # Первоначальное обновление календаря
        try:
            with app.app_context():
                from app.calendar_routes import update_calendar_cache
                update_calendar_cache()
        except Exception as e:
            # Если таблицы еще не созданы, пропускаем обновление календаря
            error_str = str(e)
            if 'doesn\'t exist' in error_str or 'Table' in error_str or 'ProgrammingError' in error_str:
                # Это ошибка отсутствия таблиц - это нормально
                pass
            else:
                import sys
                print(f"Warning: Could not update calendar: {e}", file=sys.stderr)
        
        app._calendar_update_started = True


# WSGI entry point для production серверов (Passenger, Gunicorn и т.д.)
# Passenger ищет переменную 'application'
application = app

# Совместимость со старым passenger_wsgi.py
# Старый код: wsgi = load_source('wsgi', 'main.py'); application = wsgi.passenger_wsgi.py
# Когда main.py загружается как модуль 'wsgi', все его переменные становятся атрибутами модуля
# Поэтому нужно создать объект passenger_wsgi с атрибутом py
class PyModule:
    """Обертка для совместимости со старым passenger_wsgi.py"""
    def __init__(self):
        self.py = application

# Создаем объект passenger_wsgi для доступа через wsgi.passenger_wsgi.py
# Когда main.py загружается как модуль 'wsgi', этот объект будет доступен как wsgi.passenger_wsgi
passenger_wsgi = PyModule()

# Также создаем объект wsgi для совместимости с другими вариантами
class WsgiModule:
    """Обертка для совместимости со старым passenger_wsgi.py"""
    def __init__(self):
        self.wsgi = PyModule()
        self.passenger_wsgi = PyModule()

wsgi = WsgiModule()


if __name__ == '__main__':
    # Запуск только при прямом выполнении (не через WSGI)
    with app.app_context():
        db.create_all()
        setup_admin()
        # Запуск Telegram бота
        start_telegram_bot()
    
    app.run(debug=True, host='0.0.0.0', port=5000)

