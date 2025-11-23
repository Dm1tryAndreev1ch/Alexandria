# Настройка WSGI для Passenger

## Структура файлов

- **Главный файл приложения**: `main.py`
- **Точка входа WSGI**: зависит от вашей конфигурации

## Варианты настройки

### Вариант 1: Стандартный Passenger (рекомендуется)

Если вы можете использовать стандартный `passenger_wsgi.py`:

**Точка входа**: `passenger_wsgi.py`

**Главный файл**: `main.py`

**Конфигурация в панели управления хостингом:**
- WSGI файл: `passenger_wsgi.py`
- Главный файл: `main.py` (или не указывать, так как он импортируется автоматически)

### Вариант 2: Старый Passenger (если нельзя изменить passenger_wsgi.py)

Если на сервере используется старый `passenger_wsgi.py`, который загружает `main.py`:

**Точка входа**: `passenger_wsgi.py` (на сервере, не изменяется)

**Главный файл**: `main.py`

**Как это работает:**
```python
# Старый passenger_wsgi.py на сервере:
wsgi = load_source('wsgi', 'main.py')
application = wsgi.wsgi.py
```

В этом случае `main.py` должен содержать объект `wsgi.wsgi.py` (уже добавлен в код).

### Вариант 3: Gunicorn / uWSGI

Если используете Gunicorn или uWSGI:

**Точка входа**: `wsgi.py` или `passenger_wsgi.py`

**Главный файл**: `main.py`

**Команда запуска:**
```bash
gunicorn -w 4 -b 0.0.0.0:8000 passenger_wsgi:application
# или
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:application
```

## Настройка в панели управления хостингом

### Для Passenger (cPanel, Plesk и т.д.)

1. **WSGI файл**: `passenger_wsgi.py`
2. **Главный файл**: `main.py` (или оставить пустым)
3. **Python версия**: 3.13 (или ваша версия)
4. **Виртуальное окружение**: путь к `venv` (если используется)

### Для Apache с mod_wsgi

В `.htaccess` или конфигурации Apache:
```apache
WSGIScriptAlias / /path/to/your/project/passenger_wsgi.py
WSGIPythonPath /path/to/your/project
```

## Проверка работы

После настройки проверьте:

1. Приложение должно быть доступно по вашему домену
2. В логах не должно быть ошибок импорта
3. База данных должна быть настроена (переменная `DATABASE_URL` в `.env`)

## Важные файлы

- `main.py` - главный файл приложения Flask
- `passenger_wsgi.py` - точка входа WSGI (стандартный вариант)
- `wsgi.py` - альтернативная точка входа WSGI
- `config.py` - конфигурация приложения
- `.env` - переменные окружения (не загружайте на сервер, используйте переменные окружения хостинга)

## Переменные окружения

Убедитесь, что на сервере установлены все необходимые переменные:
- `SECRET_KEY`
- `ENCRYPTION_KEY`
- `DATABASE_URL`
- `TELEGRAM_BOT_TOKEN`
- `ADMIN_USERNAME`
- `GOOGLE_CALENDAR_ID`
- и другие из `env.example`

