import secrets
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (Course, Lesson, Question, Answer, UserProgress, UserQuizResult,
                         Certificate, CourseReview, LessonComment, FavoriteCourse,
                         LessonNote, LessonView, award_badges, update_streak,
                         CommentLike, Assignment, AssignmentSubmission, UserQuizAnswer)

courses_bp = Blueprint('courses', __name__)


@courses_bp.route('/course/<int:course_id>')
def course(course_id):
    course = Course.query.get_or_404(course_id)
    if not course.is_published and not (current_user.is_authenticated and current_user.is_admin):
        flash('Этот курс недоступен', 'warning')
        return redirect(url_for('main.catalog'))

    if current_user.is_authenticated:
        completed_ids = {p.lesson_id for p in current_user.progress}
        certificate = Certificate.query.filter_by(
            user_id=current_user.id, course_id=course_id
        ).first()
        user_review = CourseReview.query.filter_by(
            user_id=current_user.id, course_id=course_id
        ).first()
        is_favorite = FavoriteCourse.query.filter_by(
            user_id=current_user.id, course_id=course_id
        ).first() is not None
    else:
        completed_ids = set()
        certificate = None
        user_review = None
        is_favorite = False

    total = len(course.lessons)
    completed = sum(1 for l in course.lessons if l.id in completed_ids)
    percent = int(completed / total * 100) if total > 0 else 0

    # Related courses: same category, excluding this one
    related = []
    if course.category:
        related = Course.query.filter(
            Course.category == course.category,
            Course.id != course_id,
            Course.is_published == True
        ).limit(3).all()

    return render_template('courses/course.html',
                           course=course,
                           completed_ids=completed_ids,
                           completed=completed,
                           total=total,
                           percent=percent,
                           certificate=certificate,
                           user_review=user_review,
                           is_favorite=is_favorite,
                           related=related)


@courses_bp.route('/lesson/<int:lesson_id>')
def lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    course = lesson.course

    # Check course availability
    if not course.is_published:
        if current_user.is_authenticated and current_user.is_admin:
            pass  # admin can preview unpublished
        elif current_user.is_authenticated:
            flash('Этот курс недоступен', 'warning')
            return redirect(url_for('main.catalog'))
        else:
            return redirect(url_for('auth.login'))

    lessons = list(course.lessons)
    idx = next((i for i, l in enumerate(lessons) if l.id == lesson_id), 0)
    prev_lesson = lessons[idx - 1] if idx > 0 else None
    next_lesson = lessons[idx + 1] if idx < len(lessons) - 1 else None
    is_first = (idx == 0)

    # Non-authenticated: preview first lesson only
    if not current_user.is_authenticated:
        if not is_first:
            flash('Войдите или зарегистрируйтесь для доступа к урокам', 'info')
            return redirect(url_for('auth.login'))
        return render_template('courses/lesson.html',
                               lesson=lesson, course=course,
                               completed_ids=set(),
                               prev_lesson=None,
                               next_lesson=next_lesson,
                               quiz_result=None,
                               preview=True,
                               user_note=None,
                               is_first_lesson=True)

    # Authenticated user
    completed_ids = {p.lesson_id for p in current_user.progress}

    quiz_result = None
    quiz_locked = False
    quiz_unlock_at = None
    if lesson.lesson_type == 'quiz':
        quiz_result = UserQuizResult.query.filter_by(
            user_id=current_user.id, lesson_id=lesson_id
        ).first()
        if lesson.quiz_max_attempts and quiz_result:
            if (quiz_result.attempts or 0) >= lesson.quiz_max_attempts:
                if lesson.quiz_reset_hours:
                    from datetime import timedelta
                    unlock_at = quiz_result.completed_at + timedelta(hours=lesson.quiz_reset_hours)
                    if datetime.utcnow() < unlock_at:
                        quiz_locked = True
                        quiz_unlock_at = unlock_at
                else:
                    quiz_locked = True

    # Track view for history
    view = LessonView.query.filter_by(user_id=current_user.id, lesson_id=lesson_id).first()
    if view:
        view.viewed_at = datetime.utcnow()
    else:
        db.session.add(LessonView(user_id=current_user.id, lesson_id=lesson_id))
    db.session.commit()

    # Personal note
    user_note = LessonNote.query.filter_by(user_id=current_user.id, lesson_id=lesson_id).first()

    return render_template('courses/lesson.html',
                           lesson=lesson,
                           course=course,
                           completed_ids=completed_ids,
                           prev_lesson=prev_lesson,
                           next_lesson=next_lesson,
                           quiz_result=quiz_result,
                           quiz_locked=quiz_locked,
                           quiz_unlock_at=quiz_unlock_at,
                           preview=False,
                           user_note=user_note,
                           is_first_lesson=is_first)


