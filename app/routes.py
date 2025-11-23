from flask import Blueprint, render_template
from flask_login import login_required

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """Главная страница"""
    return render_template('index.html', title='Главная')


@bp.route('/schedule')
@login_required
def schedule():
    """Расписание (табличный вид)"""
    from app.calendar_routes import events
    return events()


@bp.route('/schedule/calendar')
@login_required
def schedule_calendar():
    """Расписание (календарный вид)"""
    return render_template('schedule_calendar.html', title='Расписание - Календарь')

