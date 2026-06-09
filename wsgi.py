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

    try:
        from sqlalchemy import text, inspect
        insp = inspect(db.engine)
        user_cols = [c['name'] for c in insp.get_columns('user')]
        with db.engine.connect() as conn:
            if 'avatar_url' not in user_cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN avatar_url VARCHAR(500)'))
                conn.commit()
            if 'streak_days' not in user_cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN streak_days INTEGER DEFAULT 0'))
                conn.commit()
            if 'last_activity_date' not in user_cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN last_activity_date DATE'))
                conn.commit()
            if 'referral_code' not in user_cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN referral_code VARCHAR(20)'))
                conn.commit()
            if 'referred_by_id' not in user_cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN referred_by_id INTEGER REFERENCES "user"(id)'))
                conn.commit()
    except Exception:
        pass

    try:
        from sqlalchemy import text, inspect
        insp = inspect(db.engine)
        course_cols2 = [c['name'] for c in insp.get_columns('course')]
        with db.engine.connect() as conn:
            if 'deadline' not in course_cols2:
                conn.execute(text('ALTER TABLE course ADD COLUMN deadline DATE'))
                conn.commit()
    except Exception:
        pass

    try:
        from sqlalchemy import text, inspect
        insp = inspect(db.engine)
        lesson_cols = [c['name'] for c in insp.get_columns('lesson')]
        with db.engine.connect() as conn:
            if 'quiz_max_attempts' not in lesson_cols:
                conn.execute(text('ALTER TABLE lesson ADD COLUMN quiz_max_attempts INTEGER'))
                conn.commit()
            if 'quiz_reset_hours' not in lesson_cols:
                conn.execute(text('ALTER TABLE lesson ADD COLUMN quiz_reset_hours INTEGER'))
                conn.commit()
        insp2 = inspect(db.engine)
        qr_cols = [c['name'] for c in insp2.get_columns('user_quiz_result')]
        with db.engine.connect() as conn:
            if 'attempts' not in qr_cols:
                conn.execute(text('ALTER TABLE user_quiz_result ADD COLUMN attempts INTEGER DEFAULT 1'))
                conn.commit()
    except Exception:
        pass

    # Fix FK: user_quiz_answer.answer_id must cascade on delete
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            conn.execute(text('''
                ALTER TABLE user_quiz_answer
                DROP CONSTRAINT IF EXISTS user_quiz_answer_answer_id_fkey
            '''))
            conn.execute(text('''
                ALTER TABLE user_quiz_answer
                ADD CONSTRAINT user_quiz_answer_answer_id_fkey
                FOREIGN KEY (answer_id) REFERENCES answer(id) ON DELETE SET NULL
            '''))
            conn.commit()
    except Exception:
        pass

    if not User.query.filter_by(is_admin=True).first():
        admin = User(username='admin', email='admin@platform.com', is_admin=True)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
