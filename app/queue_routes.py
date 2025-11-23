from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import QueueEntry, User, CalendarEvent
from app.forms import QueueEntryForm

bp = Blueprint('queue', __name__)


def is_history_event(event_title):
    """Проверка, является ли событие занятием по истории"""
    title_lower = event_title.lower()
    # Проверяем различные варианты названий истории
    history_keywords = ['история', 'history', 'истбг', 'ист.бг']
    has_history_keyword = any(keyword in title_lower for keyword in history_keywords)
    # Обязательно должно быть (ПЗ) в названии
    has_pz = '(пз)' in title_lower or '(пз' in title_lower
    return has_history_keyword and has_pz


def get_history_dates():
    """Получение дат с занятиями по истории из календаря"""
    now = datetime.utcnow()
    future = now + timedelta(days=60)  # Проверяем на 60 дней вперед
    
    # Получаем все события в диапазоне
    events = CalendarEvent.query.filter(
        CalendarEvent.start_time >= now,
        CalendarEvent.start_time <= future
    ).all()
    
    history_dates = set()
    for event in events:
        if is_history_event(event.title):
            # Берем дату начала события
            event_date = event.start_time.date()
            history_dates.add(event_date)
    
    return sorted(history_dates)


@bp.route('/')
@login_required
def index():
    """Главная страница очереди ответов"""
    form = QueueEntryForm()
    
    # Получение дат с историей для формы
    history_dates = get_history_dates()
    
    # Получение очередей для обоих предметов
    oaip_queue = QueueEntry.query.filter_by(
        subject='ОАиП',
        has_answered=False
    ).order_by(QueueEntry.timestamp.asc()).all()
    
    history_queue = QueueEntry.query.filter_by(
        subject='История',
        has_answered=False
    ).order_by(QueueEntry.event_date.asc(), QueueEntry.timestamp.asc()).all()
    
    # Проверка, находится ли пользователь в очереди
    user_in_oaip = QueueEntry.query.filter_by(
        user_id=current_user.id,
        subject='ОАиП',
        has_answered=False
    ).first()
    
    user_in_history = QueueEntry.query.filter_by(
        user_id=current_user.id,
        subject='История',
        has_answered=False
    ).first()
    
    return render_template(
        'queue.html',
        title='Очередь ответов',
        form=form,
        oaip_queue=oaip_queue,
        history_queue=history_queue,
        user_in_oaip=user_in_oaip,
        user_in_history=user_in_history,
        history_dates=history_dates
    )


@bp.route('/add', methods=['POST'])
@login_required
def add():
    """Добавление в очередь"""
    form = QueueEntryForm()
    
    if form.validate_on_submit():
        subject = form.subject.data
        
        # Для истории проверяем наличие даты и занятия
        if subject == 'История':
            event_date_str = form.event_date.data
            if not event_date_str:
                flash('Для истории необходимо выбрать дату занятия.', 'danger')
                return redirect(url_for('queue.index'))
            
            try:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Неверный формат даты.', 'danger')
                return redirect(url_for('queue.index'))
            
            # Проверяем, есть ли занятия по истории на эту дату
            history_dates = get_history_dates()
            if event_date not in history_dates:
                flash('На выбранную дату нет занятий по истории.', 'danger')
                return redirect(url_for('queue.index'))
            
            # Проверка, не находится ли пользователь уже в очереди на эту дату
            existing = QueueEntry.query.filter_by(
                user_id=current_user.id,
                subject='История',
                event_date=event_date,
                has_answered=False
            ).first()
            
            if existing:
                flash(f'Вы уже находитесь в очереди по истории на {event_date.strftime("%d.%m.%Y")}.', 'warning')
                return redirect(url_for('queue.index'))
            
            # Находим событие календаря для этой даты
            calendar_event = None
            events = CalendarEvent.query.filter(
                CalendarEvent.start_time >= datetime.combine(event_date, datetime.min.time()),
                CalendarEvent.start_time < datetime.combine(event_date + timedelta(days=1), datetime.min.time())
            ).all()
            
            for event in events:
                if is_history_event(event.title):
                    calendar_event = event
                    break
            
            # Добавление в очередь
            queue_entry = QueueEntry(
                user_id=current_user.id,
                subject=subject,
                event_date=event_date,
                calendar_event_id=calendar_event.id if calendar_event else None,
                has_answered=False
            )
        else:
            # Для ОАиП проверка, не находится ли пользователь уже в очереди
            existing = QueueEntry.query.filter_by(
                user_id=current_user.id,
                subject=subject,
                has_answered=False
            ).first()
            
            if existing:
                flash(f'Вы уже находитесь в очереди по предмету {subject}.', 'warning')
                return redirect(url_for('queue.index'))
            
            # Добавление в очередь
            queue_entry = QueueEntry(
                user_id=current_user.id,
                subject=subject,
                has_answered=False
            )
        
        db.session.add(queue_entry)
        db.session.commit()
        
        if subject == 'История':
            flash(f'Вы добавлены в очередь по истории на {event_date.strftime("%d.%m.%Y")}.', 'success')
        else:
            flash(f'Вы добавлены в очередь по предмету {subject}.', 'success')
    else:
        flash('Ошибка при добавлении в очередь.', 'danger')
    
    return redirect(url_for('queue.index'))


@bp.route('/remove/<int:entry_id>', methods=['POST'])
@login_required
def remove(entry_id):
    """Удаление из очереди (только своя запись)"""
    entry = QueueEntry.query.get_or_404(entry_id)
    
    if entry.user_id != current_user.id:
        flash('Вы можете удалить только свою запись из очереди.', 'danger')
        return redirect(url_for('queue.index'))
    
    if entry.has_answered:
        flash('Эта запись уже отмечена как отвеченная.', 'warning')
        return redirect(url_for('queue.index'))
    
    db.session.delete(entry)
    db.session.commit()
    
    flash('Вы удалены из очереди.', 'success')
    return redirect(url_for('queue.index'))


@bp.route('/mark_answered/<int:entry_id>', methods=['POST'])
@login_required
def mark_answered(entry_id):
    """Отметка как отвеченного (только своя запись)"""
    entry = QueueEntry.query.get_or_404(entry_id)
    
    if entry.user_id != current_user.id:
        flash('Вы можете отметить только свою запись.', 'danger')
        return redirect(url_for('queue.index'))
    
    entry.has_answered = True
    db.session.commit()
    
    flash('Вы отметили себя как ответившего.', 'success')
    return redirect(url_for('queue.index'))


@bp.route('/api/list')
@login_required
def api_list():
    """API для получения списка очереди"""
    subject = request.args.get('subject')
    
    if subject not in ['ОАиП', 'История']:
        return jsonify({'error': 'Неверный предмет'}), 400
    
    entries = QueueEntry.query.filter_by(
        subject=subject,
        has_answered=False
    ).order_by(QueueEntry.timestamp.asc()).all()
    
    entries_list = [{
        'id': entry.id,
        'username': entry.user.username,
        'full_name': entry.user.get_full_name(),
        'timestamp': entry.timestamp.isoformat(),
        'is_current_user': entry.user_id == current_user.id
    } for entry in entries]
    
    return jsonify(entries_list)

