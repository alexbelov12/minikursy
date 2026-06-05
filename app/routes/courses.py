from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Course, Lesson, Question, Answer, UserProgress, UserQuizResult

courses_bp = Blueprint('courses', __name__)

@courses_bp.route('/course/<int:course_id>')
@login_required
def course(course_id):
    course = Course.query.get_or_404(course_id)
    if not course.is_published and not current_user.is_admin:
        flash('Этот курс недоступен', 'warning')
        return redirect(url_for('main.catalog'))

    completed_ids = {p.lesson_id for p in current_user.progress}
    total = len(course.lessons)
    completed = sum(1 for l in course.lessons if l.id in completed_ids)
    percent = int(completed / total * 100) if total > 0 else 0

    return render_template('courses/course.html',
                           course=course,
                           completed_ids=completed_ids,
                           completed=completed,
                           total=total,
                           percent=percent)

@courses_bp.route('/lesson/<int:lesson_id>')
@login_required
def lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    course = lesson.course

    if not course.is_published and not current_user.is_admin:
        flash('Этот курс недоступен', 'warning')
        return redirect(url_for('main.catalog'))

    completed_ids = {p.lesson_id for p in current_user.progress}
    lessons = list(course.lessons)
    idx = next((i for i, l in enumerate(lessons) if l.id == lesson_id), 0)
    prev_lesson = lessons[idx - 1] if idx > 0 else None
    next_lesson = lessons[idx + 1] if idx < len(lessons) - 1 else None

    quiz_result = None
    if lesson.lesson_type == 'quiz':
        quiz_result = UserQuizResult.query.filter_by(
            user_id=current_user.id, lesson_id=lesson_id
        ).first()

    return render_template('courses/lesson.html',
                           lesson=lesson,
                           course=course,
                           completed_ids=completed_ids,
                           prev_lesson=prev_lesson,
                           next_lesson=next_lesson,
                           quiz_result=quiz_result)

@courses_bp.route('/lesson/<int:lesson_id>/complete', methods=['POST'])
@login_required
def complete_lesson(lesson_id):
    Lesson.query.get_or_404(lesson_id)
    existing = UserProgress.query.filter_by(
        user_id=current_user.id, lesson_id=lesson_id
    ).first()
    if not existing:
        db.session.add(UserProgress(user_id=current_user.id, lesson_id=lesson_id))
        db.session.commit()
    return jsonify({'success': True})

@courses_bp.route('/lesson/<int:lesson_id>/submit-quiz', methods=['POST'])
@login_required
def submit_quiz(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)

    score = 0
    max_score = len(lesson.questions)

    for question in lesson.questions:
        answer_id = request.form.get(f'question_{question.id}')
        if answer_id:
            answer = Answer.query.get(int(answer_id))
            if answer and answer.is_correct:
                score += 1

    result = UserQuizResult.query.filter_by(
        user_id=current_user.id, lesson_id=lesson_id
    ).first()

    if result:
        result.score = score
        result.max_score = max_score
        result.completed_at = datetime.utcnow()
    else:
        result = UserQuizResult(
            user_id=current_user.id, lesson_id=lesson_id,
            score=score, max_score=max_score
        )
        db.session.add(result)

    existing = UserProgress.query.filter_by(
        user_id=current_user.id, lesson_id=lesson_id
    ).first()
    if not existing:
        db.session.add(UserProgress(user_id=current_user.id, lesson_id=lesson_id))

    db.session.commit()

    if score == max_score:
        flash(f'Отлично! Тест завершён: {score}/{max_score} — все ответы верны!', 'success')
    else:
        flash(f'Тест завершён. Ваш результат: {score}/{max_score}', 'info')

    return redirect(url_for('courses.lesson', lesson_id=lesson_id))
