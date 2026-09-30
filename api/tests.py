from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from interviews.models import Answer, Interview, Question


def fake_generate_questions(*, question_count, **kwargs):
    labels = ['Soru bir?', 'Soru iki?', 'Soru üç?', 'Soru dört?', 'Soru beş?']
    categories = ['teknik', 'davranissal']
    return [
        (labels[i % len(labels)], categories[i % len(categories)])
        for i in range(question_count)
    ]


def fake_evaluate_answer(**kwargs):
    return {
        'score': 7, 'strengths': 'iyi', 'improvements': 'daha iyi olabilir',
        'sample_answer': 'örnek', 'language_score': None, 'language_feedback': '',
    }


def fake_summarize_interview(**kwargs):
    return {'summary': 'özet', 'top_strength': 'güçlü yön', 'top_improvement': 'gelişim alanı'}


class GeminiMockMixin:
    """api.views'a bağlanmış generate_questions/evaluate_answer ve interviews.views'a bağlanmış
    summarize_interview (mülakat tamamlanınca _complete_interview çağırır) isimlerini geçici
    olarak sahteleriyle değiştirir (interviews/tests.py::GuestTrialTests ile aynı desen)."""

    def setUp(self):
        super().setUp()
        from api import views as api_views
        from interviews import views as interview_views
        self._real_generate = api_views.generate_questions
        self._real_evaluate = api_views.evaluate_answer
        self._real_summarize = interview_views.summarize_interview
        api_views.generate_questions = fake_generate_questions
        api_views.evaluate_answer = fake_evaluate_answer
        interview_views.summarize_interview = fake_summarize_interview
        self.addCleanup(self._restore)

    def _restore(self):
        from api import views as api_views
        from interviews import views as interview_views
        api_views.generate_questions = self._real_generate
        api_views.evaluate_answer = self._real_evaluate
        interview_views.summarize_interview = self._real_summarize


class AuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_creates_user_and_returns_token(self):
        response = self.client.post(reverse('api_register'), {
            'email': 'new@example.com', 'password': 'a-strong-password-1',
            'kvkk_consent': True,
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertIn('token', response.data)
        user = User.objects.get(email='new@example.com')
        self.assertEqual(user.username, 'new@example.com')
        self.assertTrue(user.check_password('a-strong-password-1'))

    def test_register_requires_kvkk_consent(self):
        response = self.client.post(reverse('api_register'), {
            'email': 'x@example.com', 'password': 'a-strong-password-1',
            'kvkk_consent': False,
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('kvkk_consent', response.data['errors'])

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(username='dup@example.com', email='dup@example.com', password='x')
        response = self.client.post(reverse('api_register'), {
            'email': 'dup@example.com', 'password': 'a-strong-password-1',
            'kvkk_consent': True,
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data['errors'])

    def test_login_with_correct_credentials_returns_token(self):
        User.objects.create_user(username='u@example.com', email='u@example.com', password='right-pass')
        response = self.client.post(reverse('api_login'), {
            'email': 'u@example.com', 'password': 'right-pass',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)

    def test_login_with_wrong_password_is_rejected(self):
        User.objects.create_user(username='u2@example.com', email='u2@example.com', password='right-pass')
        response = self.client.post(reverse('api_login'), {
            'email': 'u2@example.com', 'password': 'wrong-pass',
        }, format='json')

        self.assertEqual(response.status_code, 400)

    def test_google_login_creates_user_on_first_call(self):
        from api import views
        original = views.verify_google_credential
        views.verify_google_credential = lambda credential: 'google-user@example.com'
        self.addCleanup(setattr, views, 'verify_google_credential', original)

        response = self.client.post(reverse('api_google_login'), {'credential': 'x'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)
        self.assertTrue(User.objects.filter(email='google-user@example.com').exists())


class InterviewApiTests(GeminiMockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='panel@example.com', email='panel@example.com', password='x'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_requires_authentication(self):
        anon = APIClient()
        response = anon.get(reverse('api_interview_list_create'))
        self.assertEqual(response.status_code, 401)

    def test_empty_list(self):
        response = self.client.get(reverse('api_interview_list_create'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'in_progress': [], 'completed': []})

    def _create_payload(self, **overrides):
        payload = {
            'position': 'junior_developer', 'level': 'junior', 'interview_type': 'technical',
            'language': 'tr', 'question_count': 5, 'custom_position': '', 'job_posting': '',
            'cv_text': '', 'cv_consent': False,
        }
        payload.update(overrides)
        return payload

    def test_create_interview_returns_first_question(self):
        response = self.client.post(
            reverse('api_interview_list_create'), self._create_payload(), format='json'
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['current_question']['text'], 'Soru bir?')
        self.assertEqual(response.data['total_count'], 5)
        self.assertEqual(Question.objects.filter(interview_id=response.data['id']).count(), 5)

    def test_create_interview_rejects_invalid_form(self):
        response = self.client.post(
            reverse('api_interview_list_create'), self._create_payload(position=''), format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('position', response.data['errors'])

    def test_daily_limit_blocks_further_creation(self):
        for _ in range(3):
            Interview.objects.create(
                user=self.user, position='junior_developer', level='junior',
                interview_type='technical', language='tr', question_count=5,
            )

        response = self.client.post(
            reverse('api_interview_list_create'), self._create_payload(), format='json'
        )
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.data['limit_reached'])

    def test_full_answer_flow_completes_interview_and_report(self):
        create_response = self.client.post(
            reverse('api_interview_list_create'), self._create_payload(), format='json'
        )
        interview_id = create_response.data['id']
        total = create_response.data['total_count']
        question_id = create_response.data['current_question']['id']

        detail = self.client.get(reverse('api_interview_detail', args=[interview_id]))
        self.assertEqual(detail.data['status'], 'in_progress')
        self.assertEqual(detail.data['answered_count'], 0)

        for i in range(total):
            response = self.client.post(
                reverse('api_interview_answer', args=[interview_id]),
                {'question_id': question_id, 'text': f'cevabım {i}'}, format='json',
            )
            self.assertEqual(response.status_code, 200)
            is_last = i == total - 1
            self.assertEqual(response.data['done'], is_last)
            if not is_last:
                question_id = response.data['next_question']['id']

        interview = Interview.objects.get(pk=interview_id)
        self.assertEqual(interview.status, 'completed')
        self.assertEqual(interview.overall_score, 7)
        self.assertEqual(Answer.objects.filter(question__interview=interview).count(), total)

        report = self.client.get(reverse('api_interview_report', args=[interview_id]))
        self.assertEqual(report.status_code, 200)
        self.assertEqual(len(report.data['answers']), total)
        self.assertEqual(report.data['answers'][0]['score'], 7)

    def test_answer_rejects_empty_text(self):
        create_response = self.client.post(
            reverse('api_interview_list_create'), self._create_payload(), format='json'
        )
        interview_id = create_response.data['id']
        question_id = create_response.data['current_question']['id']

        response = self.client.post(
            reverse('api_interview_answer', args=[interview_id]),
            {'question_id': question_id, 'text': '   '}, format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_access_another_users_interview(self):
        other = User.objects.create_user(username='other@example.com', email='other@example.com', password='x')
        interview = Interview.objects.create(
            user=other, position='junior_developer', level='junior',
            interview_type='technical', language='tr', question_count=5,
        )

        response = self.client.get(reverse('api_interview_detail', args=[interview.pk]))
        self.assertEqual(response.status_code, 404)


class AbandonedInterviewApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='m@example.com', email='m@example.com', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _interview(self, minutes_old):
        from datetime import timedelta

        from django.utils import timezone

        interview = Interview.objects.create(
            user=self.user, position='backend_developer', level='junior',
            interview_type='mixed', language='tr', question_count=5,
        )
        Interview.objects.filter(pk=interview.pk).update(
            created_at=timezone.now() - timedelta(minutes=minutes_old)
        )
        return interview

    def test_old_questionless_interview_is_deleted_and_reported(self):
        interview = self._interview(minutes_old=30)

        response = self.client.get(f'/api/v1/interviews/{interview.pk}/')

        self.assertEqual(response.status_code, 404)
        self.assertIn('silindi', response.data['detail'])
        self.assertFalse(Interview.objects.filter(pk=interview.pk).exists())

    def test_recent_questionless_interview_reports_still_preparing(self):
        interview = self._interview(minutes_old=1)

        response = self.client.get(f'/api/v1/interviews/{interview.pk}/')

        self.assertEqual(response.status_code, 409)
        self.assertTrue(Interview.objects.filter(pk=interview.pk).exists())

    def test_list_cleans_old_questionless_interviews(self):
        old = self._interview(minutes_old=30)

        response = self.client.get('/api/v1/interviews/')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Interview.objects.filter(pk=old.pk).exists())
