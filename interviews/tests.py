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


class ContactEmailTests(TestCase):
    def test_public_pages_show_app_contact_email_only(self):
        for name in ('home', 'privacy', 'kvkk'):
            response = self.client.get(reverse(name))
            self.assertContains(response, 'mulakatsimulatoru%40gmail.com' if name == 'home'
                                else 'mailto:mulakatsimulatoru@gmail.com')
            self.assertNotContains(response, 'turkensar07')


class RepeatInterviewTests(TestCase):
    def setUp(self):
        from .models import Interview

        self.user = User.objects.create_user(username='t@example.com', email='t@example.com', password='x')
        self.interview = Interview.objects.create(
            user=self.user, position='other', custom_position='Hemşire, özel hastane',
            level='junior', interview_type='behavioral', language='en', question_count=8,
            job_posting='İlan metni ' * 10, cv_based=True, status='completed',
        )
        self.client.force_login(self.user)

    def test_report_offers_repeat_link(self):
        response = self.client.get(reverse('interview_report', args=[self.interview.pk]))
        self.assertContains(response, f'?tekrar={self.interview.pk}')

    def test_repeat_prefills_previous_settings(self):
        response = self.client.get(reverse('interview_create') + f'?tekrar={self.interview.pk}')
        form = response.context['form']
        self.assertEqual(form['position'].value(), 'other')
        self.assertEqual(form['custom_position'].value(), 'Hemşire, özel hastane')
        self.assertEqual(form['interview_type'].value(), 'behavioral')
        self.assertEqual(form['language'].value(), 'en')
        self.assertEqual(form['question_count'].value(), 8)
        self.assertContains(response, 'yeniden yapıştırman gerekiyor')

    def test_cannot_repeat_someone_elses_interview(self):
        other = User.objects.create_user(username='o@example.com', email='o@example.com', password='x')
        self.client.force_login(other)
        response = self.client.get(reverse('interview_create') + f'?tekrar={self.interview.pk}')
        self.assertIsNone(response.context.get('repeat_from'))
        self.assertNotContains(response, 'Hemşire')

    def test_bad_repeat_param_is_ignored(self):
        response = self.client.get(reverse('interview_create') + '?tekrar=abc')
        self.assertEqual(response.status_code, 200)