@courses_bp.route('/lesson/<int:lesson_id>/complete', methods=['POST'])
@login_required
def complete_lesson(lesson_id):
    Lesson.query.get_or_404(lesson_id)
    existing = UserProgress.query.filter_by(
        user_id=current_user.id, lesson_id=lesson_id
    ).first()
    if not existing:
        db.session.add(UserProgress(user_id=current_user.id, lesson_id=lesson_id))
        db.session.flush()
        update_streak(current_user)
        award_badges(current_user)
        db.session.commit()
    return jsonify({'success': True, 'streak': current_user.streak_days or 0})


@courses_bp.route('/lesson/<int:lesson_id>/submit-quiz', methods=['POST'])
@login_required
def submit_quiz(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)

    # Check attempt limit
    result = UserQuizResult.query.filter_by(
        user_id=current_user.id, lesson_id=lesson_id
    ).first()

    if lesson.quiz_max_attempts and result:
        attempts_used = result.attempts or 1
        if attempts_used >= lesson.quiz_max_attempts:
            # Check if reset window has passed
            if lesson.quiz_reset_hours:
                from datetime import timedelta
                unlock_at = result.completed_at + timedelta(hours=lesson.quiz_reset_hours)
                if datetime.utcnow() < unlock_at:
                    flash(f'Превышен лимит попыток ({lesson.quiz_max_attempts}). '
                          f'Повтор доступен {unlock_at.strftime("%d.%m %H:%M")} UTC.', 'danger')
                    return redirect(url_for('courses.lesson', lesson_id=lesson_id))
                else:
                    result.attempts = 0
            else:
                flash(f'Превышен лимит попыток ({lesson.quiz_max_attempts}).', 'danger')
                return redirect(url_for('courses.lesson', lesson_id=lesson_id))

    score = 0
    max_score = len(lesson.questions)

    for question in lesson.questions:
        answer_id = request.form.get(f'question_{question.id}')
        is_correct = False
        chosen_answer = None
        if answer_id:
            chosen_answer = Answer.query.get(int(answer_id))
            if chosen_answer and chosen_answer.is_correct:
                score += 1
                is_correct = True
        qa = UserQuizAnswer.query.filter_by(
            user_id=current_user.id, question_id=question.id
        ).first()
        if qa:
            qa.answer_id = chosen_answer.id if chosen_answer else None
            qa.is_correct = is_correct
            qa.answered_at = datetime.utcnow()
        else:
            db.session.add(UserQuizAnswer(
                user_id=current_user.id, question_id=question.id,
                answer_id=chosen_answer.id if chosen_answer else None,
                is_correct=is_correct
            ))

    if result:
        result.score = score
        result.max_score = max_score
        result.completed_at = datetime.utcnow()
        result.attempts = (result.attempts or 0) + 1
    else:
        result = UserQuizResult(
            user_id=current_user.id, lesson_id=lesson_id,
            score=score, max_score=max_score, attempts=1
        )
        db.session.add(result)

    existing = UserProgress.query.filter_by(
        user_id=current_user.id, lesson_id=lesson_id
    ).first()
    if not existing:
        db.session.add(UserProgress(user_id=current_user.id, lesson_id=lesson_id))

    db.session.flush()
    update_streak(current_user)
    award_badges(current_user)
    db.session.commit()

    if score == max_score:
        flash(f'Отлично! Тест завершён: {score}/{max_score} — все ответы верны!', 'success')
    else:
        flash(f'Тест завершён. Ваш результат: {score}/{max_score}', 'info')

    return redirect(url_for('courses.lesson', lesson_id=lesson_id))


# ── Notes ──────────────────────────────────────────────────────────────────────

@courses_bp.route('/lesson/<int:lesson_id>/note', methods=['POST'])
@login_required
def save_note(lesson_id):
    Lesson.query.get_or_404(lesson_id)
    text = request.form.get('note_text', '').strip()
    note = LessonNote.query.filter_by(user_id=current_user.id, lesson_id=lesson_id).first()
    if note:
        note.text = text
        note.updated_at = datetime.utcnow()
    else:
        db.session.add(LessonNote(user_id=current_user.id, lesson_id=lesson_id, text=text))
    db.session.commit()
    return jsonify({'success': True})


# ── Certificate ────────────────────────────────────────────────────────────────

@courses_bp.route('/course/<int:course_id>/certificate')
@login_required
def certificate(course_id):
    course = Course.query.get_or_404(course_id)
    if not course.is_published and not current_user.is_admin:
        return redirect(url_for('main.catalog'))

    completed_ids = {p.lesson_id for p in current_user.progress}
    total = len(course.lessons)
    completed = sum(1 for l in course.lessons if l.id in completed_ids)

    if total == 0 or completed < total:
        flash('Сертификат выдаётся только после прохождения всех уроков курса', 'warning')
        return redirect(url_for('courses.course', course_id=course_id))

    cert = Certificate.query.filter_by(
        user_id=current_user.id, course_id=course_id
    ).first()
    if not cert:
        cert = Certificate(user_id=current_user.id, course_id=course_id)
        db.session.add(cert)
        db.session.commit()

    return render_template('courses/certificate.html', cert=cert, course=course)


