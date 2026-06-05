from flask import Blueprint, request, jsonify, session
from flask_login import login_required
from app.models import Lesson

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/chat', methods=['POST'])
@login_required
def ai_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    lesson_id = data.get('lesson_id')

    if not message:
        return jsonify({'error': 'Пустое сообщение'}), 400
    if not lesson_id:
        return jsonify({'error': 'lesson_id обязателен'}), 400

    lesson = Lesson.query.get_or_404(lesson_id)
    lang = session.get('lang', 'ru')

    try:
        from app.ai import chat_with_lesson
        reply = chat_with_lesson(
            message, lesson.content or '', lesson.title,
            lang=lang
        )
        return jsonify({'response': reply})
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception:
        return jsonify({'error': 'Ошибка ИИ-сервиса. Попробуйте позже.'}), 500
