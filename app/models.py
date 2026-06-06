import secrets
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

BADGE_DEFS = {
    'first_lesson':  {'icon': 'fas fa-check-circle', 'color': '#10b981', 'bg': '#dcfce7',
                      'name': 'Первый шаг',    'desc': 'Завершил первый урок'},
    'ten_lessons':   {'icon': 'fas fa-book-reader',  'color': '#3b82f6', 'bg': '#dbeafe',
                      'name': 'Книжный червь', 'desc': 'Завершил 10 уроков'},
    'first_course':  {'icon': 'fas fa-graduation-cap','color': '#f59e0b', 'bg': '#fef9c3',
                      'name': 'Выпускник',    'desc': 'Прошёл первый курс полностью'},
    'three_courses': {'icon': 'fas fa-trophy',        'color': '#ef4444', 'bg': '#fee2e2',
                      'name': 'Мастер',       'desc': 'Прошёл 3 курса полностью'},
    'quiz_perfect':  {'icon': 'fas fa-star',          'color': '#6366f1', 'bg': '#ede9fe',
                      'name': 'Перфекционист','desc': 'Получил 100% в тесте'},
}


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    progress = db.relationship('UserProgress', backref='user', lazy=True, cascade='all, delete-orphan')
    quiz_results = db.relationship('UserQuizResult', backref='user', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('CourseReview', backref='user', lazy=True, cascade='all, delete-orphan')
    lesson_comments = db.relationship('LessonComment', backref='user', lazy=True, cascade='all, delete-orphan')
    favorites = db.relationship('FavoriteCourse', backref='user', lazy=True, cascade='all, delete-orphan')
    badges = db.relationship('UserBadge', backref='user', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')
    reset_tokens = db.relationship('PasswordResetToken', backref='user', lazy=True, cascade='all, delete-orphan')
    certificates = db.relationship('Certificate', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    short_description = db.Column(db.Text)
    cover_image = db.Column(db.String(500))
    category = db.Column(db.String(100))
    difficulty = db.Column(db.String(20))
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lessons = db.relationship('Lesson', backref='course', lazy=True,
                              order_by='Lesson.order', cascade='all, delete-orphan')
    reviews = db.relationship('CourseReview', backref='course', lazy=True, cascade='all, delete-orphan')
    favorited_by = db.relationship('FavoriteCourse', backref='course', lazy=True, cascade='all, delete-orphan')
    certificates = db.relationship('Certificate', backref='course', lazy=True, cascade='all, delete-orphan')

    @property
    def avg_rating(self):
        if not self.reviews:
            return 0
        return round(sum(r.rating for r in self.reviews) / len(self.reviews), 1)

    @property
    def review_count(self):
        return len(self.reviews)


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    video_url = db.Column(db.String(500))
    lesson_type = db.Column(db.String(20), default='text')
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship('Question', backref='lesson', lazy=True,
                                order_by='Question.order', cascade='all, delete-orphan')
    progress_records = db.relationship('UserProgress', backref='lesson', lazy=True, cascade='all, delete-orphan')
    quiz_results = db.relationship('UserQuizResult', backref='lesson', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('LessonComment', backref='lesson', lazy=True,
                               order_by='LessonComment.created_at', cascade='all, delete-orphan')


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    order = db.Column(db.Integer, default=0)

    answers = db.relationship('Answer', backref='question', lazy=True, cascade='all, delete-orphan')


class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)


class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'lesson_id'),)


class UserQuizResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    max_score = db.Column(db.Integer, default=0)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── New models ─────────────────────────────────────────────────────────────────

class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    code = db.Column(db.String(32), unique=True, nullable=False,
                     default=lambda: secrets.token_hex(16))
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'course_id'),)


class CourseReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'course_id'),)


class LessonComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FavoriteCourse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'course_id'),)


class UserBadge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    badge_type = db.Column(db.String(50), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'badge_type'),)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    related_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)


def award_badges(user):
    """Check and award any earned badges. Call after progress or quiz updates."""
    earned_types = {b.badge_type for b in user.badges}

    def _try_award(badge_type):
        if badge_type not in earned_types:
            try:
                db.session.add(UserBadge(user_id=user.id, badge_type=badge_type))
                db.session.flush()
                earned_types.add(badge_type)
            except Exception:
                db.session.rollback()

    total_done = len(user.progress)

    if total_done >= 1:
        _try_award('first_lesson')
    if total_done >= 10:
        _try_award('ten_lessons')

    course_map = {}
    for p in user.progress:
        lesson = Lesson.query.get(p.lesson_id)
        if lesson:
            cid = lesson.course_id
            total = len(lesson.course.lessons)
            if cid not in course_map:
                course_map[cid] = {'total': total, 'done': 0}
            course_map[cid]['done'] += 1

    completed_courses = sum(1 for d in course_map.values()
                            if d['total'] > 0 and d['done'] >= d['total'])
    if completed_courses >= 1:
        _try_award('first_course')
    if completed_courses >= 3:
        _try_award('three_courses')

    for result in user.quiz_results:
        if result.max_score > 0 and result.score == result.max_score:
            _try_award('quiz_perfect')
            break
