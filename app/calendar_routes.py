from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import login_required, current_user
from app import db
from app.models import CalendarEvent

# Часовой пояс для календаря (Europe/Minsk = UTC+3)
LOCAL_TIMEZONE_OFFSET = timedelta(hours=3)  # UTC+3 для Минска

bp = Blueprint('calendar', __name__)


def fetch_events_from_google():
    """Получение событий из Google Calendar без OAuth (публичный доступ)"""
    try:
        calendar_id = current_app.config.get('GOOGLE_CALENDAR_ID')
        if not calendar_id:
            return []
        
        # Получение событий из кэша БД
        # События в БД хранятся в локальном времени (UTC+3)
        now = datetime.utcnow() + LOCAL_TIMEZONE_OFFSET
        future = now + timedelta(days=30)
        
        cached_events = CalendarEvent.query.filter(
            CalendarEvent.start_time >= now,
            CalendarEvent.start_time <= future
        ).order_by(CalendarEvent.start_time).all()
        
        # Если в кэше нет событий, пытаемся обновить
        if not cached_events:
            update_calendar_cache()
            cached_events = CalendarEvent.query.filter(
                CalendarEvent.start_time >= now,
                CalendarEvent.start_time <= future
            ).order_by(CalendarEvent.start_time).all()
        
        return cached_events
        
    except Exception as e:
        print(f"Error fetching events: {e}")
        return []


