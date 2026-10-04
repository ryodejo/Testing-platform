from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Question, AttemptDraft, TestResult, AttemptAnswer

def question_snapshot(test):
    """Проверить структуру теста и получить серверный снимок вопросов."""
    questions = list(Question.objects.filter(topic__test=test).order_by('id').prefetch_related('answers'))
    if not questions:
        raise ValidationError('У теста пока нет вопросов.')
    if len(questions) > 100:
        raise ValidationError('В одном тесте допускается до 100 вопросов.')
    result = []
    for question in questions:
        answers = list(question.answers.all())
        if not question.text.strip() or len(answers) < 2 or sum((a.is_correct for a in answers)) != 1 or any((not a.text.strip() for a in answers)):
            raise ValidationError('Каждый вопрос должен иметь минимум два варианта и ровно один правильный ответ.')
        result.append({'id': question.id, 'text': question.text, 'explanation': question.explanation, 'answers': [{'id': a.id, 'text': a.text, 'correct': a.is_correct} for a in sorted(answers, key=lambda a: a.id)]})
    return result

def begin_attempt(user, test):
    """Создать черновик после POST; правильные ответы остаются только на сервере."""
    if not test.is_active:
        raise ValidationError('Тест не опубликован.')
    return AttemptDraft.objects.create(user=user, test=test, snapshot=question_snapshot(test))

def submit_attempt(user, test, draft_id, data):
    """Сохранить результат и ответы атомарно. SQLite IMMEDIATE сериализует повторные отправки."""
    with transaction.atomic():
        draft = AttemptDraft.objects.select_related('test').get(pk=draft_id, user=user, test=test)
        previous = TestResult.objects.filter(attempt_id=draft.id, user=user).first()
        if previous:
            return previous
        test.refresh_from_db()
        if not test.is_active:
            raise ValidationError('Тест не опубликован.')
        if draft.created_at < timezone.now() - timedelta(hours=12):
            raise ValidationError('Попытка истекла. Начните тест заново.')
        if question_snapshot(test) != draft.snapshot:
            raise ValidationError('Вопросы изменились. Начните тест заново.')
        allowed = {'csrfmiddlewaretoken', 'attempt_id', 'confirm_missing'} | {f"question_{q['id']}" for q in draft.snapshot}
        if set(data) - allowed:
            raise ValidationError('Форма содержит неизвестные вопросы или поля.')
        selections = {}
        for question in draft.snapshot:
            key = f"question_{question['id']}"
            values = data.getlist(key)
            if len(values) > 1:
                raise ValidationError('У вопроса может быть только один выбранный ответ.')
            value = values[0] if values else ''
            if value and value not in {str(a['id']) for a in question['answers']}:
                raise ValidationError('Выбранный ответ не относится к этому вопросу.')
            selections[question['id']] = value
        missing = sum((not v for v in selections.values()))
        if missing and data.get('confirm_missing') != 'yes':
            raise ValidationError(f'Пропущено вопросов: {missing}. Выберите ответы или подтвердите отправку с пропусками.')
        responses = []
        for question in draft.snapshot:
            correct = next((a for a in question['answers'] if a['correct']))
            selected = next((a for a in question['answers'] if str(a['id']) == selections[question['id']]), None)
            responses.append(AttemptAnswer(question_id_snapshot=question['id'], question_text=question['text'], selected_text=selected['text'] if selected else '', correct_text=correct['text'], explanation=question['explanation'], is_correct=selected is not None and selected['id'] == correct['id'], options=question['answers']))
        result = TestResult.objects.create(user=user, test=test, score=sum((r.is_correct for r in responses)), total=len(responses), title_snapshot=test.title, attempt_id=draft.id)
        for response in responses:
            response.result = result
        AttemptAnswer.objects.bulk_create(responses)
        return result
