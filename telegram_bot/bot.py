import os
import sys
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import asyncio

# Добавление пути к приложению
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User, File, CalendarEvent

# Глобальная переменная для хранения состояния загрузки файлов
file_upload_states = {}

# Глобальная переменная для хранения состояния расписания (навигация по дням)
schedule_states = {}

# Глобальная переменная для хранения Application бота (для отправки уведомлений)
bot_application = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    app = create_app()
    with app.app_context():
        # Сохранение telegram_id пользователя
        telegram_id = str(update.effective_user.id)
        telegram_username = update.effective_user.username
        first_name = update.effective_user.first_name or ""
        
        # Поиск пользователя по telegram_id
        user = User.query.filter_by(telegram_id=telegram_id).first()
        
        # Если не найден по telegram_id, пытаемся найти по username
        if not user and telegram_username:
            user = User.query.filter_by(username=telegram_username).first()
            if user:
                user.telegram_id = telegram_id
                db.session.commit()
                print(f"Linked telegram_id {telegram_id} to user {user.username}")
        
        welcome_text = (
            "Добро пожаловать в бот электронного дневника БГУИР!\n\n"
            "Доступные команды:\n"
            "/schedule - показать ближайшие занятия\n"
            "Отправьте фото или файл для загрузки в систему."
        )
        
        if user:
            if user.is_admin:
                welcome_text += "\n\n✅ Вы администратор. Доступные команды:\n/approve <username> - подтвердить пользователя"
                welcome_text += f"\n\nВаш аккаунт: {user.username}"
            else:
                welcome_text += f"\n\nВаш аккаунт: {user.username}"
                if not user.is_active:
                    welcome_text += "\n⚠️ Ваш аккаунт ожидает подтверждения администратором."
        else:
            welcome_text += "\n\n⚠️ Ваш Telegram аккаунт не связан с пользователем в системе."
            welcome_text += "\nЗарегистрируйтесь через веб-интерфейс или свяжите аккаунт, если вы уже зарегистрированы."
            if telegram_username:
                welcome_text += f"\n\nДля автоматической связи используйте имя пользователя: {telegram_username}"
        
        await update.message.reply_text(welcome_text)


async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /schedule - показать ближайшие занятия (только inline-кнопки с навигацией по дням)"""
    app = create_app()
    with app.app_context():
        # Получение событий из кэша БД
        # Используем локальное время (UTC+3) для сравнения
        from app.calendar_routes import LOCAL_TIMEZONE_OFFSET
        now = datetime.utcnow() + LOCAL_TIMEZONE_OFFSET
        future = now + timedelta(days=14)  # Показываем на 2 недели вперед
        
        events = CalendarEvent.query.filter(
            CalendarEvent.start_time >= now,
            CalendarEvent.start_time <= future
        ).order_by(CalendarEvent.start_time).all()
        
        if not events:
            await update.message.reply_text("Ближайшие занятия не найдены.")
            return
        
        # Группировка событий по дням
        events_by_day = group_events_by_day(events)
        
        if not events_by_day:
            await update.message.reply_text("Ближайшие занятия не найдены.")
            return
        
        # Сохраняем события по дням для навигации
        events_by_day_serialized = {}
        for day, day_events in events_by_day.items():
            day_str = day.isoformat()
            events_by_day_serialized[day_str] = [e.id for e in day_events]
        
        # Сохраняем состояние для навигации
        global schedule_states
        schedule_states[update.effective_user.id] = {
            'events_by_day_serialized': events_by_day_serialized,
            'current_day_index': 0
        }
        
        # Форматирование первого дня
        message, keyboard, day_info = format_schedule_day(events_by_day_serialized, 0)
        
        if not message:
            await update.message.reply_text("Ошибка при форматировании занятий.")
            return
        
        # Добавление кнопок навигации
        nav_buttons = []
        if day_info[1] > 1:
            if day_info[0] > 0:
                nav_buttons.append(InlineKeyboardButton("◀️ Предыдущий день", callback_data="schedule_prev_day"))
            if day_info[0] < day_info[1] - 1:
                nav_buttons.append(InlineKeyboardButton("Следующий день ▶️", callback_data="schedule_next_day"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, reply_markup=reply_markup)


async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /approve <username> - подтверждение пользователя (только админ)"""
    app = create_app()
    with app.app_context():
        # Проверка, является ли пользователь админом
        telegram_id = str(update.effective_user.id)
        admin_user = User.query.filter_by(telegram_id=telegram_id, is_admin=True).first()
        
        if not admin_user:
            await update.message.reply_text("У вас нет прав для выполнения этой команды.")
            return
        
        if not context.args:
            await update.message.reply_text("Использование: /approve <username>")
            return
        
        username = context.args[0]
        user = User.query.filter_by(username=username).first()
        
        if not user:
            await update.message.reply_text(f"Пользователь {username} не найден.")
            return
        
        if user.is_active:
            await update.message.reply_text(f"Пользователь {username} уже активирован.")
            return
        
        user.is_active = True
        db.session.commit()
        
        # Отправка уведомления пользователю, если у него есть telegram_id
        if user.telegram_id:
            try:
                bot = context.bot
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"✅ Ваш аккаунт {username} был активирован администратором!\nТеперь вы можете войти в систему."
                )
            except Exception as e:
                print(f"Error sending notification to user: {e}")
        
        await update.message.reply_text(f"Пользователь {username} успешно активирован!")