def update_calendar_cache():
    """Обновление кэша календаря из Google Calendar (публичный доступ)"""
    try:
        calendar_id = current_app.config.get('GOOGLE_CALENDAR_ID')
        if not calendar_id:
            return
        
        # Используем публичный iCal feed для получения событий
        import urllib.request
        import urllib.parse
        import icalendar
        
        # Публичный iCal URL для календаря
        # URL-encode calendar ID для использования в URL
        encoded_calendar_id = urllib.parse.quote(calendar_id, safe='')
        ical_url = f"https://calendar.google.com/calendar/ical/{encoded_calendar_id}/public/basic.ics"
        
        try:
            # Создаем запрос с заголовками
            req = urllib.request.Request(ical_url)
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            with urllib.request.urlopen(req, timeout=15) as response:
                cal_data = response.read()
                # Убеждаемся, что данные правильно декодированы перед парсингом
                # iCal формат обычно использует UTF-8, но может быть и другой кодировкой
                try:
                    # Пробуем декодировать как UTF-8 для проверки
                    cal_data_str = cal_data.decode('utf-8')
                    # Если успешно, кодируем обратно в bytes для библиотеки
                    cal_data = cal_data_str.encode('utf-8')
                except UnicodeDecodeError:
                    # Если UTF-8 не работает, оставляем как есть
                    pass
                
                cal = icalendar.Calendar.from_ical(cal_data)
                
                # Используем UTC для получения событий из iCal
                # Потом конвертируем в локальное время (UTC+3)
                now_utc = datetime.utcnow()
                future_utc = now_utc + timedelta(days=60)  # Кэшируем на 60 дней
                # Локальное время для сравнения с событиями в БД (которые хранятся в локальном времени)
                now_local = now_utc + LOCAL_TIMEZONE_OFFSET
                future_local = future_utc + LOCAL_TIMEZONE_OFFSET
                
                def safe_decode(value, default='', params=None):
                    """Безопасное декодирование значения из iCal компонента с поддержкой UTF-8"""
                    if value is None:
                        return default
                    
                    # Проверяем параметр CHARSET из iCal, если есть
                    charset = 'utf-8'  # По умолчанию UTF-8
                    if params and 'CHARSET' in params:
                        charset = params['CHARSET'].lower()
                    
                    # Пробуем разные методы получения значения
                    # 1. Если это bytes, декодируем напрямую
                    if isinstance(value, bytes):
                        try:
                            return value.decode(charset)
                        except (UnicodeDecodeError, LookupError):
                            try:
                                return value.decode('utf-8')
                            except UnicodeDecodeError:
                                try:
                                    return value.decode('latin-1')
                                except:
                                    return value.decode('utf-8', errors='replace')
                    
                    # 2. Если это vText объект, используем to_ical()
                    if hasattr(value, 'to_ical'):
                        try:
                            ical_bytes = value.to_ical()
                            if isinstance(ical_bytes, bytes):
                                # Пробуем декодировать с указанным charset или UTF-8
                                try:
                                    decoded = ical_bytes.decode(charset)
                                    return decoded
                                except (UnicodeDecodeError, LookupError):
                                    # Если указанный charset не работает, пробуем UTF-8
                                    try:
                                        decoded = ical_bytes.decode('utf-8')
                                        return decoded
                                    except UnicodeDecodeError:
                                        # Если UTF-8 не работает, пробуем latin-1 (часто используется в старых iCal)
                                        try:
                                            decoded = ical_bytes.decode('latin-1')
                                            return decoded
                                        except:
                                            # В крайнем случае используем replace для замены нечитаемых символов
                                            decoded = ical_bytes.decode('utf-8', errors='replace')
                                            return decoded
                            else:
                                # Это уже строка
                                return str(ical_bytes)
                        except (AttributeError, TypeError):
                            pass
                    
                    # 3. Если это уже строка, но может содержать неправильную кодировку
                    # Пробуем перекодировать через latin-1 -> utf-8 (частая проблема)
                    if isinstance(value, str):
                        # Проверяем, не является ли это неправильно декодированной UTF-8 строкой
                        # Это происходит, когда UTF-8 байты были декодированы как latin-1 или cp1252
                        try:
                            # Если строка содержит символы, которые выглядят как неправильно декодированные
                            # (например, последовательности типа "????" или странные символы)
                            if any(ord(c) > 127 for c in value):
                                # Пробуем исправить через latin-1 -> utf-8
                                # Это работает, если UTF-8 был декодирован как latin-1
                                try:
                                    fixed = value.encode('latin-1').decode('utf-8')
                                    # Проверяем, что исправление дало результат (нет замененных символов)
                                    if '\ufffd' not in fixed and '?' not in fixed[:10]:
                                        return fixed
                                except (UnicodeEncodeError, UnicodeDecodeError):
                                    pass
                                
                                # Пробуем исправить через cp1252 -> utf-8 (Windows кодировка)
                                try:
                                    fixed = value.encode('cp1252').decode('utf-8')
                                    if '\ufffd' not in fixed and '?' not in fixed[:10]:
                                        return fixed
                                except (UnicodeEncodeError, UnicodeDecodeError):
                                    pass
                                
                                # Пробуем исправить через cp1251 -> utf-8 (кириллица в Windows)
                                try:
                                    fixed = value.encode('cp1251').decode('utf-8')
                                    if '\ufffd' not in fixed and '?' not in fixed[:10]:
                                        return fixed
                                except (UnicodeEncodeError, UnicodeDecodeError):
                                    pass
                        except:
                            pass
                        return value
                    
                    # 5. В крайнем случае используем str()
                    try:
                        return str(value)
                    except:
                        return default
                
                for component in cal.walk():
                    if component.name == "VEVENT":
                        # Получаем параметры для правильного декодирования
                        # В icalendar параметры доступны через component.params, но структура может быть разной
                        uid_value = component.get('UID')
                        uid_params = {}
                        if hasattr(component, 'params') and 'UID' in component.params:
                            uid_params_list = component.params['UID']
                            if isinstance(uid_params_list, list) and len(uid_params_list) > 0:
                                uid_params = uid_params_list[0] if isinstance(uid_params_list[0], dict) else {}
                        
                        event_id = safe_decode(uid_value, '', uid_params)
                        if not event_id:
                            continue
                        
                        # Получаем значения с параметрами для правильного декодирования
                        summary_value = component.get('SUMMARY', 'Без названия')
                        summary_params = {}
                        if hasattr(component, 'params') and 'SUMMARY' in component.params:
                            summary_params_list = component.params['SUMMARY']
                            if isinstance(summary_params_list, list) and len(summary_params_list) > 0:
                                summary_params = summary_params_list[0] if isinstance(summary_params_list[0], dict) else {}
                        summary = safe_decode(summary_value, 'Без названия', summary_params)
                        
                        description_value = component.get('DESCRIPTION', '')
                        description_params = {}
                        if hasattr(component, 'params') and 'DESCRIPTION' in component.params:
                            description_params_list = component.params['DESCRIPTION']
                            if isinstance(description_params_list, list) and len(description_params_list) > 0:
                                description_params = description_params_list[0] if isinstance(description_params_list[0], dict) else {}
                        description = safe_decode(description_value, '', description_params)
                        
                        location_value = component.get('LOCATION', '')
                        location_params = {}
                        if hasattr(component, 'params') and 'LOCATION' in component.params:
                            location_params_list = component.params['LOCATION']
                            if isinstance(location_params_list, list) and len(location_params_list) > 0:
                                location_params = location_params_list[0] if isinstance(location_params_list[0], dict) else {}
                        location = safe_decode(location_value, '', location_params)
                        
                        dtstart = component.get('DTSTART')
                        dtend = component.get('DTEND')
                        
                        if not dtstart or not dtend:
                            continue
                        
                        # Преобразование даты
                        # iCal может возвращать datetime или date объекты
                        # Даты в iCal обычно в UTC (формат DTSTART:20251105T103500Z)
                        if isinstance(dtstart.dt, datetime):
                            start_time = dtstart.dt
                            # Если нет timezone, считаем что это UTC (как в iCal формате)
                            if start_time.tzinfo is None:
                                start_time = start_time.replace(tzinfo=timezone.utc)
                        else:
                            # Это date объект, добавляем время начала дня в UTC
                            start_time = datetime.combine(dtstart.dt, datetime.min.time(), tzinfo=timezone.utc)
                        
                        if isinstance(dtend.dt, datetime):
                            end_time = dtend.dt
                            if end_time.tzinfo is None:
                                end_time = end_time.replace(tzinfo=timezone.utc)
                        else:
                            end_time = datetime.combine(dtend.dt, datetime.min.time(), tzinfo=timezone.utc)
                        
                        # Конвертируем UTC в локальное время (Europe/Minsk, UTC+3)
                        # и сохраняем как naive datetime в БД
                        if start_time.tzinfo:
                            # Конвертируем из UTC в локальное время (UTC+3)
                            start_time_utc = start_time
                            start_time_local = start_time_utc + LOCAL_TIMEZONE_OFFSET
                            start_time = start_time_local.replace(tzinfo=None)
                        if end_time.tzinfo:
                            end_time_utc = end_time
                            end_time_local = end_time_utc + LOCAL_TIMEZONE_OFFSET
                            end_time = end_time_local.replace(tzinfo=None)
                        
                        # Пропускаем старые события (сравниваем в локальном времени)
                        if end_time < now_local:
                            continue
                        
                        # Пропускаем события далеко в будущем
                        if start_time > future_local:
                            continue
                        
                        # Сохранение или обновление в БД
                        existing = CalendarEvent.query.filter_by(event_id=event_id).first()
                        if existing:
                            existing.title = summary
                            existing.start_time = start_time
                            existing.end_time = end_time
                            existing.description = description
                            existing.location = location
                            existing.updated_at = datetime.utcnow()
                        else:
                            cal_event = CalendarEvent(
                                event_id=event_id,
                                title=summary,
                                start_time=start_time,
                                end_time=end_time,
                                description=description,
                                location=location
                            )
                            db.session.add(cal_event)
                
                db.session.commit()
                event_count = CalendarEvent.query.filter(
                    CalendarEvent.start_time >= now_local - timedelta(days=1),
                    CalendarEvent.start_time <= future_local
                ).count()
                print(f"Calendar cache updated successfully. Calendar ID: {calendar_id}, Events cached: {event_count}")
                
        except Exception as e:
            print(f"Error updating calendar from iCal feed: {e}")
            # Если iCal не работает, используем альтернативный метод через API
            # (требует API ключ, но можно оставить пустым для публичных календарей)
            
    except Exception as e:
        print(f"Error in update_calendar_cache: {e}")


