from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Task
from app.forms import TaskForm

bp = Blueprint('todo', __name__)


@bp.route('/list')
@login_required
def list():
    """Список задач (табличный вид)"""
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(
        Task.due_date.asc(),
        Task.completed.asc()
    ).all()
    
    return render_template('todo_list.html', title='Мои задачи', tasks=tasks)


@bp.route('/calendar')
@login_required
def calendar():
    """Календарный вид задач"""
    return render_template('todo_calendar.html', title='Календарь задач')


@bp.route('/api/events')
@login_required
def api_events():
    """API для получения событий задач для FullCalendar"""
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    
    events = []
    for task in tasks:
        events.append({
            'id': task.id,
            'title': task.title,
            'start': task.due_date.isoformat() if task.due_date else None,
            'allDay': False,
            'backgroundColor': '#28a745' if task.completed else '#dc3545',
            'borderColor': '#28a745' if task.completed else '#dc3545',
            'extendedProps': {
                'description': task.description,
                'completed': task.completed
            }
        })
    
    return jsonify(events)


@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Добавление новой задачи"""
    form = TaskForm()
    
    if form.validate_on_submit():
        task = Task(
            user_id=current_user.id,
            title=form.title.data,
            description=form.description.data if form.description.data else None,
            due_date=form.due_date.data,
            completed=False
        )
        db.session.add(task)
        db.session.commit()
        flash('Задача успешно добавлена.', 'success')
        return redirect(url_for('todo.list'))
    
    return render_template('todo_form.html', title='Добавить задачу', form=form)


@bp.route('/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit(task_id):
    """Редактирование задачи"""
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != current_user.id:
        flash('У вас нет прав для редактирования этой задачи.', 'danger')
        return redirect(url_for('todo.list'))
    
    form = TaskForm(obj=task)
    
    if form.validate_on_submit():
        task.title = form.title.data
        task.description = form.description.data if form.description.data else None
        task.due_date = form.due_date.data
        db.session.commit()
        flash('Задача успешно обновлена.', 'success')
        return redirect(url_for('todo.list'))
    
    return render_template('todo_form.html', title='Редактировать задачу', form=form, task=task)


@bp.route('/delete/<int:task_id>', methods=['POST'])
@login_required
def delete(task_id):
    """Удаление задачи"""
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != current_user.id:
        flash('У вас нет прав для удаления этой задачи.', 'danger')
        return redirect(url_for('todo.list'))
    
    db.session.delete(task)
    db.session.commit()
    flash('Задача успешно удалена.', 'success')
    return redirect(url_for('todo.list'))


@bp.route('/toggle/<int:task_id>', methods=['POST'])
@login_required
def toggle(task_id):
    """Переключение статуса выполнения задачи"""
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != current_user.id:
        return jsonify({'error': 'Нет прав'}), 403
    
    task.completed = not task.completed
    db.session.commit()
    
    return jsonify({'completed': task.completed})

