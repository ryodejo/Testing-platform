import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

class Test(models.Model):
    TOPICS = [('math', 'Математика'), ('history', 'История'), ('it', 'Информационные технологии'), ('python', 'Python'), ('sql', 'SQL'), ('web', 'Web / HTTP'), ('testing', 'Тестирование ПО')]
    title = models.CharField('Название теста', max_length=255)
    description = models.TextField('Описание', blank=True, null=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    difficulty = models.CharField('Сложность', max_length=10, choices=[('easy', 'Легкий'), ('medium', 'Средний'), ('hard', 'Сложный')], default='medium')
    is_active = models.BooleanField('Опубликован', default=False)
    time_limit = models.PositiveIntegerField('Рекомендуемое время (минуты)', default=30)
    topic = models.CharField('Тема', max_length=10, choices=TOPICS, default='math')
    demo_key = models.CharField(max_length=40, blank=True, null=True, unique=True, editable=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Тест'
        verbose_name_plural = 'Тесты'

    def __str__(self):
        return self.title

    def clean(self):
        if self.is_active:
            from .services import question_snapshot
            if not self.pk:
                raise ValidationError({'is_active': 'Сначала сохраните черновик и добавьте вопросы.'})
            try:
                question_snapshot(self)
            except ValidationError as error:
                raise ValidationError({'is_active': error.messages})

class Topic(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='topics')
    title = models.CharField(max_length=255)

    class Meta:
        verbose_name = 'Раздел теста'
        verbose_name_plural = 'Разделы тестов'

    def __str__(self):
        return f'{self.title} ({self.test.title})'

class Question(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    explanation = models.TextField('Объяснение ответа', blank=True)

    def __str__(self):
        return self.text[:80]

class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text[:80]

class AttemptDraft(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

class TestResult(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    test = models.ForeignKey(Test, on_delete=models.SET_NULL, null=True, blank=True)
    score = models.PositiveIntegerField()
    total = models.PositiveIntegerField(null=True, blank=True)
    title_snapshot = models.CharField(max_length=255, blank=True)
    attempt_id = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-completed_at', '-id']
        constraints = [models.CheckConstraint(condition=models.Q(total__isnull=True) | models.Q(score__lte=models.F('total')), name='result_score_within_total')]

    @property
    def percentage(self):
        return round(self.score * 100 / self.total) if self.total else None

    @property
    def verdict(self):
        if self.total is None:
            return 'Исторический результат'
        return 'Отличный результат' if self.percentage >= 80 else 'Хорошая основа' if self.percentage >= 50 else 'Есть над чем поработать'

    def __str__(self):
        return f'{self.user.username} — {self.title_snapshot} ({self.score})'

class AttemptAnswer(models.Model):
    result = models.ForeignKey(TestResult, on_delete=models.CASCADE, related_name='responses')
    question_id_snapshot = models.PositiveBigIntegerField()
    question_text = models.TextField()
    selected_text = models.TextField(blank=True)
    correct_text = models.TextField()
    explanation = models.TextField('Объяснение ответа', blank=True)
    is_correct = models.BooleanField()
    options = models.JSONField(default=list)

    class Meta:
        ordering = ['id']
        constraints = [models.UniqueConstraint(fields=['result', 'question_id_snapshot'], name='one_response_per_question')]