@bp.route('/events')
@login_required
def events():
    """Получение и отображение событий календаря (без OAuth)"""
    # Получаем события из кэша БД
    events_list = fetch_events_from_google()
    
    # Форматируем для шаблона
    events_for_template = []
    for event in events_list:
        # Форматируем время для отображения (локальное время уже в БД)
        start_str = event.start_time.strftime('%Y-%m-%d %H:%M')
        end_str = event.end_time.strftime('%Y-%m-%d %H:%M')
        events_for_template.append({
            'id': event.event_id,
            'summary': event.title,
            'start': {'dateTime': event.start_time.isoformat(), 'formatted': start_str},
            'end': {'dateTime': event.end_time.isoformat(), 'formatted': end_str},
            'description': event.description or '',
            'location': event.location or ''
        })
    
    return render_template('schedule.html', events=events_for_template, title='Расписание')


@bp.route('/events/list')
@login_required
def events_list():
    """API endpoint для получения списка событий (для выбора при загрузке файлов)"""
    try:
        # Получаем события из кэша БД
        # События в БД хранятся в локальном времени (UTC+3)
        now = datetime.utcnow() + LOCAL_TIMEZONE_OFFSET
        future = now + timedelta(days=7)
        
        events = CalendarEvent.query.filter(
            CalendarEvent.start_time >= now,
            CalendarEvent.start_time <= future
        ).order_by(CalendarEvent.start_time).all()
        
        # Форматирование для JSON
        events_list = []
        for event in events:
            # Добавляем timezone для правильного отображения
            start_iso = event.start_time.isoformat()
            end_iso = event.end_time.isoformat()
            
            if '+' not in start_iso and 'Z' not in start_iso:
                start_iso = start_iso + '+03:00'
            if '+' not in end_iso and 'Z' not in end_iso:
                end_iso = end_iso + '+03:00'
            
            events_list.append({
                'id': event.event_id,
                'title': event.title,
                'start': start_iso,
                'end': end_iso,
                'description': event.description or '',
                'location': event.location or ''
            })
        
        return jsonify(events_list)
        
    except Exception as error:
        return jsonify({'error': str(error)}), 500


