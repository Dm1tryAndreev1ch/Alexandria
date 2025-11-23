from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField, DateTimeField, SelectField
from wtforms.validators import DataRequired, EqualTo, Length, ValidationError
from app.models import User


class LoginForm(FlaskForm):
    """Форма входа"""
    username = StringField('Имя пользователя', validators=[DataRequired(message='Введите имя пользователя')])
    password = PasswordField('Пароль', validators=[DataRequired(message='Введите пароль')])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


class RegistrationForm(FlaskForm):
    """Форма регистрации"""
    username = StringField('Имя пользователя', validators=[
        DataRequired(message='Введите имя пользователя'),
        Length(min=3, max=80, message='Имя пользователя должно быть от 3 до 80 символов')
    ])
    full_name = StringField('ФИО (Полное имя)', validators=[
        DataRequired(message='Введите ФИО'),
        Length(min=3, max=200, message='ФИО должно быть от 3 до 200 символов')
    ])
    password = PasswordField('Пароль', validators=[
        DataRequired(message='Введите пароль'),
        Length(min=6, message='Пароль должен быть не менее 6 символов')
    ])
    password2 = PasswordField('Повторите пароль', validators=[
        DataRequired(message='Повторите пароль'),
        EqualTo('password', message='Пароли не совпадают')
    ])
    submit = SubmitField('Зарегистрироваться')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Пользователь с таким именем уже существует.')


class TaskForm(FlaskForm):
    """Форма создания/редактирования задачи"""
    title = StringField('Название', validators=[DataRequired(message='Введите название задачи')])
    description = TextAreaField('Описание')
    due_date = DateTimeField('Срок выполнения', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    submit = SubmitField('Сохранить')


class QueueEntryForm(FlaskForm):
    """Форма добавления в очередь"""
    subject = SelectField('Предмет', choices=[
        ('ОАиП', 'ОАиП'),
        ('История', 'История')
    ], validators=[DataRequired()])
    event_date = StringField('Дата занятия (для истории)', validators=[])
    submit = SubmitField('Встать в очередь')