# ── Reviews ────────────────────────────────────────────────────────────────────

@courses_bp.route('/course/<int:course_id>/review', methods=['POST'])
@login_required
def review_course(course_id):
    Course.query.get_or_404(course_id)
    rating = int(request.form.get('rating', 0))
    comment = request.form.get('comment', '').strip()

    if rating < 1 or rating > 5:
        flash('Выберите оценку от 1 до 5', 'danger')
        return redirect(url_for('courses.course', course_id=course_id))

    review = CourseReview.query.filter_by(
        user_id=current_user.id, course_id=course_id
    ).first()
    if review:
        review.rating = rating
        review.comment = comment
        review.created_at = datetime.utcnow()
    else:
        review = CourseReview(user_id=current_user.id, course_id=course_id,
                              rating=rating, comment=comment)
        db.session.add(review)
    db.session.commit()
    flash('Отзыв сохранён!', 'success')
    return redirect(url_for('courses.course', course_id=course_id))


@courses_bp.route('/review/<int:review_id>/delete', methods=['POST'])
@login_required
def delete_review(review_id):
    review = CourseReview.query.get_or_404(review_id)
    if review.user_id != current_user.id and not current_user.is_admin:
        flash('Нет доступа', 'danger')
        return redirect(url_for('main.catalog'))
    course_id = review.course_id
    db.session.delete(review)
    db.session.commit()
    flash('Отзыв удалён', 'info')
    return redirect(url_for('courses.course', course_id=course_id))


# ── Comments ───────────────────────────────────────────────────────────────────

@courses_bp.route('/lesson/<int:lesson_id>/comment', methods=['POST'])
@login_required
def add_comment(lesson_id):
    Lesson.query.get_or_404(lesson_id)
    text = request.form.get('text', '').strip()
    if not text:
        flash('Комментарий не может быть пустым', 'warning')
        return redirect(url_for('courses.lesson', lesson_id=lesson_id))
    if len(text) > 2000:
        flash('Комментарий слишком длинный (максимум 2000 символов)', 'warning')
        return redirect(url_for('courses.lesson', lesson_id=lesson_id))
    db.session.add(LessonComment(user_id=current_user.id, lesson_id=lesson_id, text=text))
    db.session.commit()
    return redirect(url_for('courses.lesson', lesson_id=lesson_id) + '#comments')


@courses_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = LessonComment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id and not current_user.is_admin:
        flash('Нет доступа', 'danger')
        return redirect(url_for('main.index'))
    lesson_id = comment.lesson_id
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('courses.lesson', lesson_id=lesson_id) + '#comments')


# ── Favorites ──────────────────────────────────────────────────────────────────

@courses_bp.route('/course/<int:course_id>/favorite', methods=['POST'])
@login_required
def toggle_favorite(course_id):
    Course.query.get_or_404(course_id)
    fav = FavoriteCourse.query.filter_by(
        user_id=current_user.id, course_id=course_id
    ).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        return jsonify({'is_favorite': False})
    else:
        db.session.add(FavoriteCourse(user_id=current_user.id, course_id=course_id))
        db.session.commit()
        return jsonify({'is_favorite': True})


# ── Comment likes ──────────────────────────────────────────────────────────────

@courses_bp.route('/comment/<int:comment_id>/like', methods=['POST'])
@login_required
def like_comment(comment_id):
    from app.models import LessonComment
    LessonComment.query.get_or_404(comment_id)
    like = CommentLike.query.filter_by(
        user_id=current_user.id, comment_id=comment_id
    ).first()
    if like:
        db.session.delete(like)
        liked = False
    else:
        db.session.add(CommentLike(user_id=current_user.id, comment_id=comment_id))
        liked = True
    db.session.commit()
    count = CommentLike.query.filter_by(comment_id=comment_id).count()
    return jsonify({'liked': liked, 'count': count})


# ── Assignments ────────────────────────────────────────────────────────────────

@courses_bp.route('/assignment/<int:assignment_id>/submit', methods=['POST'])
@login_required
def submit_assignment(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)
    text = request.form.get('answer_text', '').strip()
    if not text:
        flash('Напишите ответ перед отправкой', 'warning')
        return redirect(url_for('courses.lesson', lesson_id=a.lesson_id))
    sub = AssignmentSubmission.query.filter_by(
        user_id=current_user.id, assignment_id=assignment_id
    ).first()
    if sub:
        sub.answer_text = text
        sub.submitted_at = datetime.utcnow()
    else:
        db.session.add(AssignmentSubmission(
            user_id=current_user.id, assignment_id=assignment_id, answer_text=text
        ))
    db.session.commit()
    flash('Задание отправлено!', 'success')
    return redirect(url_for('courses.lesson', lesson_id=a.lesson_id))
