import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, transaction
from django.http import QueryDict
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from .forms_regis import RegisterForm
from .models import Test as Quiz, Topic, Question, Answer, TestResult, AttemptDraft, AttemptAnswer
from .services import begin_attempt, submit_attempt
PASSWORD = 'Fixture-Passphrase-928!'

def quiz(title='Пример', active=True):
    test = Quiz.objects.create(title=title, is_active=active)
    topic = Topic.objects.create(test=test, title='Пример')
    question = Question.objects.create(topic=topic, text='Сколько будет 2 + 2?', explanation='Объяснение: сумма двух двоек равна четырём.')
    correct = Answer.objects.create(question=question, text='4', is_correct=True)
    wrong = Answer.objects.create(question=question, text='5')
    return (test, question, correct, wrong)

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AccountTests(TestCase):

    def payload(self, **extra):
        data = {'username': 'student', 'email': ' Student@Example.com ', 'password1': PASSWORD, 'password2': PASSWORD}
        data.update(extra)
        return data

    def test_registration_normalizes_email_and_hashes_password(self):
        self.assertRedirects(self.client.post(reverse('register'), self.payload()), reverse('test_list'))
        user = User.objects.get(username='student')
        self.assertEqual(user.email, 'student@example.com')
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))

    def test_email_required_and_password_confirmation(self):
        for payload in [self.payload(email=''), self.payload(email='bad-address'), self.payload(password2='other')]:
            response = self.client.post(reverse('register'), payload)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.assertEqual(User.objects.count(), 0)

    def test_duplicate_email_case_insensitive_form_and_database(self):
        User.objects.create_user('existing', 'student@example.com', PASSWORD)
        response = self.client.post(reverse('register'), self.payload())
        self.assertIn('email', response.context['form'].errors)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user('second', 'STUDENT@EXAMPLE.COM', PASSWORD)

    def test_login_password_and_external_next(self):
        User.objects.create_user('student', 'student@example.com', PASSWORD)
        response = self.client.post(reverse('login'), {'username': 'student', 'password': PASSWORD, 'next': 'https://evil.example/path'})
        self.assertRedirects(response, reverse('test_list'))
        self.client.logout()
        bad = self.client.post(reverse('login'), {'username': 'student', 'password': 'wrong'})
        self.assertTrue(bad.context['form'].errors)
        response = self.client.post(reverse('login'), {'username': 'student', 'password': PASSWORD, 'next': reverse('history')})
        self.assertRedirects(response, reverse('history'))

    def test_logout_requires_post(self):
        user = User.objects.create_user('student', password=PASSWORD)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('user_logout')).status_code, 405)
        self.assertRedirects(self.client.post(reverse('user_logout')), reverse('home'))

    def test_standard_password_reset_and_token_one_use(self):
        user = User.objects.create_user('student', 'student@example.com', PASSWORD)
        response = self.client.post(reverse('password_reset'), {'email': 'STUDENT@example.com'})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        import re
        url = re.search('http://testserver(/reset/[^\\s]+)', mail.outbox[0].body).group(1)
        first = self.client.get(url)
        self.assertEqual(first.status_code, 302)
        confirm = self.client.get(first.url)
        self.assertTrue(confirm.context['validlink'])
        changed = self.client.post(first.url, {'new_password1': 'New-Passphrase-482!', 'new_password2': 'New-Passphrase-482!'})
        self.assertRedirects(changed, reverse('password_reset_complete'))
        user.refresh_from_db()
        self.assertTrue(user.check_password('New-Passphrase-482!'))
        self.assertFalse(user.check_password(PASSWORD))
        self.assertFalse(self.client.get(url, follow=True).context['validlink'])

    def test_unknown_email_generic_response_and_no_mail(self):
        self.assertRedirects(self.client.post(reverse('password_reset'), {'email': 'unknown@example.com'}), reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_get_registration_and_reset_do_not_change_data(self):
        self.client.get(reverse('register'))
        self.client.get(reverse('password_reset'))
        self.assertEqual(User.objects.count(), 0)

    def test_anonymous_and_nonstaff_access(self):
        self.assertEqual(self.client.get(reverse('history')).status_code, 302)
        user = User.objects.create_user('student', password=PASSWORD)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/admin/tasks/test/').status_code, 302)

    def test_csrf_is_enforced(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse('register'), self.payload()).status_code, 403)

class AttemptTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('student', 'student@example.com', PASSWORD)
        self.client.force_login(self.user)
        self.test, self.question, self.correct, self.wrong = quiz()

    def start(self):
        response = self.client.post(reverse('start_test', args=[self.test.id]))
        self.assertEqual(response.status_code, 302)
        return AttemptDraft.objects.latest('created_at')

    def data(self, draft, answer=None):
        return {'attempt_id': str(draft.id), f'question_{self.question.id}': str((answer or self.correct).id)}

    def submit(self, draft, data=None):
        return self.client.post(reverse('submit_test', args=[self.test.id]), data or self.data(draft))

    def test_score_and_answer_persist_and_attempt_get_does_not_save_result(self):
        draft = self.start()
        self.assertEqual(TestResult.objects.count(), 0)
        self.client.get(reverse('attempt', args=[draft.id]))
        self.assertEqual(TestResult.objects.count(), 0)
        self.assertEqual(self.submit(draft).status_code, 302)
        result = TestResult.objects.get()
        self.assertEqual((result.score, result.total, result.percentage), (1, 1, 100))
        self.assertEqual(result.responses.get().selected_text, '4')

    def test_wrong_and_missing_answers(self):
        draft = self.start()
        self.submit(draft, self.data(draft, self.wrong))
        self.assertEqual(TestResult.objects.get().score, 0)
        draft = self.start()
        data = {'attempt_id': str(draft.id)}
        response = self.submit(draft, data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(TestResult.objects.count(), 1)
        data['confirm_missing'] = 'yes'
        self.assertEqual(self.submit(draft, data).status_code, 302)
        result = TestResult.objects.order_by('-id').first()
        self.assertEqual(result.score, 0)
        self.assertEqual(result.responses.get().selected_text, '')

    def test_get_submit_and_start_rejected(self):
        for name in ['submit_test', 'start_test']:
            self.assertEqual(self.client.get(reverse(name, args=[self.test.id])).status_code, 405)
        self.assertFalse(TestResult.objects.exists())
        self.assertFalse(AttemptDraft.objects.exists())

    def test_foreign_question_and_answer_and_client_score_rejected(self):
        other, q, answer, wrong = quiz('Другой тест')
        for mutate in [lambda d: d.update({f'question_{q.id}': str(answer.id)}), lambda d: d.update({f'question_{self.question.id}': str(answer.id)}), lambda d: d.update({'score': '100'})]:
            draft = self.start()
            data = self.data(draft)
            mutate(data)
            self.assertEqual(self.submit(draft, data).status_code, 400)
        self.assertFalse(TestResult.objects.exists())

    def test_duplicate_answer_keys_rejected(self):
        draft = self.start()
        data = QueryDict('', mutable=True)
        data['attempt_id'] = str(draft.id)
        data.setlist(f'question_{self.question.id}', [str(self.correct.id), str(self.wrong.id)])
        self.assertEqual(self.submit(draft, dict(data.lists())).status_code, 400)
        self.assertFalse(TestResult.objects.exists())

    def test_retry_is_idempotent_and_refresh_redirects(self):
        draft = self.start()
        first = self.submit(draft)
        second = self.submit(draft, self.data(draft, self.wrong))
        self.assertEqual(first.url, second.url)
        self.assertEqual(TestResult.objects.count(), 1)
        self.assertEqual(AttemptAnswer.objects.count(), 1)
        self.assertRedirects(self.client.get(reverse('attempt', args=[draft.id])), first.url)
        self.start()
        self.assertEqual(AttemptDraft.objects.count(), 2)

    def test_foreign_result_and_draft_forbidden(self):
        draft = self.start()
        self.submit(draft)
        result = TestResult.objects.get()
        user = User.objects.create_user('other', 'other@example.com', PASSWORD)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('result', args=[result.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse('attempt', args=[draft.id])).status_code, 404)
        self.assertEqual(self.submit(draft).status_code, 404)
        self.assertEqual(list(self.client.get(reverse('history')).context['page']), [])

    def test_snapshot_survives_edit_and_delete(self):
        draft = self.start()
        self.submit(draft)
        result = TestResult.objects.get()
        self.question.text = 'Изменённый вопрос'
        self.question.save()
        self.correct.text = 'Новый ответ'
        self.correct.save()
        self.test.title = 'Новое название'
        self.test.save()
        self.test.delete()
        result.refresh_from_db()
        self.assertEqual(result.title_snapshot, 'Пример')
        self.assertIsNone(result.test)
        self.assertEqual(result.responses.get().question_text, 'Сколько будет 2 + 2?')
        self.assertEqual(result.responses.get().correct_text, '4')

    def test_changed_questions_invalidate_unfinished_attempt(self):
        draft = self.start()
        self.question.text = 'Новый вопрос'
        self.question.save()
        self.assertEqual(self.submit(draft).status_code, 400)
        self.assertFalse(TestResult.objects.exists())

    def test_unpublished_or_invalid_tests_blocked(self):
        self.test.is_active = False
        self.test.save()
        self.assertEqual(self.client.post(reverse('start_test', args=[self.test.id])).status_code, 404)
        self.test.is_active = True
        self.test.save()
        self.correct.is_correct = False
        self.correct.save()
        response = self.client.post(reverse('start_test', args=[self.test.id]))
        self.assertRedirects(response, reverse('test_detail', args=[self.test.id]))
        self.assertFalse(AttemptDraft.objects.exists())
        with self.assertRaises(ValidationError):
            self.test.full_clean()

    def test_unfinished_html_has_no_answer_keys_or_explanations(self):
        draft = self.start()
        response = self.client.get(reverse('attempt', args=[draft.id]))
        self.assertNotContains(response, 'Объяснение: сумма двух двоек')
        self.assertNotContains(response, 'is_correct')
        self.assertNotContains(response, '"correct"')
        self.assertNotContains(response, 'Правильный ответ')

    def test_transaction_rolls_back_if_answer_write_fails(self):
        draft = self.start()
        with patch('tasks.services.AttemptAnswer.objects.bulk_create', side_effect=RuntimeError('injected failure')):
            with self.assertRaises(RuntimeError):
                submit_attempt(self.user, self.test, draft.id, QueryDict(f'attempt_id={draft.id}&question_{self.question.id}={self.correct.id}'))
        self.assertFalse(TestResult.objects.exists())
        self.assertFalse(AttemptAnswer.objects.exists())

    def test_catalog_search_filter_and_empty_state(self):
        self.assertContains(self.client.get(reverse('test_list'), {'q': 'Пример'}), 'Пример')
        self.assertContains(self.client.get(reverse('test_list'), {'topic': 'sql'}), 'Тесты не найдены')
        self.test.is_active = False
        self.test.save()
        self.assertNotContains(self.client.get(reverse('test_list')), 'href="/tests/' + str(self.test.id) + '/"')

    def test_empty_legacy_published_test_is_not_offered_in_catalog(self):
        empty = Quiz.objects.create(title='Тест без вопросов', is_active=True)
        response = self.client.get(reverse('test_list'))
        self.assertNotContains(response, 'href="/tests/' + str(empty.id) + '/"')

    def test_expired_attempt_and_malformed_uuid_rejected(self):
        from datetime import timedelta
        from django.utils import timezone
        draft = self.start()
        AttemptDraft.objects.filter(pk=draft.id).update(created_at=timezone.now() - timedelta(hours=13))
        self.assertEqual(self.submit(draft).status_code, 400)
        self.assertEqual(self.client.post(reverse('submit_test', args=[self.test.id]), {'attempt_id': 'bad-uuid'}).status_code, 400)
        self.assertFalse(TestResult.objects.exists())

    def test_legacy_result_has_no_invented_percentage(self):
        saved = TestResult.objects.create(user=self.user, test=self.test, score=3, title_snapshot='Старый тест')
        response = self.client.get(reverse('result', args=[saved.id]))
        self.assertContains(response, 'Процент восстановить достоверно нельзя')
        self.assertIsNone(saved.percentage)

    def test_demo_seed_is_idempotent_and_questions_valid(self):
        call_command('seed_demo', verbosity=0)
        call_command('seed_demo', verbosity=0)
        self.assertEqual(Quiz.objects.exclude(demo_key=None).count(), 4)
        from .services import question_snapshot
        for test in Quiz.objects.exclude(demo_key=None):
            self.assertEqual(len(question_snapshot(test)), 5)

class AdminValidationTests(TestCase):

    def test_new_topic_cannot_be_added_to_published_test(self):
        from .admin import TopicAdminForm
        test, q, a, w = quiz()
        form = TopicAdminForm({'title': 'Новый раздел', 'test': test.id})
        self.assertFalse(form.is_valid())

    def test_publishing_needs_questions_and_one_correct_answer(self):
        empty = Quiz.objects.create(title='Пример')
        empty.is_active = True
        with self.assertRaises(ValidationError):
            empty.full_clean()
        test, q, a, w = quiz(active=False)
        test.is_active = True
        test.full_clean()
        w.is_correct = True
        w.save()
        with self.assertRaises(ValidationError):
            test.full_clean()

    def test_published_answer_inline_validation(self):
        from django.forms.models import inlineformset_factory
        from .admin import AnswerFormSet
        test, q, a, w = quiz()
        factory = inlineformset_factory(Question, Answer, formset=AnswerFormSet, fields=['text', 'is_correct'], extra=0)
        data = {'answers-TOTAL_FORMS': '2', 'answers-INITIAL_FORMS': '2', 'answers-0-id': a.id, 'answers-0-text': '4', 'answers-0-is_correct': 'on', 'answers-1-id': w.id, 'answers-1-text': '5', 'answers-1-is_correct': 'on'}
        formset = factory(data, instance=q)
        self.assertFalse(formset.is_valid())
        self.assertTrue(formset.non_form_errors())

class ErrorPageTests(TestCase):

    @override_settings(DEBUG=False)
    def test_custom_404_and_403_without_debug_details(self):
        self.assertContains(self.client.get('/not-a-real-page/'), 'Страница не найдена', status_code=404)
        from django.test import Client
        self.assertContains(Client(enforce_csrf_checks=True).post(reverse('register'), {}), 'Доступ ограничен', status_code=403)

    def test_custom_500_template(self):
        from django.test import RequestFactory
        from django.views.defaults import server_error
        response = server_error(RequestFactory().get('/'))
        self.assertContains(response, 'Не удалось открыть страницу', status_code=500)

class ConcurrentSubmissionTests(TransactionTestCase):

    def test_simultaneous_submission_stores_one_result(self):
        user = User.objects.create_user('concurrent', 'concurrent@example.com', PASSWORD)
        test, question, correct, wrong = quiz()
        draft = begin_attempt(user, test)

        def run():
            close_old_connections()
            try:
                data = QueryDict(f'attempt_id={draft.id}&question_{question.id}={correct.id}')
                return submit_attempt(User.objects.get(pk=user.pk), Quiz.objects.get(pk=test.pk), draft.id, data).id
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: run(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(TestResult.objects.count(), 1)
        self.assertEqual(AttemptAnswer.objects.count(), 1)
