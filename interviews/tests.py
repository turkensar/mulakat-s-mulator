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


FETCH = {'HTTP_X_REQUESTED_WITH': 'fetch'}
CREATE_DATA = {
    'position': 'junior_developer', 'level': 'junior', 'interview_type': 'technical',
    'language': 'tr', 'question_count': '5', 'job_posting': '', 'cv_text': '', 'custom_position': '',
}


class AsyncCreateTests(TestCase):
    def setUp(self):
        from unittest.mock import patch

        self.user = User.objects.create_user(username='a@example.com', email='a@example.com', password='x')
        self.client.force_login(self.user)
        self.patch = patch('interviews.views.generate_questions', side_effect=fake_generate_questions)
        self.mock = self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_success_returns_redirect_json(self):
        response = self.client.post(reverse('interview_create'), CREATE_DATA, **FETCH)
        interview = self.user.interviews.get()
        self.assertEqual(response.json(), {'redirect': reverse('interview_detail', args=[interview.pk])})
        self.assertEqual(interview.questions.count(), 2)

    def test_invalid_form_asks_for_native_resubmit(self):
        response = self.client.post(reverse('interview_create'), {**CREATE_DATA, 'position': ''}, **FETCH)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'invalid': True})
        self.mock.assert_not_called()

    def test_slow_ai_returns_error_json_and_frees_daily_slot(self):
        from .services.gemini import GeminiTimeoutError

        self.mock.side_effect = GeminiTimeoutError('yavaş')
        response = self.client.post(reverse('interview_create'), CREATE_DATA, **FETCH)
        self.assertEqual(response.status_code, 503)
        self.assertIn('yavaş ya da yoğun', response.json()['error'])
        self.assertFalse(self.user.interviews.exists())

    def test_plain_post_still_works_without_javascript(self):
        response = self.client.post(reverse('interview_create'), CREATE_DATA)
        interview = self.user.interviews.get()
        self.assertRedirects(response, reverse('interview_detail', args=[interview.pk]))


class AsyncGuestTrialTests(TestCase):
    def setUp(self):
        self._real_generate = guest_views.generate_questions
        self._real_evaluate = guest_views.evaluate_answer
        guest_views.generate_questions = fake_generate_questions
        guest_views.evaluate_answer = fake_evaluate_answer

    def tearDown(self):
        guest_views.generate_questions = self._real_generate
        guest_views.evaluate_answer = self._real_evaluate

    def test_start_returns_redirect_json(self):
        response = self.client.post(reverse('guest_trial_start'), **FETCH)
        self.assertEqual(response.json(), {'redirect': reverse('guest_trial')})

    def test_answer_error_returns_json_and_keeps_progress(self):
        from .services.gemini import GeminiError

        self.client.post(reverse('guest_trial_start'), **FETCH)

        def failing(**kwargs):
            raise GeminiError('patladı')

        guest_views.evaluate_answer = failing
        response = self.client.post(reverse('guest_trial_answer'), {'answer': 'cevap'}, **FETCH)
        self.assertEqual(response.status_code, 503)
        self.assertIn('Değerlendirme sırasında', response.json()['error'])
        self.assertEqual(self.client.session['guest_trial']['answers'], [])


