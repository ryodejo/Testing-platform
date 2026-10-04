from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from .models import Test, Topic, Question, Answer, TestResult, AttemptAnswer

class AnswerFormSet(BaseInlineFormSet):

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        choices = [f.cleaned_data for f in self.forms if f.cleaned_data and (not f.cleaned_data.get('DELETE'))]
        if self.instance.topic_id and self.instance.topic.test.is_active:
            if len(choices) < 2 or sum((bool(c.get('is_correct')) for c in choices)) != 1:
                raise ValidationError('Опубликованный вопрос: минимум два варианта и ровно один правильный ответ.')

class PublishedInlineFormSet(BaseInlineFormSet):

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        test = self.instance if isinstance(self.instance, Test) else self.instance.test
        if test.is_active and any((f.has_changed() for f in self.forms)):
            raise ValidationError('Сначала снимите тест с публикации, затем меняйте его структуру.')

class TopicInline(admin.TabularInline):
    model = Topic
    extra = 0
    show_change_link = True
    formset = PublishedInlineFormSet

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    show_change_link = True
    formset = PublishedInlineFormSet

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 2
    formset = AnswerFormSet

class TopicAdminForm(forms.ModelForm):

    class Meta:
        model = Topic
        fields = '__all__'

    def clean(self):
        data = super().clean()
        test = data.get('test')
        if not self.instance.pk and test and test.is_active:
            raise ValidationError('Чтобы добавить раздел, сначала снимите тест с публикации.')
        return data

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ['title', 'topic', 'difficulty', 'is_active', 'updated_at']
    list_filter = ['is_active', 'topic', 'difficulty']
    search_fields = ['title', 'description']
    inlines = [TopicInline]

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    form = TopicAdminForm
    list_display = ['title', 'test']
    search_fields = ['title', 'test__title']
    list_filter = ['test__topic']
    inlines = [QuestionInline]

    def get_readonly_fields(self, request, obj=None):
        return ['test'] if obj else []

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (obj is None or not obj.test.is_active)
    actions = None

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text', 'topic']
    search_fields = ['text']
    list_filter = ['topic__test']
    inlines = [AnswerInline]

    def get_readonly_fields(self, request, obj=None):
        return ['topic'] if obj else []

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (obj is None or not obj.topic.test.is_active)
    actions = None

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['text', 'question', 'is_correct']
    search_fields = ['text', 'question__text']
    list_filter = ['is_correct', 'question__topic__test']
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return ['question'] if obj else []

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (obj is None or not obj.question.topic.test.is_active)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (obj is None or not obj.question.topic.test.is_active)

class ResponseInline(admin.TabularInline):
    model = AttemptAnswer
    extra = 0
    can_delete = False
    readonly_fields = ['question_text', 'selected_text', 'correct_text', 'explanation', 'is_correct']
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(TestResult)
class ResultAdmin(admin.ModelAdmin):
    list_display = ['user', 'title_snapshot', 'score', 'total', 'completed_at']
    list_filter = ['completed_at']
    search_fields = ['user__username', 'title_snapshot']
    inlines = [ResponseInline]
    readonly_fields = ['user', 'test', 'score', 'total', 'title_snapshot', 'attempt_id', 'completed_at']
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
admin.site.site_header = 'Testing Platform · Управление'
admin.site.site_title = 'Testing Platform'
admin.site.index_title = 'Учебные материалы'