def group_events_by_day(events):
    """Группировка событий по дням"""
    events_by_day = {}
    for event in events:
        day_key = event.start_time.date()
        if day_key not in events_by_day:
            events_by_day[day_key] = []
        events_by_day[day_key].append(event)
    return events_by_day


def format_day_events_from_ids(events_by_day_serialized, day_index):
    """Форматирование событий для конкретного дня из сериализованных данных"""
    from datetime import date
    
    sorted_days = sorted(events_by_day_serialized.keys())
    
    if day_index < 0 or day_index >= len(sorted_days):
        return None, None, None
    
    current_day_str = sorted_days[day_index]
    event_ids = events_by_day_serialized[current_day_str]
    
    # Получение событий из БД (должно вызываться в контексте приложения)
    day_events = CalendarEvent.query.filter(CalendarEvent.id.in_(event_ids)).all()
    
    if not day_events:
        return None, None, None
    
    # Форматирование даты
    current_day = date.fromisoformat(current_day_str)
    day_name = current_day.strftime('%A')
    day_date = current_day.strftime('%d.%m.%Y')
    day_names_ru = {
        'Monday': 'Понедельник',
        'Tuesday': 'Вторник',
        'Wednesday': 'Среда',
        'Thursday': 'Четверг',
        'Friday': 'Пятница',
        'Saturday': 'Суббота',
        'Sunday': 'Воскресенье'
    }
    day_name_ru = day_names_ru.get(day_name, day_name)
    
    message = f"📅 {day_name_ru}, {day_date}\n\n"
    keyboard = []
    
    for event in sorted(day_events, key=lambda x: x.start_time):
        start_str = event.start_time.strftime('%H:%M')
        message += f"• {start_str} - {event.title}\n"
        
        keyboard.append([InlineKeyboardButton(
            f"{start_str} - {event.title[:30]}",
            callback_data=f"upload_file_{event.id}"
        )])
    
    return message, keyboard, (day_index, len(sorted_days))


