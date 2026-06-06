from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите в систему для доступа к этой странице'
login_manager.login_message_category = 'warning'

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.courses import courses_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    @app.context_processor
    def inject_lang():
        from app.translations import TRANSLATIONS
        from flask_login import current_user
        lang = session.get('lang', 'ru')
        def t(key):
            trans = TRANSLATIONS.get(lang, TRANSLATIONS['ru'])
            return trans.get(key, TRANSLATIONS['ru'].get(key, key))
        unread_count = 0
        if current_user.is_authenticated and not current_user.is_admin:
            from app.models import Notification
            unread_count = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()
        return dict(t=t, lang=lang, unread_count=unread_count)

    return app
