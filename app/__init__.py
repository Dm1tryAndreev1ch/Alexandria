from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from config import config
from app.models import db, User

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите в систему для доступа к этой странице.'
login_manager.login_message_category = 'info'

migrate = Migrate()


def create_app(config_name='development'):
    """Фабрика приложения Flask"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Инициализация расширений
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # Регистрация blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.upload_routes import bp as upload_bp
    app.register_blueprint(upload_bp, url_prefix='/upload')
    
    from app.queue_routes import bp as queue_bp
    app.register_blueprint(queue_bp, url_prefix='/queue')
    
    from app.todo_routes import bp as todo_bp
    app.register_blueprint(todo_bp, url_prefix='/todo')
    
    from app.calendar_routes import bp as calendar_bp
    app.register_blueprint(calendar_bp, url_prefix='/calendar')
    
    from app.admin_routes import bp as admin_bp
    app.register_blueprint(admin_bp)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    return app
