from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (Course, Lesson, Question, Answer, User, UserProgress,
                         Notification, LessonAttachment, PromoCode,
                         Assignment, AssignmentSubmission, UserQuizAnswer, UserQuizResult)
from app.uploads import save_upload

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Доступ запрещён', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


def _notify_all_users(course):
    users = User.query.filter_by(is_admin=False).all()
    for u in users:
        db.session.add(Notification(
            user_id=u.id,
            type='new_course',
            message=f'Новый курс: {course.title}',
            related_id=course.id
        ))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    courses = Course.query.order_by(Course.created_at.desc()).all()
    return render_template('admin/dashboard.html',
                           courses=courses,
                           courses_count=Course.query.count(),
                           lessons_count=Lesson.query.count(),
                           users_count=User.query.filter_by(is_admin=False).count())


# ── Stats ─────────────────────────────────────────────────────────────────────

@admin_bp.route('/stats')
@login_required
@admin_required
def stats():
    users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all()
    stats_data = []
    for user in users:
        completed = len(user.progress)
        quiz_res = user.quiz_results
        total_score = sum(r.score for r in quiz_res)
        total_max = sum(r.max_score for r in quiz_res)
        avg = int(total_score / total_max * 100) if total_max > 0 else 0
        stats_data.append({
            'user': user,
            'completed': completed,
            'quizzes': len(quiz_res),
            'avg_score': avg
        })

    courses = Course.query.order_by(Course.created_at.desc()).all()
    course_stats = []
    for course in courses:
        lesson_ids = [l.id for l in course.lessons]
        if lesson_ids:
            enrolled = UserProgress.query.filter(
                UserProgress.lesson_id.in_(lesson_ids)
            ).with_entities(UserProgress.user_id).distinct().count()
        else:
            enrolled = 0
        completed_ids_per_user = {p.user_id for p in UserProgress.query.filter(
            UserProgress.lesson_id.in_(lesson_ids)
        ).all()} if lesson_ids else set()
        fully_done = sum(
            1 for uid in completed_ids_per_user
            if all(any(p.lesson_id == lid and p.user_id == uid
                       for p in UserProgress.query.filter_by(user_id=uid).all())
                   for lid in lesson_ids)
        ) if lesson_ids else 0
        course_stats.append({'course': course, 'enrolled': enrolled, 'fully_done': fully_done})

    return render_template('admin/stats.html',
                           stats_data=stats_data,
                           course_stats=course_stats,
                           total_users=len(users),
                           total_completions=UserProgress.query.count())


# ── Courses ────────────────────────────────────────────────────────────────────