class AbandonedInterviewTests(TestCase):
    """Soru üretimi yarıda kesilirse sorusuz kalan mülakat: açılınca çökmez, temizlenir."""

    def setUp(self):
        self.user = User.objects.create_user(username='a@example.com', email='a@example.com', password='x')
        self.client.force_login(self.user)

    def _interview(self, minutes_old):
        from datetime import timedelta

        from django.utils import timezone

        from .models import Interview

        interview = Interview.objects.create(
            user=self.user, position='backend_developer', level='junior',
            interview_type='mixed', language='tr', question_count=5,
        )
        Interview.objects.filter(pk=interview.pk).update(
            created_at=timezone.now() - timedelta(minutes=minutes_old)
        )
        return interview

    def test_old_questionless_interview_is_removed_with_message(self):
        from .models import Interview

        interview = self._interview(minutes_old=30)

        response = self.client.get(reverse('interview_detail', args=[interview.pk]), follow=True)

        self.assertRedirects(response, reverse('interview_create'))
        self.assertContains(response, 'soruları hazırlanamamıştı')
        self.assertFalse(Interview.objects.filter(pk=interview.pk).exists())

    def test_recent_questionless_interview_is_left_alone(self):
        from .models import Interview

        interview = self._interview(minutes_old=1)

        response = self.client.get(reverse('interview_detail', args=[interview.pk]), follow=True)

        self.assertRedirects(response, reverse('panel'))
        self.assertContains(response, 'hâlâ hazırlanıyor')
        self.assertTrue(Interview.objects.filter(pk=interview.pk).exists())

    def test_panel_cleans_old_ones_only_and_frees_daily_limit(self):
        from .models import DAILY_INTERVIEW_LIMIT, Interview

        old = [self._interview(minutes_old=30) for _ in range(DAILY_INTERVIEW_LIMIT)]
        recent = self._interview(minutes_old=1)

        self.assertEqual(self.client.get(reverse('panel')).status_code, 200)

        self.assertFalse(Interview.objects.filter(pk__in=[i.pk for i in old]).exists())
        self.assertTrue(Interview.objects.filter(pk=recent.pk).exists())

    def test_complete_without_answers_does_not_crash(self):
        from .views import _complete_interview

        interview = self._interview(minutes_old=30)

        _complete_interview(interview)  # 0/0 Decimal bölmesi decimal.InvalidOperation fırlatırdı

        interview.refresh_from_db()
        self.assertEqual(interview.status, 'in_progress')
        self.assertIsNone(interview.overall_score)


class AnswerLengthTests(TestCase):
    """Cevap uzunluğu sınırı (web ve misafir): Gemini'ye gitmeden reddedilir."""

    def setUp(self):
        from .models import Interview, Question

        self.user = User.objects.create_user(username='l@example.com', email='l@example.com', password='x')
        self.client.force_login(self.user)
        self.interview = Interview.objects.create(
            user=self.user, position='backend_developer', level='junior',
            interview_type='mixed', language='tr', question_count=5,
        )
        self.question = Question.objects.create(
            interview=self.interview, order=1, text='Soru?', category='teknik',
        )

    def test_web_answer_too_long_is_rejected_before_gemini(self):
        import json
        from unittest.mock import patch

        from .models import MAX_ANSWER_LENGTH, Answer

        with patch('interviews.views.evaluate_answer') as evaluate:
            response = self.client.post(
                reverse('interview_answer', args=[self.interview.pk]),
                data=json.dumps({'question_id': self.question.pk, 'text': 'a' * (MAX_ANSWER_LENGTH + 1)}),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn(str(MAX_ANSWER_LENGTH), response.json()['message'])
        evaluate.assert_not_called()
        self.assertFalse(Answer.objects.exists())

    def test_detail_textarea_has_maxlength(self):
        from .models import MAX_ANSWER_LENGTH

        response = self.client.get(reverse('interview_detail', args=[self.interview.pk]))
        self.assertContains(response, f'maxlength="{MAX_ANSWER_LENGTH}"')

    def test_guest_answer_too_long_is_rejected_before_gemini(self):
        from unittest.mock import patch

        from .models import MAX_ANSWER_LENGTH

        self.client.logout()
        session = self.client.session
        session['guest_trial'] = {
            'questions': [{'text': 'Soru?', 'category': 'teknik'}], 'answers': [], 'language': 'tr',
        }
        session.save()

        with patch('interviews.guest_views.evaluate_answer') as evaluate:
            response = self.client.post(
                reverse('guest_trial_answer'), {'answer': 'a' * (MAX_ANSWER_LENGTH + 1)}, follow=True,
            )

        evaluate.assert_not_called()
        self.assertContains(response, str(MAX_ANSWER_LENGTH))
        self.assertEqual(self.client.session['guest_trial']['answers'], [])
