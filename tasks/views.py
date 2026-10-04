from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from .forms_regis import RegisterForm
from .models import Test, Topic, AttemptDraft, TestResult
from .services import begin_attempt, submit_attempt

def csrf_failure(request, reason=''):
    return render(request, '403.html', status=403)

@require_GET
def home(request):
    return render(request, 'home.html')

@require_http_methods(['GET', 'POST'])
def register(request):
    form = RegisterForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            form.add_error(None, 'Логин или email уже занят. Проверьте данные.')
        else:
            login(request, user)
            messages.success(request, 'Аккаунт создан. Можно начать тест.')
            return redirect('test_list')
    return render(request, 'register.html', {'form': form})

@require_GET
def test_list(request):
    search = request.GET.get('q', '').strip()[:255]
    topic = request.GET.get('topic', '')
    tests = Test.objects.filter(is_active=True).annotate(question_count=Count('topics__questions', distinct=True)).filter(question_count__gt=0)
    if search:
        tests = tests.filter(title__icontains=search)
    if topic:
        tests = tests.filter(topic=topic)
    return render(request, 'test_list.html', {'tests': tests, 'search': search, 'selected_topic': topic, 'topics': Test.TOPICS})

@require_GET
def test_detail(request, test_id):
    test = get_object_or_404(Test, is_active=True, pk=test_id)
    return render(request, 'test_detail.html', {'test': test, 'question_count': sum((t.questions.count() for t in test.topics.all()))})

@login_required
@require_POST
def start_test(request, test_id):
    test = get_object_or_404(Test, is_active=True, pk=test_id)
    try:
        draft = begin_attempt(request.user, test)
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
        return redirect('test_detail', test_id=test.id)
    return redirect('attempt', attempt_id=draft.id)

def attempt_context(draft, data=None, error=''):
    questions = []
    for item in draft.snapshot:
        key = f"question_{item['id']}"
        selected = data.get(key, '') if data is not None else ''
        questions.append({'id': item['id'], 'text': item['text'], 'answers': [{'id': a['id'], 'text': a['text'], 'selected': str(a['id']) == selected} for a in item['answers']]})
    return {'test': draft.test, 'draft': draft, 'questions': questions, 'error': error, 'has_missing': bool(error and 'Пропущено' in error)}

@login_required
@require_GET
def attempt(request, attempt_id):
    draft = get_object_or_404(AttemptDraft.objects.select_related('test'), pk=attempt_id, user=request.user)
    previous = TestResult.objects.filter(attempt_id=draft.id, user=request.user).first()
    if previous:
        return redirect('result', result_id=previous.id)
    if not draft.test.is_active:
        return render(request, '403.html', status=403)
    return render(request, 'start_test.html', attempt_context(draft))

@login_required
@require_POST
def submit_test(request, test_id):
    try:
        draft_id = request.POST.get('attempt_id', '')
        draft = get_object_or_404(AttemptDraft.objects.select_related('test'), pk=draft_id, user=request.user, test_id=test_id)
    except (ValidationError, ValueError):
        return render(request, '403.html', status=400)
    try:
        saved = submit_attempt(request.user, draft.test, draft.id, request.POST)
    except ValidationError as error:
        return render(request, 'start_test.html', attempt_context(draft, request.POST, ' '.join(error.messages)), status=400)
    return redirect('result', result_id=saved.id)

@login_required
@require_GET
def result(request, result_id):
    saved = get_object_or_404(TestResult.objects.prefetch_related('responses'), pk=result_id, user=request.user)
    return render(request, 'result.html', {'result': saved})

@login_required
@require_GET
def history(request):
    from django.core.paginator import Paginator
    page = Paginator(TestResult.objects.filter(user=request.user).select_related('test'), 20).get_page(request.GET.get('page'))
    return render(request, 'history.html', {'page': page})

@login_required
@require_GET
def legacy_result(request, test_id):
    saved = TestResult.objects.filter(user=request.user, test_id=test_id).first()
    if saved:
        return redirect('result', result_id=saved.id)
    messages.info(request, 'У вас пока нет результатов этого теста.')
    return redirect('test_list')
