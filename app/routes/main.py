from datetime import datetime
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from app import db
from app.models import (Course, Lesson, FavoriteCourse, Notification, BADGE_DEFS,
                         User, UserProgress, LessonView, UserBadge, PromoCode, UserPromoCode)
from app.uploads import save_upload

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
        lesson_course_ids = db.session.query(Lesson.course_id).filter(
            Lesson.title.ilike(f'%{q}%') | Lesson.content.ilike(f'%{q}%')
        ).subquery()
        query = query.filter(
            Course.title.ilike(f'%{q}%') |
            Course.description.ilike(f'%{q}%') |
            Course.short_description.ilike(f'%{q}%') |
            Course.id.in_(lesson_course_ids)
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

    favorites = [f.course for f in current_user.favorites if f.course.is_published]

    badges = []
    for b in sorted(current_user.badges, key=lambda x: x.earned_at):
        defn = BADGE_DEFS.get(b.badge_type, {})
        badges.append({'badge': b, 'defn': defn})

    # Recent lesson history (last 10 viewed)
    recent_views = LessonView.query.filter_by(user_id=current_user.id)\
        .order_by(LessonView.viewed_at.desc()).limit(10).all()
    recent_history = []
    for v in recent_views:
        lesson = Lesson.query.get(v.lesson_id)
        if lesson and lesson.course.is_published:
            recent_history.append({'lesson': lesson, 'viewed_at': v.viewed_at})

    # Applied promo codes
    used_promos = UserPromoCode.query.filter_by(user_id=current_user.id).all()

    # Referral
    from flask import request as req
    from app.models import User as UserModel
    referral_count = UserModel.query.filter_by(referred_by_id=current_user.id).count()
    referral_link = req.host_url.rstrip('/') + url_for('auth.register') + \
        '?ref=' + (current_user.referral_code or '')

    return render_template('profile.html',
                           courses_progress=courses_progress,
                           completed_lessons=len(completed_lesson_ids),
                           quiz_count=len(quiz_results),
                           avg_percent=avg_percent,
                           favorites=favorites,
                           badges=badges,
                           recent_history=recent_history,
                           used_promos=used_promos,
                           referral_link=referral_link,
                           referral_count=referral_count)


@main_bp.route('/profile/avatar', methods=['POST'])
@login_required
def update_avatar():
    uploaded = save_upload(request.files.get('avatar_file'), 'avatars')
    if uploaded:
        current_user.avatar_url = uploaded
    elif 'remove_avatar' in request.form:
        current_user.avatar_url = None
    db.session.commit()
    flash('Аватар обновлён!', 'success')
    return redirect(url_for('main.profile'))


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


@main_bp.route('/leaderboard')
def leaderboard():
    users = User.query.filter_by(is_admin=False).all()
    board = []
    for user in users:
        completed_lessons = len(user.progress)
        if completed_lessons == 0:
            continue
        # Count fully completed courses
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
        board.append({
            'user': user,
            'completed_lessons': completed_lessons,
            'completed_courses': completed_courses,
            'badges_count': len(user.badges),
            'streak': user.streak_days or 0,
        })

    board.sort(key=lambda x: (-x['completed_lessons'], -x['completed_courses'], -x['badges_count']))
    return render_template('main/leaderboard.html', board=board[:50])


@main_bp.route('/promo', methods=['GET', 'POST'])
@login_required
def apply_promo():
    if request.method == 'POST':
        code_str = request.form.get('code', '').strip().upper()
        promo = PromoCode.query.filter_by(code=code_str, is_active=True).first()

        if not promo:
            flash('Промокод не найден или недействителен', 'danger')
        elif promo.expires_at and promo.expires_at < datetime.utcnow():
            flash('Срок действия промокода истёк', 'warning')
        elif promo.max_uses > 0 and promo.uses_count >= promo.max_uses:
            flash('Промокод исчерпан', 'warning')
        else:
            existing = UserPromoCode.query.filter_by(
                user_id=current_user.id, promo_code_id=promo.id
            ).first()
            if existing:
                flash('Вы уже использовали этот промокод', 'info')
            else:
                db.session.add(UserPromoCode(user_id=current_user.id, promo_code_id=promo.id))
                promo.uses_count += 1
                # Award promo_member badge if not already earned
                has_badge = UserBadge.query.filter_by(
                    user_id=current_user.id, badge_type='promo_member'
                ).first()
                if not has_badge:
                    db.session.add(UserBadge(user_id=current_user.id, badge_type='promo_member'))
                db.session.commit()
                desc = f' — {promo.description}' if promo.description else ''
                flash(f'Промокод «{promo.code}» активирован!{desc}', 'success')
                return redirect(url_for('main.apply_promo'))

    used_promos = UserPromoCode.query.filter_by(user_id=current_user.id).all()
    return render_template('main/promo.html', used_promos=used_promos)
