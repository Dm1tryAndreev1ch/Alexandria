import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import File, CalendarEvent
from app.utils import allowed_file, get_secure_filename

bp = Blueprint('upload', __name__)


@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    """Страница загрузки файлов"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Файл не выбран.', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        calendar_event_id = request.form.get('calendar_event_id')
        
        if file.filename == '':
            flash('Файл не выбран.', 'danger')
            return redirect(request.url)
        
        if not calendar_event_id:
            flash('Необходимо выбрать занятие из расписания.', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Получение события календаря
            cal_event = CalendarEvent.query.get(calendar_event_id)
            if not cal_event:
                flash('Занятие не найдено.', 'danger')
                return redirect(request.url)
            
            # Сохранение файла
            filename = get_secure_filename(file.filename)
            from datetime import datetime as dt
            timestamp = dt.now().strftime('%Y%m%d_%H%M%S_')
            unique_filename = timestamp + filename
            
            upload_folder = os.path.join(os.getcwd(), 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            
            file_path = os.path.join(upload_folder, unique_filename)
            file.save(file_path)
            
            # Определение типа файла
            file_ext = filename.rsplit('.', 1)[1].lower()
            file_type = 'image' if file_ext in ['png', 'jpg', 'jpeg', 'gif'] else 'document'
            
            # Сохранение в БД
            file_record = File(
                user_id=current_user.id,
                calendar_event_id=cal_event.id,
                filename=unique_filename,
                original_filename=filename,
                file_type=file_type,
                file_size=os.path.getsize(file_path)
            )
            db.session.add(file_record)
            db.session.commit()
            
            flash('Файл успешно загружен и привязан к занятию.', 'success')
            return redirect(url_for('upload.upload_file'))
        else:
            flash('Недопустимый тип файла.', 'danger')
    
    # Получение событий для выбора из кэша БД
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    future = now + timedelta(days=7)
    
    events = CalendarEvent.query.filter(
        CalendarEvent.start_time >= now,
        CalendarEvent.start_time <= future
    ).order_by(CalendarEvent.start_time).all()
    
    events_list = [{
        'id': event.id,
        'title': event.title,
        'start': event.start_time.isoformat()
    } for event in events]
    
    return render_template('upload.html', title='Загрузка файлов', events=events_list)


@bp.route('/files/<int:file_id>')
@login_required
def download_file(file_id):
    """Скачивание файла"""
    file_record = File.query.get_or_404(file_id)
    
    # Проверка прав доступа (только владелец или админ)
    if file_record.user_id != current_user.id and not current_user.is_admin:
        flash('У вас нет прав для доступа к этому файлу.', 'danger')
        return redirect(url_for('upload.upload_file'))
    
    upload_folder = os.path.join(os.getcwd(), 'uploads')
    return send_from_directory(upload_folder, file_record.filename, as_attachment=True)


@bp.route('/files/event/<int:event_id>')
@login_required
def files_by_event(event_id):
    """Получение списка файлов для конкретного события"""
    cal_event = CalendarEvent.query.get_or_404(event_id)
    files = File.query.filter_by(calendar_event_id=event_id).order_by(File.upload_date.desc()).all()
    
    files_list = [{
        'id': f.id,
        'original_filename': f.original_filename,
        'upload_date': f.upload_date.isoformat(),
        'file_type': f.file_type,
        'uploader': f.user.username
    } for f in files]
    
    return jsonify({
        'event': {
            'id': cal_event.id,
            'title': cal_event.title,
            'start_time': cal_event.start_time.isoformat()
        },
        'files': files_list
    })


@bp.route('/files')
@login_required
def list_files():
    """Список всех загруженных файлов пользователя"""
    files = File.query.filter_by(user_id=current_user.id).order_by(File.upload_date.desc()).all()
    return render_template('files_list.html', title='Мои файлы', files=files)