def format_schedule_day(events_by_day_serialized, day_index):
    """Форматирование событий для расписания (только inline-кнопки)"""
    from datetime import date
    
    sorted_days = sorted(events_by_day_serialized.keys())
    
    if day_index < 0 or day_index >= len(sorted_days):
        return None, None, None
    
    current_day_str = sorted_days[day_index]
    event_ids = events_by_day_serialized[current_day_str]
    
    # Получение событий из БД (должно вызываться в контексте приложения)
    day_events = CalendarEvent.query.filter(CalendarEvent.id.in_(event_ids)).all()
    
    if not day_events:
        return None, None, None
    
    # Форматирование даты
    current_day = date.fromisoformat(current_day_str)
    day_name = current_day.strftime('%A')
    day_date = current_day.strftime('%d.%m.%Y')
    day_names_ru = {
        'Monday': 'Понедельник',
        'Tuesday': 'Вторник',
        'Wednesday': 'Среда',
        'Thursday': 'Четверг',
        'Friday': 'Пятница',
        'Saturday': 'Суббота',
        'Sunday': 'Воскресенье'
    }
    day_name_ru = day_names_ru.get(day_name, day_name)
    
    message = f"📅 {day_name_ru}, {day_date}\n\nВыберите занятие:"
    keyboard = []
    
    for event in sorted(day_events, key=lambda x: x.start_time):
        start_str = event.start_time.strftime('%H:%M')
        # Обрезаем название, если слишком длинное
        title = event.title[:35] + "..." if len(event.title) > 35 else event.title
        keyboard.append([InlineKeyboardButton(
            f"{start_str} - {title}",
            callback_data=f"select_event_{event.id}"
        )])
    
    return message, keyboard, (day_index, len(sorted_days))


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка загруженных файлов"""
    app = create_app()
    with app.app_context():
        # Получение пользователя по telegram_id
        telegram_id = str(update.effective_user.id)
        user = User.query.filter_by(telegram_id=telegram_id).first()
        
        if not user:
            await update.message.reply_text(
                "Вы не зарегистрированы в системе. Пожалуйста, зарегистрируйтесь через веб-интерфейс."
            )
            return
        
        if not user.is_active:
            await update.message.reply_text(
                "Ваш аккаунт не активирован. Ожидайте подтверждения администратором."
            )
            return
        
        # Получение файла
        if update.message.photo:
            file = await context.bot.get_file(update.message.photo[-1].file_id)
            file_type = 'image'
            original_filename = f"photo_{update.message.photo[-1].file_id}.jpg"
        elif update.message.document:
            file = await context.bot.get_file(update.message.document.file_id)
            file_type = 'document'
            original_filename = update.message.document.file_name or f"file_{update.message.document.file_id}"
        else:
            await update.message.reply_text("Поддерживаются только фото и документы.")
            return
        
        # Получение списка ближайших событий
        # Используем локальное время (UTC+3) для сравнения
        from app.calendar_routes import LOCAL_TIMEZONE_OFFSET
        now = datetime.utcnow() + LOCAL_TIMEZONE_OFFSET
        future = now + timedelta(days=14)  # Показываем на 2 недели вперед
        
        events = CalendarEvent.query.filter(
            CalendarEvent.start_time >= now,
            CalendarEvent.start_time <= future
        ).order_by(CalendarEvent.start_time).all()
        
        if not events:
            await update.message.reply_text(
                "Ближайшие занятия не найдены. Файл не может быть загружен."
            )
            return
        
        # Группировка событий по дням (сохраняем только ID событий)
        events_by_day = group_events_by_day(events)
        
        if not events_by_day:
            await update.message.reply_text(
                "Ближайшие занятия не найдены. Файл не может быть загружен."
            )
            return
        
        # Сохранение информации о файле и событиях для выбора
        # Сохраняем события по дням как словарь {date_str: [event_ids]}
        events_by_day_serialized = {}
        for day, day_events in events_by_day.items():
            day_str = day.isoformat()
            events_by_day_serialized[day_str] = [e.id for e in day_events]
        
        file_upload_states[update.effective_user.id] = {
            'file_id': file.file_id,
            'file_path': file.file_path,
            'original_filename': original_filename,
            'file_type': file_type,
            'user_id': user.id,
            'events_by_day_serialized': events_by_day_serialized,
            'current_day_index': 0
        }
        
        # Форматирование первого дня
        message, keyboard, day_info = format_day_events_from_ids(
            events_by_day_serialized, 0
        )
        
        if not message:
            await update.message.reply_text(
                "Ошибка при форматировании занятий."
            )
            del file_upload_states[update.effective_user.id]
            return
        
        # Добавление кнопок навигации
        nav_buttons = []
        if day_info[1] > 1:
            if day_info[0] > 0:
                nav_buttons.append(InlineKeyboardButton("◀️ Предыдущий день", callback_data="prev_day"))
            if day_info[0] < day_info[1] - 1:
                nav_buttons.append(InlineKeyboardButton("Следующий день ▶️", callback_data="next_day"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_upload")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Выберите занятие, к которому привязать файл:\n\n{message}",
            reply_markup=reply_markup
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на инлайн-кнопки"""
    query = update.callback_query
    await query.answer()
    
    app = create_app()
    with app.app_context():
        if query.data.startswith("select_event_"):
            # Выбор события для просмотра
            event_id = int(query.data.split("_")[-1])
            event = CalendarEvent.query.get(event_id)
            
            if event:
                files = File.query.filter_by(calendar_event_id=event_id).all()
                message = f"Занятие: {event.title}\n"
                message += f"Время: {event.start_time.strftime('%d.%m.%Y %H:%M')}\n\n"
                
                if files:
                    message += "Прикреплённые файлы:\n"
                    for f in files:
                        message += f"• {f.original_filename}\n"
                else:
                    message += "Файлы не загружены."
                
                await query.edit_message_text(message)
        
        elif query.data.startswith("upload_file_"):
            # Загрузка файла к событию
            event_id = int(query.data.split("_")[-1])
            user_id = query.from_user.id
            
            if user_id not in file_upload_states:
                await query.edit_message_text("Ошибка: информация о файле не найдена.")
                return
            
            file_info = file_upload_states[user_id]
            event = CalendarEvent.query.get(event_id)
            
            if not event:
                await query.edit_message_text("Ошибка: событие не найдено.")
                del file_upload_states[user_id]
                return
            
            try:
                # Скачивание файла
                file_obj = await context.bot.get_file(file_info['file_id'])
                
                # Сохранение файла
                import os
                upload_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + file_info['original_filename']
                file_path = os.path.join(upload_folder, filename)
                
                await file_obj.download(file_path)
                
                # Сохранение в БД
                file_record = File(
                    user_id=file_info['user_id'],
                    calendar_event_id=event.id,
                    filename=filename,
                    original_filename=file_info['original_filename'],
                    file_type=file_info['file_type'],
                    file_size=os.path.getsize(file_path)
                )
                db.session.add(file_record)
                db.session.commit()
                
                await query.edit_message_text(
                    f"Файл успешно загружен и привязан к занятию:\n{event.title}"
                )
                
            except Exception as e:
                await query.edit_message_text(f"Ошибка при загрузке файла: {str(e)}")
            
            finally:
                del file_upload_states[user_id]
        
        elif query.data in ["prev_day", "next_day"]:
            # Навигация по дням
            user_id = query.from_user.id
            
            if user_id not in file_upload_states:
                await query.edit_message_text("Ошибка: информация о файле не найдена.")
                return
            
            file_info = file_upload_states[user_id]
            
            if 'events_by_day_serialized' not in file_info:
                await query.edit_message_text("Ошибка: информация о днях не найдена.")
                return
            
            # Изменение индекса дня
            current_index = file_info['current_day_index']
            if query.data == "prev_day":
                new_index = current_index - 1
            else:  # next_day
                new_index = current_index + 1
            
            # Форматирование нового дня
            message, keyboard, day_info = format_day_events_from_ids(
                file_info['events_by_day_serialized'], new_index
            )
            
            if not message:
                await query.edit_message_text("Ошибка при форматировании занятий.")
                return
            
            # Обновление индекса
            file_info['current_day_index'] = new_index
            
            # Добавление кнопок навигации
            nav_buttons = []
            if day_info[1] > 1:
                if day_info[0] > 0:
                    nav_buttons.append(InlineKeyboardButton("◀️ Предыдущий день", callback_data="prev_day"))
                if day_info[0] < day_info[1] - 1:
                    nav_buttons.append(InlineKeyboardButton("Следующий день ▶️", callback_data="next_day"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_upload")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"Выберите занятие, к которому привязать файл:\n\n{message}",
                reply_markup=reply_markup
            )
        
        elif query.data == "cancel_upload":
            user_id = query.from_user.id
            if user_id in file_upload_states:
                del file_upload_states[user_id]
            await query.edit_message_text("Загрузка отменена.")
        
        elif query.data in ["schedule_prev_day", "schedule_next_day"]:
            # Навигация по дням в расписании
            global schedule_states
            user_id = query.from_user.id
            
            if user_id not in schedule_states:
                await query.edit_message_text("Ошибка: состояние расписания не найдено. Используйте /schedule.")
                return
            
            schedule_info = schedule_states[user_id]
            
            if 'events_by_day_serialized' not in schedule_info:
                await query.edit_message_text("Ошибка: информация о днях не найдена.")
                return
            
            # Изменение индекса дня
            current_index = schedule_info['current_day_index']
            if query.data == "schedule_prev_day":
                new_index = current_index - 1
            else:  # schedule_next_day
                new_index = current_index + 1
            
            # Форматирование нового дня
            message, keyboard, day_info = format_schedule_day(
                schedule_info['events_by_day_serialized'], new_index
            )
            
            if not message:
                await query.edit_message_text("Ошибка при форматировании занятий.")
                return
            
            # Обновление индекса
            schedule_info['current_day_index'] = new_index
            
            # Добавление кнопок навигации
            nav_buttons = []
            if day_info[1] > 1:
                if day_info[0] > 0:
                    nav_buttons.append(InlineKeyboardButton("◀️ Предыдущий день", callback_data="schedule_prev_day"))
                if day_info[0] < day_info[1] - 1:
                    nav_buttons.append(InlineKeyboardButton("Следующий день ▶️", callback_data="schedule_next_day"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=reply_markup)
        
        elif query.data.startswith("approve_"):
            # Подтверждение пользователя через кнопку
            telegram_id = str(query.from_user.id)
            admin_user = User.query.filter_by(telegram_id=telegram_id, is_admin=True).first()
            
            if not admin_user:
                await query.answer("У вас нет прав для выполнения этого действия.", show_alert=True)
                return
            
            username = query.data.replace("approve_", "")
            user = User.query.filter_by(username=username).first()
            
            if not user:
                await query.answer(f"Пользователь {username} не найден.", show_alert=True)
                return
            
            if user.is_active:
                await query.answer(f"Пользователь {username} уже активирован.", show_alert=True)
                return
            
            user.is_active = True
            db.session.commit()
            
            # Отправка уведомления пользователю, если у него есть telegram_id
            if user.telegram_id:
                try:
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"✅ Ваш аккаунт {username} был активирован администратором!\nТеперь вы можете войти в систему."
                    )
                except Exception as e:
                    print(f"Error sending notification to user: {e}")
            
            await query.answer(f"Пользователь {username} успешно активирован!")
            await query.edit_message_text(
                f"✅ Пользователь {username} успешно активирован!\n\n"
                f"Имя пользователя: {username}\n"
                f"ФИО: {user.get_full_name()}"
            )
        
        elif query.data.startswith("reject_"):
            # Отклонение пользователя
            telegram_id = str(query.from_user.id)
            admin_user = User.query.filter_by(telegram_id=telegram_id, is_admin=True).first()
            
            if not admin_user:
                await query.answer("У вас нет прав для выполнения этого действия.", show_alert=True)
                return
            
            username = query.data.replace("reject_", "")
            user = User.query.filter_by(username=username).first()
            
            if not user:
                await query.answer(f"Пользователь {username} не найден.", show_alert=True)
                return
            
            await query.answer(f"Пользователь {username} отклонен.")
            await query.edit_message_text(
                f"❌ Пользователь {username} отклонен.\n\n"
                f"Имя пользователя: {username}\n"
                f"ФИО: {user.get_full_name()}\n\n"
                f"Пользователь остается неактивным."
            )


def init_bot(token=None):
    """Инициализация бота (без запуска polling)"""
    # Если токен передан напрямую, используем его
    if token:
        bot_token = token
    else:
        # Пытаемся получить токен из переменных окружения
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        
        # Если токена нет в окружении, пытаемся загрузить из .env
        if not bot_token:
            try:
                from dotenv import load_dotenv
                # Пытаемся загрузить .env с обработкой BOM
                try:
                    load_dotenv(encoding='utf-8-sig')
                except (UnicodeEncodeError, UnicodeDecodeError):
                    # Если ошибка кодировки, пробуем без загрузки .env
                    # и используем только переменные окружения
                    pass
                except Exception:
                    # Другие ошибки - пробуем обычный utf-8
                    try:
                        load_dotenv(encoding='utf-8')
                    except Exception:
                        load_dotenv()
                
                bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
            except Exception as e:
                print(f"Warning: Could not load .env file: {e}")
                bot_token = None
    
    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN not set in environment variables")
        return None
    
    token = bot_token
    
    try:
        global bot_application
        bot_application = Application.builder().token(token).build()
        
        # Регистрация обработчиков
        bot_application.add_handler(CommandHandler("start", start))
        bot_application.add_handler(CommandHandler("schedule", schedule_command))
        bot_application.add_handler(CommandHandler("approve", approve_command))
        bot_application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_file))
        bot_application.add_handler(CallbackQueryHandler(button_callback))
        
        print(f"Telegram bot initialized with token: {token[:10]}...")
        return bot_application
    except Exception as e:
        print(f"Error initializing Telegram bot: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_bot_polling_sync():
    """Синхронная функция для запуска polling в отдельном потоке"""
    global bot_application
    if not bot_application:
        bot_application = init_bot()
    
    if not bot_application:
        print("ERROR: Failed to initialize bot application")
        return
    
    try:
        print("Telegram bot is running...")
        # Используем run_polling - это синхронный метод, который создает свой event loop
        # stop_signals=None отключает обработку сигналов (так как мы в daemon потоке)
        bot_application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            stop_signals=None
        )
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        error_msg = str(e)
        if "Conflict" in error_msg:
            print("ERROR: Another bot instance is running. Please stop all Python processes and restart.")
        else:
            print(f"Error in bot polling: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Запуск бота (для standalone режима)"""
    app = init_bot()
    if app:
        try:
            app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        except KeyboardInterrupt:
            print("Bot stopped by user")
        except Exception as e:
            print(f"Error in bot: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    main()