@admin_bp.route('/course/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_course():
    if request.method == 'POST':
        is_published = bool(request.form.get('is_published'))
        uploaded = save_upload(request.files.get('cover_image_file'), 'courses')
        cover_image = uploaded or request.form.get('cover_image', '').strip() or None
        from datetime import date as date_type
        deadline_str = request.form.get('deadline', '').strip()
        deadline_val = None
        if deadline_str:
            try:
                deadline_val = date_type.fromisoformat(deadline_str)
            except ValueError:
                pass
        course = Course(
            title=request.form.get('title', '').strip(),
            description=request.form.get('description', '').strip(),
            short_description=request.form.get('short_description', '').strip(),
            cover_image=cover_image,
            category=request.form.get('category', '').strip() or None,
            difficulty=request.form.get('difficulty', '').strip() or None,
            is_published=is_published,
            deadline=deadline_val
        )
        db.session.add(course)
        db.session.flush()
        if is_published:
            _notify_all_users(course)
        db.session.commit()
        flash('Курс успешно создан!', 'success')
        return redirect(url_for('admin.edit_course', course_id=course.id))
    return render_template('admin/course_form.html', course=None)


@admin_bp.route('/course/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        was_published = course.is_published
        course.title = request.form.get('title', '').strip()
        course.description = request.form.get('description', '').strip()
        course.short_description = request.form.get('short_description', '').strip()
        uploaded = save_upload(request.files.get('cover_image_file'), 'courses')
        course.cover_image = uploaded or request.form.get('cover_image', '').strip() or None
        course.category = request.form.get('category', '').strip() or None
        course.difficulty = request.form.get('difficulty', '').strip() or None
        course.is_published = bool(request.form.get('is_published'))
        from datetime import date as date_type
        deadline_str = request.form.get('deadline', '').strip()
        if deadline_str:
            try:
                course.deadline = date_type.fromisoformat(deadline_str)
            except ValueError:
                pass
        else:
            course.deadline = None
        if not was_published and course.is_published:
            _notify_all_users(course)
        db.session.commit()
        flash('Курс обновлён!', 'success')
    return render_template('admin/course_form.html', course=course)


@admin_bp.route('/course/<int:course_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    flash('Курс удалён', 'info')
    return redirect(url_for('admin.dashboard'))


# ── Lessons ────────────────────────────────────────────────────────────────────

@admin_bp.route('/course/<int:course_id>/lesson/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_lesson(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        lesson_type = request.form.get('lesson_type', 'text')
        def _int_or_none(v):
            try: return int(v) if v and v.strip() else None
            except ValueError: return None
        lesson = Lesson(
            course_id=course_id,
            title=request.form.get('title', '').strip(),
            lesson_type=lesson_type,
            content=request.form.get('content', '').strip(),
            video_url=request.form.get('video_url', '').strip(),
            order=int(request.form.get('order') or len(course.lessons)),
            quiz_max_attempts=_int_or_none(request.form.get('quiz_max_attempts')),
            quiz_reset_hours=_int_or_none(request.form.get('quiz_reset_hours'))
        )
        db.session.add(lesson)
        db.session.commit()
        flash('Урок создан!', 'success')
        return redirect(url_for('admin.edit_lesson', lesson_id=lesson.id))
    return render_template('admin/lesson_form.html', course=course, lesson=None,
                           next_order=len(course.lessons))


@admin_bp.route('/lesson/<int:lesson_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if request.method == 'POST':
        def _int_or_none(v):
            try: return int(v) if v and v.strip() else None
            except ValueError: return None
        lesson.title = request.form.get('title', '').strip()
        lesson.lesson_type = request.form.get('lesson_type', 'text')
        lesson.content = request.form.get('content', '').strip()
        lesson.video_url = request.form.get('video_url', '').strip()
        lesson.order = int(request.form.get('order') or lesson.order)
        lesson.quiz_max_attempts = _int_or_none(request.form.get('quiz_max_attempts'))
        lesson.quiz_reset_hours = _int_or_none(request.form.get('quiz_reset_hours'))
        db.session.commit()
        flash('Урок обновлён!', 'success')
    return render_template('admin/lesson_form.html', course=lesson.course, lesson=lesson,
                           next_order=lesson.order)


@admin_bp.route('/lesson/<int:lesson_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    course_id = lesson.course_id
    db.session.delete(lesson)
    db.session.commit()
    flash('Урок удалён', 'info')
    return redirect(url_for('admin.edit_course', course_id=course_id))


# ── Attachments ────────────────────────────────────────────────────────────────

@admin_bp.route('/lesson/<int:lesson_id>/attachment/add', methods=['POST'])
@login_required
@admin_required
def add_attachment(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    name = request.form.get('att_name', '').strip()
    url = request.form.get('att_url', '').strip()
    file_type = request.form.get('att_type', 'link')
    if name and url:
        att = LessonAttachment(
            lesson_id=lesson_id,
            name=name,
            url=url,
            file_type=file_type,
            order=len(lesson.attachments)
        )
        db.session.add(att)
        db.session.commit()
        flash('Файл прикреплён!', 'success')
    else:
        flash('Укажите название и ссылку', 'warning')
    return redirect(url_for('admin.edit_lesson', lesson_id=lesson_id))


@admin_bp.route('/attachment/<int:att_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_attachment(att_id):
    att = LessonAttachment.query.get_or_404(att_id)
    lesson_id = att.lesson_id
    db.session.delete(att)
    db.session.commit()
    flash('Вложение удалено', 'info')
    return redirect(url_for('admin.edit_lesson', lesson_id=lesson_id))


# ── AI Content Generator ───────────────────────────────────────────────────────

@admin_bp.route('/lesson/<int:lesson_id>/ai-generate-content', methods=['POST'])
@login_required
@admin_required
def ai_generate_content(lesson_id):
    Lesson.query.get_or_404(lesson_id)
    topic = request.form.get('topic', '').strip()
    if not topic:
        return jsonify({'error': 'Укажите тему урока'}), 400
    lang = session.get('lang', 'ru')
    try:
        from app.ai import generate_lesson_content
        html = generate_lesson_content(topic, lang)
        return jsonify({'html': html})
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'Ошибка генерации: {e}'}), 500


# ── AI Question Generator ─────────────────────────────────────────────────────

@admin_bp.route('/lesson/<int:lesson_id>/ai-generate', methods=['POST'])
@login_required
@admin_required
def ai_generate_questions(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    num = min(max(int(request.form.get('num_questions', 5)), 1), 10)
    replace = bool(request.form.get('replace_existing'))
    lang = session.get('lang', 'ru')

    try:
        from app.ai import generate_quiz_questions
        data = generate_quiz_questions(lesson.content, lesson.title, num, lang)

        if replace:
            for q in list(lesson.questions):
                db.session.delete(q)
            db.session.flush()

        start_order = 0 if replace else len(lesson.questions)
        generated = data.get('questions', [])
        for i, q_data in enumerate(generated):
            question = Question(
                lesson_id=lesson_id,
                text=q_data['text'],
                order=start_order + i
            )
            db.session.add(question)
            db.session.flush()
            for a_data in q_data.get('answers', []):
                db.session.add(Answer(
                    question_id=question.id,
                    text=a_data['text'],
                    is_correct=bool(a_data.get('is_correct'))
                ))

        db.session.commit()
        flash(f'ИИ сгенерировал {len(generated)} вопросов!', 'success')
    except RuntimeError as e:
        flash(str(e), 'danger')
    except Exception as e:
        flash(f'Ошибка генерации: {e}', 'danger')

    return redirect(url_for('admin.edit_lesson', lesson_id=lesson_id))


# ── Questions ──────────────────────────────────────────────────────────────────

@admin_bp.route('/lesson/<int:lesson_id>/question/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_question(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if request.method == 'POST':
        question = Question(
            lesson_id=lesson_id,
            text=request.form.get('text', '').strip(),
            order=int(request.form.get('order') or len(lesson.questions))
        )
        db.session.add(question)
        db.session.flush()

        texts = request.form.getlist('answer_text[]')
        corrects = set(request.form.getlist('is_correct[]'))
        for i, text in enumerate(texts):
            if text.strip():
                db.session.add(Answer(
                    question_id=question.id,
                    text=text.strip(),
                    is_correct=(str(i) in corrects)
                ))
        db.session.commit()
        flash('Вопрос добавлен!', 'success')
        return redirect(url_for('admin.edit_lesson', lesson_id=lesson_id))
    return render_template('admin/question_form.html', lesson=lesson, question=None,
                           next_order=len(lesson.questions))


@admin_bp.route('/question/<int:question_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_question(question_id):
    question = Question.query.get_or_404(question_id)
    lesson = question.lesson
    if request.method == 'POST':
        question.text = request.form.get('text', '').strip()
        question.order = int(request.form.get('order') or question.order)

        for answer in question.answers:
            db.session.delete(answer)
        db.session.flush()

        texts = request.form.getlist('answer_text[]')
        corrects = set(request.form.getlist('is_correct[]'))
        for i, text in enumerate(texts):
            if text.strip():
                db.session.add(Answer(
                    question_id=question.id,
                    text=text.strip(),
                    is_correct=(str(i) in corrects)
                ))
        db.session.commit()
        flash('Вопрос обновлён!', 'success')
        return redirect(url_for('admin.edit_lesson', lesson_id=lesson.id))
    return render_template('admin/question_form.html', lesson=lesson, question=question,
                           next_order=question.order)


@admin_bp.route('/question/<int:question_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    lesson_id = question.lesson_id
    db.session.delete(question)
    db.session.commit()
    flash('Вопрос удалён', 'info')
    return redirect(url_for('admin.edit_lesson', lesson_id=lesson_id))


# ── Promo Codes ────────────────────────────────────────────────────────────────

@admin_bp.route('/promos')
@login_required
@admin_required
def promo_list():
    promos = PromoCode.query.order_by(PromoCode.created_at.desc()).all()
    return render_template('admin/promo_list.html', promos=promos)


@admin_bp.route('/promos/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_promo():
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        if not code:
            flash('Укажите код', 'danger')
            return render_template('admin/promo_form.html', promo=None)
        if PromoCode.query.filter_by(code=code).first():
            flash('Такой промокод уже существует', 'danger')
            return render_template('admin/promo_form.html', promo=None)
        expires_str = request.form.get('expires_at', '').strip()
        expires_at = None
        if expires_str:
            try:
                expires_at = datetime.strptime(expires_str, '%Y-%m-%d')
            except ValueError:
                pass
        promo = PromoCode(
            code=code,
            description=request.form.get('description', '').strip() or None,
            max_uses=int(request.form.get('max_uses') or 0),
            expires_at=expires_at,
            is_active=bool(request.form.get('is_active'))
        )
        db.session.add(promo)
        db.session.commit()
        flash(f'Промокод «{code}» создан!', 'success')
        return redirect(url_for('admin.promo_list'))
    return render_template('admin/promo_form.html', promo=None)


@admin_bp.route('/promos/<int:promo_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_promo(promo_id):
    promo = PromoCode.query.get_or_404(promo_id)
    promo.is_active = not promo.is_active
    db.session.commit()
    flash(f'Промокод {"активирован" if promo.is_active else "деактивирован"}', 'info')
    return redirect(url_for('admin.promo_list'))


@admin_bp.route('/promos/<int:promo_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_promo(promo_id):
    promo = PromoCode.query.get_or_404(promo_id)
    db.session.delete(promo)
    db.session.commit()
    flash('Промокод удалён', 'info')
    return redirect(url_for('admin.promo_list'))


# ── Analytics ──────────────────────────────────────────────────────────────────

@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics():
    from sqlalchemy import func, cast
    from sqlalchemy.types import Date
    thirty_ago = datetime.utcnow() - timedelta(days=30)
    seven_ago = datetime.utcnow() - timedelta(days=7)

    # Registrations per day (last 30 days)
    reg_rows = db.session.query(
        cast(User.created_at, Date).label('day'),
        func.count(User.id).label('cnt')
    ).filter(User.created_at >= thirty_ago, User.is_admin == False
    ).group_by('day').order_by('day').all()
    reg_labels = [str(r.day) for r in reg_rows]
    reg_data   = [r.cnt for r in reg_rows]

    # Lesson completions per day (last 30 days)
    comp_rows = db.session.query(
        cast(UserProgress.completed_at, Date).label('day'),
        func.count(UserProgress.id).label('cnt')
    ).filter(UserProgress.completed_at >= thirty_ago
    ).group_by('day').order_by('day').all()
    comp_labels = [str(r.day) for r in comp_rows]
    comp_data   = [r.cnt for r in comp_rows]

    # Active users last 7 days
    active_users = db.session.query(UserProgress.user_id).filter(
        UserProgress.completed_at >= seven_ago
    ).distinct().count()

    # Popular courses (top 5 by enrollment)
    all_courses = Course.query.filter_by(is_published=True).all()
    popular = sorted(all_courses, key=lambda c: c.enrolled_count, reverse=True)[:5]
    pop_labels = [c.title[:30] for c in popular]
    pop_data   = [c.enrolled_count for c in popular]

    # Totals
    total_users = User.query.filter_by(is_admin=False).count()
    total_completions = UserProgress.query.count()
    total_courses = Course.query.filter_by(is_published=True).count()

    return render_template('admin/analytics.html',
                           reg_labels=reg_labels, reg_data=reg_data,
                           comp_labels=comp_labels, comp_data=comp_data,
                           pop_labels=pop_labels, pop_data=pop_data,
                           active_users=active_users,
                           total_users=total_users,
                           total_completions=total_completions,
                           total_courses=total_courses)


# ── Assignments ────────────────────────────────────────────────────────────────

@admin_bp.route('/lesson/<int:lesson_id>/assignment/add', methods=['POST'])
@login_required
@admin_required
def add_assignment(lesson_id):
    Lesson.query.get_or_404(lesson_id)
    title = request.form.get('title', '').strip()
    desc  = request.form.get('description', '').strip()
    if not title:
        flash('Введите название задания', 'danger')
    else:
        db.session.add(Assignment(lesson_id=lesson_id, title=title, description=desc or None))
        db.session.commit()
        flash('Задание добавлено', 'success')
    return redirect(url_for('admin.edit_lesson', lesson_id=lesson_id))


@admin_bp.route('/assignment/<int:assignment_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_assignment(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)
    lesson_id = a.lesson_id
    db.session.delete(a)
    db.session.commit()
    flash('Задание удалено', 'info')
    return redirect(url_for('admin.edit_lesson', lesson_id=lesson_id))


@admin_bp.route('/assignment/<int:assignment_id>/submissions')
@login_required
@admin_required
def assignment_submissions(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)
    return render_template('admin/submissions.html', assignment=a)


# ── Quiz stats ─────────────────────────────────────────────────────────────────

@admin_bp.route('/lesson/<int:lesson_id>/quiz-stats')
@login_required
@admin_required
def quiz_stats(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    stats = []
    total_attempts = UserQuizResult.query.filter_by(lesson_id=lesson_id).count()
    for q in lesson.questions:
        total_answers = UserQuizAnswer.query.filter_by(question_id=q.id).count()
        correct = UserQuizAnswer.query.filter_by(question_id=q.id, is_correct=True).count()
        pct = round(correct / total_answers * 100) if total_answers else 0
        stats.append({'question': q, 'total': total_answers, 'correct': correct, 'pct': pct})
    return render_template('admin/quiz_stats.html',
                           lesson=lesson, stats=stats, total_attempts=total_attempts)
