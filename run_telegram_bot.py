"""
Скрипт для запуска Telegram бота в production

Использование:
    python run_telegram_bot.py

Этот скрипт должен запускаться отдельно от веб-сервера (например, через systemd, supervisor или cron)
"""
import os
import sys

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Устанавливаем UTF-8 для вывода
if sys.platform != 'win32':
    try:
        import locale
        os.environ.setdefault('LC_ALL', 'en_US.UTF-8')
        os.environ.setdefault('LANG', 'en_US.UTF-8')
        try:
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'C.UTF-8')
            except locale.Error:
                pass
    except:
        pass

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

def main():
    """Главная функция запуска бота"""
    from app import create_app
    from telegram_bot.bot import init_bot, run_bot_polling_sync
    
    # Создаем приложение для доступа к конфигурации
    app = create_app(os.getenv('FLASK_ENV', 'production'))
    
    with app.app_context():
        token = app.config.get('TELEGRAM_BOT_TOKEN')
        if not token:
            print("ERROR: TELEGRAM_BOT_TOKEN not set in environment variables.")
            print("Please set TELEGRAM_BOT_TOKEN in your .env file or environment variables.")
            sys.exit(1)
        
        print("=" * 50)
        print("Запуск Telegram бота...")
        print(f"Token: {token[:10]}...")
        print("=" * 50)
        
        try:
            # Инициализация бота
            print("Инициализация бота...")
            bot_app = init_bot()
            
            if not bot_app:
                print("ERROR: Failed to initialize Telegram bot.")
                sys.exit(1)
            
            print("Бот успешно инициализирован!")
            print("Запуск polling...")
            print("(Для остановки нажмите Ctrl+C)")
            print("=" * 50)
            
            # Запуск бота (блокирующий вызов)
            run_bot_polling_sync()
            
        except KeyboardInterrupt:
            print("\n" + "=" * 50)
            print("Остановка бота...")
            print("=" * 50)
        except Exception as e:
            print(f"ERROR: Ошибка при запуске бота: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    main()