@bp.route('/events/cached')
@login_required
def events_cached():
    """Получение событий из кэша БД"""
    try:
        # Получаем параметры диапазона дат из запроса (если есть)
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        
        if start_str and end_str:
            # FullCalendar передает даты в формате ISO
            try:
                start_date = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                end_date = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                # Конвертируем в UTC naive для сравнения с БД
                if start_date.tzinfo:
                    start_date = start_date.replace(tzinfo=None)
                if end_date.tzinfo:
                    end_date = end_date.replace(tzinfo=None)
            except (ValueError, AttributeError):
                # Если не удалось распарсить, используем дефолтный диапазон
                start_date = datetime.utcnow()
                end_date = start_date + timedelta(days=60)
        else:
            # Дефолтный диапазон: от текущего момента до 60 дней вперед
            start_date = datetime.utcnow()
            end_date = start_date + timedelta(days=60)
        
        # Получаем события в запрошенном диапазоне
        # События, которые пересекаются с диапазоном (start_time < end_date AND end_time > start_date)
        events = CalendarEvent.query.filter(
            CalendarEvent.start_time < end_date,
            CalendarEvent.end_time > start_date
        ).order_by(CalendarEvent.start_time).all()
        
        events_list = []
        for event in events:
            # События в БД хранятся в локальном времени (UTC+3)
            # Добавляем timezone для правильного отображения в браузере
            start_iso = event.start_time.isoformat()
            end_iso = event.end_time.isoformat()
            
            # Если время не содержит timezone, добавляем локальный (UTC+3)
            if '+' not in start_iso and 'Z' not in start_iso:
                start_iso = start_iso + '+03:00'
            if '+' not in end_iso and 'Z' not in end_iso:
                end_iso = end_iso + '+03:00'
            
            events_list.append({
                'id': event.id,  # ID из БД для загрузки файлов
                'event_id': event.event_id,  # ID из Google Calendar
                'title': event.title,
                'start': start_iso,
                'end': end_iso,
                'description': event.description or '',
                'location': event.location or ''
            })
        
        return jsonify(events_list)
    except Exception as e:
        current_app.logger.error(f'Error in events_cached: {e}', exc_info=True)
        # Возвращаем пустой массив вместо ошибки, чтобы календарь мог отобразиться
        return jsonify([])


@bp.route('/refresh', methods=['POST'])
@login_required
def refresh_cache():
    """Принудительное обновление кэша календаря (только для админа)"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Доступ запрещен. Требуются права администратора.'}), 403
    
    try:
        # Получаем параметр force_refresh из запроса
        force_refresh = request.json.get('force_refresh', False) if request.is_json else False
        
        if force_refresh:
            # Удаляем все существующие события перед обновлением
            # Это исправит проблемы с кодировкой в уже сохраненных данных
            deleted_count = CalendarEvent.query.delete()
            db.session.commit()
            current_app.logger.info(f'Deleted {deleted_count} calendar events before refresh')
        
        update_calendar_cache()
        return jsonify({'success': True, 'message': 'Календарь успешно обновлен'})
    except Exception as e:
        current_app.logger.error(f'Error refreshing calendar cache: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

