from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from . import guest_views


def fake_generate_questions(**kwargs):
    return [('Soru bir?', 'technical'), ('Soru iki?', 'behavioral')]


def fake_evaluate_answer(**kwargs):
    return {
        'score': 7, 'strengths': 'iyi', 'improvements': 'daha iyi olabilir',
        'sample_answer': 'örnek', 'language_score': None, 'language_feedback': None,
    }


class GuestTrialTests(TestCase):
    def setUp(self):
        self._real_generate = guest_views.generate_questions
        self._real_evaluate = guest_views.evaluate_answer
        guest_views.generate_questions = fake_generate_questions
        guest_views.evaluate_answer = fake_evaluate_answer

    def tearDown(self):
        guest_views.generate_questions = self._real_generate
        guest_views.evaluate_answer = self._real_evaluate

    def test_authenticated_user_is_redirected_to_real_create(self):
        User.objects.create_user(username='u@example.com', email='u@example.com', password='x', is_active=True)
        self.client.force_login(User.objects.get(username='u@example.com'))

        response = self.client.post(reverse('guest_trial_start'))
        self.assertRedirects(response, reverse('interview_create'))

    def test_start_creates_session_and_shows_first_question(self):
        self.client.post(reverse('guest_trial_start'))
        response = self.client.get(reverse('guest_trial'))

        self.assertContains(response, 'Soru bir?')
        self.assertContains(response, '1')

    def test_full_flow_reaches_result_with_average_score(self):
        self.client.post(reverse('guest_trial_start'))

        r1 = self.client.post(reverse('guest_trial_answer'), {'answer': 'cevap bir'})
        self.assertRedirects(r1, reverse('guest_trial'))

        response = self.client.get(reverse('guest_trial'))
        self.assertContains(response, 'Soru iki?')

        r2 = self.client.post(reverse('guest_trial_answer'), {'answer': 'cevap iki'})
        self.assertEqual(r2.status_code, 302)
        self.assertEqual(r2.url, reverse('guest_trial_result'))

        result = self.client.get(reverse('guest_trial_result'))
        self.assertContains(result, '7,0')

        # Sonuç görüntülendikten sonra oturum temizlenir, tekrar erişim anasayfaya döner.
        second_visit = self.client.get(reverse('guest_trial_result'))
        self.assertRedirects(second_visit, reverse('home'))

    def test_empty_answer_rejected(self):
        self.client.post(reverse('guest_trial_start'))
        response = self.client.post(reverse('guest_trial_answer'), {'answer': '   '}, follow=True)

        self.assertContains(response, 'Cevap boş olamaz.')

    def test_guest_trial_without_session_redirects_home(self):
        response = self.client.get(reverse('guest_trial'))
        self.assertRedirects(response, reverse('home'))
