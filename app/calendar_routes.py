import os
from datetime import datetime, timedelta, timezone
from flask import Blueprint, redirect, url_for, request, session, jsonify, render_template, current_app, flash
from flask_login import login_required, current_user
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app import db
from app.models import CalendarEvent

# Часовой пояс для календаря (Europe/Minsk = UTC+3)
LOCAL_TIMEZONE_OFFSET = timedelta(hours=3)  # UTC+3 для Минска

bp = Blueprint('calendar', __name__)

# Scopes для Google Calendar API
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


def get_credentials():
    """Получение credentials из сессии"""
    if 'credentials' not in session:
        return None
    
    creds_dict = session['credentials']
    creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
    
    # Обновление токена, если истёк
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        session['credentials'] = creds.to_json()
    
    return creds


@bp.route('/auth')
@login_required
def auth():
    """Начало OAuth flow для Google Calendar"""
    client_id = current_app.config.get('GOOGLE_CLIENT_ID')
    client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        flash('Google Calendar не настроен. Обратитесь к администратору.', 'danger')
        return redirect(url_for('main.index'))
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [request.url_root.rstrip('/') + url_for('calendar.callback')]
            }
        },
        scopes=SCOPES
    )
    flow.redirect_uri = url_for('calendar.callback', _external=True)
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    session['state'] = state
    return redirect(authorization_url)


@bp.route('/callback')
@login_required
def callback():
    """Callback для OAuth"""
    state = session.get('state')
    
    client_id = current_app.config.get('GOOGLE_CLIENT_ID')
    client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [request.url_root.rstrip('/') + url_for('calendar.callback')]
            }
        },
        scopes=SCOPES,
        state=state
    )
    flow.redirect_uri = url_for('calendar.callback', _external=True)
    
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)
    
    credentials = flow.credentials
    session['credentials'] = credentials.to_json()
    
    return redirect(url_for('calendar.events'))


def fetch_events_from_google():
    """Получение событий из Google Calendar без OAuth (публичный доступ)"""
    try:
        calendar_id = current_app.config.get('GOOGLE_CALENDAR_ID')
        if not calendar_id:
            return []
        
        # Используем публичный доступ к календарю через API
        # Для публичного календаря можно использовать API ключ или просто публичный URL
        # Преобразуем calendar ID в формат для публичного доступа
        public_calendar_id = calendar_id.replace('@group.calendar.google.com', '')
        
        # Используем публичный iCal feed или API с API ключом
        # Для простоты используем кэшированные события из БД
        # Обновление будет происходить через фоновую задачу
        
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
                cal = icalendar.Calendar.from_ical(cal_data)
                
                # Используем UTC для получения событий из iCal
                # Потом конвертируем в локальное время (UTC+3)
                now_utc = datetime.utcnow()
                future_utc = now_utc + timedelta(days=60)  # Кэшируем на 60 дней
                # Локальное время для сравнения с событиями в БД (которые хранятся в локальном времени)
                now_local = now_utc + LOCAL_TIMEZONE_OFFSET
                future_local = future_utc + LOCAL_TIMEZONE_OFFSET
                
                for component in cal.walk():
                    if component.name == "VEVENT":
                        event_id = str(component.get('UID', ''))
                        if not event_id:
                            continue
                        
                        summary = str(component.get('SUMMARY', 'Без названия'))
                        description = str(component.get('DESCRIPTION', ''))
                        location = str(component.get('LOCATION', ''))
                        
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
                    CalendarEvent.start_time >= now - timedelta(days=1),
                    CalendarEvent.start_time <= future
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
        update_calendar_cache()
        return jsonify({'success': True, 'message': 'Календарь успешно обновлен'})
    except Exception as e:
        current_app.logger.error(f'Error refreshing calendar cache: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

