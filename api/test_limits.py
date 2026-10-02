"""API güvenlik sınırları: kimlik doğrulama uç noktalarında hız sınırı, cevap uzunluğu sınırı."""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.google_auth import GoogleTokenError
from interviews.models import MAX_ANSWER_LENGTH, Answer, Interview, Question


class AuthRateLimitTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _post(self, name, data, ip='203.0.113.7'):
        return self.client.post(reverse(name), data, format='json', HTTP_X_FORWARDED_FOR=ip)

    def test_login_is_limited_to_10_attempts_per_hour(self):
        bad = {'email': 'yok@example.com', 'password': 'yanlis-parola-1'}
        codes = [self._post('api_login', bad).status_code for _ in range(11)]
        self.assertEqual(codes[:10], [400] * 10)
        self.assertEqual(codes[10], 429)

    def test_register_is_limited_to_5_attempts_per_hour(self):
        invalid = {'email': 'x@example.com', 'password': 'a-strong-password-1', 'kvkk_consent': False}
        codes = [self._post('api_register', invalid).status_code for _ in range(6)]
        self.assertEqual(codes[:5], [400] * 5)
        self.assertEqual(codes[5], 429)
        self.assertFalse(User.objects.filter(email='x@example.com').exists())

    @patch('api.views.verify_google_credential', side_effect=GoogleTokenError('geçersiz'))
    def test_google_login_is_limited_to_15_attempts_per_hour(self, _mock):
        codes = [self._post('api_google_login', {'credential': 'kotu'}).status_code for _ in range(16)]
        self.assertEqual(codes[:15], [400] * 15)
        self.assertEqual(codes[15], 429)

    def test_limit_is_per_client_ip(self):
        bad = {'email': 'yok@example.com', 'password': 'yanlis-parola-1'}
        for _ in range(11):
            self._post('api_login', bad, ip='203.0.113.7')
        self.assertEqual(self._post('api_login', bad, ip='198.51.100.9').status_code, 400)


class AnswerLengthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u@example.com', email='u@example.com', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        interview = Interview.objects.create(
            user=self.user, position='backend_developer', level='junior',
            interview_type='mixed', language='tr', question_count=5,
        )
        self.questions = [
            Question.objects.create(interview=interview, order=i, text=f'Soru {i}?', category='teknik')
            for i in range(1, 4)
        ]
        self.url = f'/api/v1/interviews/{interview.pk}/answer/'
        result = {
            'score': 7, 'strengths': 'a', 'improvements': 'b', 'sample_answer': 'c',
            'language_score': None, 'language_feedback': '',
        }
        patcher = patch('api.views.evaluate_answer', return_value=result)
        self.evaluate = patcher.start()
        self.addCleanup(patcher.stop)

    def test_too_long_answer_is_rejected_before_gemini(self):
        response = self.client.post(
            self.url, {'question_id': self.questions[0].pk, 'text': 'a' * (MAX_ANSWER_LENGTH + 1)},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(str(MAX_ANSWER_LENGTH), response.data['detail'])
        self.evaluate.assert_not_called()
        self.assertFalse(Answer.objects.exists())

    def test_answer_at_the_limit_is_accepted(self):
        response = self.client.post(
            self.url, {'question_id': self.questions[0].pk, 'text': 'a' * MAX_ANSWER_LENGTH},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(Answer.objects.get().text), MAX_ANSWER_LENGTH)
