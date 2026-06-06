import json
import re

MODEL = 'llama-3.3-70b-versatile'


def _get_client():
    from groq import Groq
    from flask import current_app
    api_key = current_app.config.get('GROQ_API_KEY', '')
    if not api_key:
        raise RuntimeError('GROQ_API_KEY не настроен. Добавьте его в config.py.')
    return Groq(api_key=api_key)


def _generate(prompt: str, max_tokens: int = 2048) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0.7,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()



def search_web(query: str, max_results: int = 4) -> list:
    """Search the web via DuckDuckGo and return snippet list."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results
    except Exception:
        return []


def generate_quiz_questions(lesson_content, lesson_title, num_questions=5, lang='ru'):
    lang_map = {
        'ru': 'на русском языке',
        'kz': 'на казахском языке',
        'en': 'in English',
    }
    lang_str = lang_map.get(lang, 'на русском языке')
    content_block = lesson_content[:4000] if lesson_content else f'Тема урока: {lesson_title}'

    prompt = f"""Создай {num_questions} тестовых вопросов {lang_str} по теме урока «{lesson_title}».

Требования:
- Каждый вопрос содержит ровно 4 варианта ответа
- Ровно один вариант правильный (is_correct: true)
- Вопросы проверяют понимание материала

Верни ТОЛЬКО валидный JSON без markdown-блоков, без пояснений, без текста до и после:
{{
  "questions": [
    {{
      "text": "Текст вопроса?",
      "answers": [
        {{"text": "Правильный ответ", "is_correct": true}},
        {{"text": "Неправильный вариант 1", "is_correct": false}},
        {{"text": "Неправильный вариант 2", "is_correct": false}},
        {{"text": "Неправильный вариант 3", "is_correct": false}}
      ]
    }}
  ]
}}

Текст урока:
{content_block}"""

    text = _generate(prompt)
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    return json.loads(text.strip())


def generate_lesson_content(topic: str, lang: str = 'ru') -> str:
    """Generate HTML lesson content for the given topic."""
    lang_map = {
        'ru': 'на русском языке',
        'kz': 'на казахском языке',
        'en': 'in English',
    }
    lang_str = lang_map.get(lang, 'на русском языке')

    prompt = f"""Создай подробный образовательный урок {lang_str} на тему: «{topic}».

Структура урока:
- Вводный параграф (2-3 предложения о теме)
- 3-5 основных разделов с содержательными заголовками
- В каждом разделе: объяснение + примеры или практические советы
- Краткое заключение

Форматирование — используй ТОЛЬКО следующие HTML-теги:
- <h2> для названий разделов
- <p> для параграфов
- <ul><li> и <ol><li> для списков
- <strong> для ключевых понятий
- <code> для кода и технических терминов (если уместно)
- <blockquote> для важных замечаний (если уместно)

Верни ТОЛЬКО HTML-контент без markdown, без тегов html/body/head/style/script.
Начни прямо с первого тега контента."""

    return _generate(prompt, max_tokens=3000)


def chat_with_lesson(user_message, lesson_content, lesson_title, lang='ru'):
    lang_instr = {
        'ru': 'Отвечай на русском языке. Будь краток и конкретен.',
        'kz': 'Жауапты қазақ тілінде бер. Қысқа және нақты бол.',
        'en': 'Answer in English. Be concise and specific.',
    }.get(lang, 'Отвечай на русском языке.')

    # 1. Lesson text content
    lesson_block = lesson_content[:3500] if lesson_content else ''

    # 2. Web search
    web_block = ''
    web_results = search_web(f'{lesson_title} {user_message}')
    if web_results:
        label = 'Web search results' if lang == 'en' else 'Результаты веб-поиска'
        lines = []
        for r in web_results:
            title = r.get('title', '')
            body = (r.get('body') or '')[:350]
            href = r.get('href', '')
            lines.append(f'• {title}: {body}  [{href}]')
        web_block = f'{label}:\n' + '\n'.join(lines)

    # Build context
    sources = [s for s in [lesson_block, web_block] if s]
    context = '\n\n---\n\n'.join(sources) if sources else '(контекст недоступен)'

    if lang == 'en':
        source_note = 'Use all available sources: lesson content and web search results. If citing a web source, mention the URL briefly.'
    else:
        source_note = 'Используй все доступные источники: текст урока и результаты веб-поиска. При цитировании веб-источника кратко укажи ссылку.'

    prompt = f"""Ты ИИ-ассистент учебной онлайн-платформы. Студент изучает урок «{lesson_title}».
{lang_instr}
{source_note}

{context}

Вопрос студента: {user_message}"""

    return _generate(prompt, max_tokens=2048)
