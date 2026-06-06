from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    db.create_all()
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
            conn.execute(text('ALTER TABLE course ALTER COLUMN short_description TYPE TEXT'))
            conn.commit()
    except Exception:
        pass

    if not User.query.filter_by(is_admin=True).first():
        admin = User(username='admin', email='admin@platform.com', is_admin=True)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
