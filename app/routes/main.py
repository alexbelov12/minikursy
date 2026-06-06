from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Course, Lesson, FavoriteCourse, Notification, BADGE_DEFS

main_bp = Blueprint('main', __name__)


@main_bp.route('/set-lang/<lang_code>')
def set_lang(lang_code):
    if lang_code in ('ru', 'kz', 'en'):
        session['lang'] = lang_code
    return redirect(request.referrer or url_for('main.index'))


@main_bp.route('/')
def index():
    courses = Course.query.filter_by(is_published=True).order_by(Course.created_at.desc()).limit(6).all()
    return render_template('index.html', courses=courses)


@main_bp.route('/catalog')
def catalog():
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    difficulty = request.args.get('difficulty', '').strip()
    sort = request.args.get('sort', 'newest')

    query = Course.query.filter_by(is_published=True)
    if q:
        query = query.filter(
            Course.title.ilike(f'%{q}%') | Course.description.ilike(f'%{q}%') |
            Course.short_description.ilike(f'%{q}%')
        )
    if category:
        query = query.filter_by(category=category)
    if difficulty:
        query = query.filter_by(difficulty=difficulty)

    if sort == 'oldest':
        query = query.order_by(Course.created_at.asc())
    elif sort == 'az':
        query = query.order_by(Course.title.asc())
    else:
        query = query.order_by(Course.created_at.desc())

    courses = query.all()
    if sort == 'lessons':
        courses = sorted(courses, key=lambda c: len(c.lessons), reverse=True)

    all_published = Course.query.filter_by(is_published=True).all()
    categories = sorted({c.category for c in all_published if c.category})
    diff_order = ['beginner', 'intermediate', 'advanced']
    difficulties = [d for d in diff_order if any(c.difficulty == d for c in all_published)]

    favorite_ids = set()
    if current_user.is_authenticated:
        favorite_ids = {f.course_id for f in current_user.favorites}

    return render_template('courses/catalog.html', courses=courses, q=q,
                           category=category, difficulty=difficulty, sort=sort,
                           categories=categories, difficulties=difficulties,
                           favorite_ids=favorite_ids)


@main_bp.route('/profile')
@login_required
def profile():
    completed_lesson_ids = {p.lesson_id for p in current_user.progress}

    course_map = {}
    for p in current_user.progress:
        lesson = Lesson.query.get(p.lesson_id)
        if lesson and lesson.course.is_published:
            cid = lesson.course_id
            if cid not in course_map:
                course_map[cid] = {'course': lesson.course, 'count': 0}
            course_map[cid]['count'] += 1

    courses_progress = []
    for cid, data in course_map.items():
        course = data['course']
        total = len(course.lessons)
        completed = data['count']
        percent = int(completed / total * 100) if total > 0 else 0
        courses_progress.append({
            'course': course,
            'completed': completed,
            'total': total,
            'percent': percent,
            'is_finished': completed == total
        })
    courses_progress.sort(key=lambda x: (-x['percent'], x['course'].title))

    quiz_results = current_user.quiz_results
    total_score = sum(r.score for r in quiz_results)
    total_max = sum(r.max_score for r in quiz_results)
    avg_percent = int(total_score / total_max * 100) if total_max > 0 else 0

    # Favorites
    favorites = [f.course for f in current_user.favorites
                 if f.course.is_published]

    # Badges with definitions
    badges = []
    for b in sorted(current_user.badges, key=lambda x: x.earned_at):
        defn = BADGE_DEFS.get(b.badge_type, {})
        badges.append({'badge': b, 'defn': defn})

    return render_template('profile.html',
                           courses_progress=courses_progress,
                           completed_lessons=len(completed_lesson_ids),
                           quiz_count=len(quiz_results),
                           avg_percent=avg_percent,
                           favorites=favorites,
                           badges=badges)


@main_bp.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).all()
    unread = [n for n in notifs if not n.is_read]
    for n in unread:
        n.is_read = True
    db.session.commit()
    return render_template('main/notifications.html', notifications=notifs)


@main_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def read_all_notifications():
    Notification.query.filter_by(user_id=current_user.id, is_read=False)\
        .update({'is_read': True})
    db.session.commit()
    return jsonify({'ok': True})
