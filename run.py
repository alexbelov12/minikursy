from app import create_app, db
from app.models import User

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Migrate: add new columns to existing database if missing
        try:
            from sqlalchemy import text, inspect
            insp = inspect(db.engine)
            course_cols = [c['name'] for c in insp.get_columns('course')]
            with db.engine.connect() as conn:
                if 'cover_image' not in course_cols:
                    conn.execute(text('ALTER TABLE course ADD COLUMN cover_image VARCHAR(500)'))
                    conn.commit()
                if 'category' not in course_cols:
                    conn.execute(text('ALTER TABLE course ADD COLUMN category VARCHAR(100)'))
                    conn.commit()
                if 'difficulty' not in course_cols:
                    conn.execute(text('ALTER TABLE course ADD COLUMN difficulty VARCHAR(20)'))
                    conn.commit()
        except Exception:
            pass

        admin = User.query.filter_by(is_admin=True).first()
        if not admin:
            admin = User(username='admin', email='admin@platform.com', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("=" * 50)
            print("Создан администратор:")
            print("  Email:    admin@platform.com")
            print("  Пароль:   admin123")
            print("=" * 50)
    print("Сервер запущен: http://127.0.0.1:5000")
    app.run(debug=True)
