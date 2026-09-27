import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .google_auth import GoogleTokenError


class FakeResponse:
    def __init__(self, json_data):
        self._json = json_data

    def json(self):
        return self._json


def make_fake_post(captcha_ok=True):
    # reCAPTCHA doğrulaması requests.post ile yapılır; e-postalar ise Django'nun
    # e-posta sistemiyle gider ve testlerde mail.outbox'a düşer.
    def fake_post(url, **kwargs):
        return FakeResponse({'success': captcha_ok})

    return fake_post


REGISTER_DATA = {
    'email': 'yeni@example.com',
    'password1': 'cok-guclu-parola-123',
    'password2': 'cok-guclu-parola-123',
    'kvkk_consent': 'on',
    'g-recaptcha-response': 'dummy-token',
}


class RegisterFlowTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch('requests.post', side_effect=make_fake_post())
    def test_register_creates_active_user_and_logs_in(self, mock_post):
        response = self.client.post(reverse('register'), REGISTER_DATA)

        user = User.objects.get(email='yeni@example.com')
        self.assertEqual(user.username, 'yeni@example.com')
        self.assertTrue(user.is_active)
        self.assertRedirects(response, reverse('panel'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertEqual(len(mail.outbox), 0)

    @patch('requests.post', side_effect=make_fake_post())
    def test_register_username_gets_suffix_on_collision(self, mock_post):
        User.objects.create_user(username='yeni@example.com', password='x')

        self.client.post(reverse('register'), REGISTER_DATA)

        user = User.objects.get(email='yeni@example.com')
        self.assertEqual(user.username, 'yeni@example.com-2')

    @patch('requests.post', side_effect=make_fake_post())
    def test_register_requires_kvkk_consent(self, mock_post):
        data = {k: v for k, v in REGISTER_DATA.items() if k != 'kvkk_consent'}
        response = self.client.post(reverse('register'), data)

        self.assertFalse(User.objects.filter(email='yeni@example.com').exists())
        self.assertContains(response, 'onaylaman gerekiyor')

    @patch('requests.post', side_effect=make_fake_post(captcha_ok=False))
    def test_register_rejects_failed_captcha(self, mock_post):
        response = self.client.post(reverse('register'), REGISTER_DATA)

        self.assertFalse(User.objects.filter(email='yeni@example.com').exists())
        self.assertContains(response, 'Robot olmadığını doğrular mısın?')


class EmailLoginTests(TestCase):
    def test_new_style_user_logs_in_with_email(self):
        User.objects.create_user(
            username='yeni@example.com', email='yeni@example.com', password='parola-123456',
            is_active=True,
        )
        response = self.client.post(
            reverse('login'), {'username': 'yeni@example.com', 'password': 'parola-123456'}
        )
        self.assertRedirects(response, reverse('panel'))

    def test_old_style_user_still_logs_in_with_username(self):
        User.objects.create_user(
            username='eskikullanici', email='eski@example.com', password='parola-123456',
            is_active=True,
        )
        response = self.client.post(
            reverse('login'), {'username': 'eskikullanici', 'password': 'parola-123456'}
        )
        self.assertRedirects(response, reverse('panel'))

    def test_old_style_user_can_also_log_in_with_email(self):
        User.objects.create_user(
            username='eskikullanici2', email='eski2@example.com', password='parola-123456',
            is_active=True,
        )
        response = self.client.post(
            reverse('login'), {'username': 'eski2@example.com', 'password': 'parola-123456'}
        )
        self.assertRedirects(response, reverse('panel'))

    def test_wrong_password_shows_friendly_error(self):
        User.objects.create_user(
            username='yeni2@example.com', email='yeni2@example.com', password='parola-123456',
            is_active=True,
        )
        response = self.client.post(
            reverse('login'), {'username': 'yeni2@example.com', 'password': 'yanlis-parola'}
        )
        self.assertContains(response, 'E-posta ya da parola hatalı.')


class GoogleLoginTests(TestCase):
    @patch('accounts.views.verify_google_credential', return_value='yenigoogle@example.com')
    def test_new_user_created_and_logged_in(self, mock_verify):
        response = self.client.post(reverse('google_login'), {'credential': 'sahte-jwt'})

        user = User.objects.get(email='yenigoogle@example.com')
        self.assertEqual(user.username, 'yenigoogle@example.com')
        self.assertTrue(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertRedirects(response, reverse('panel'))

    @patch('accounts.views.verify_google_credential', return_value='mevcut@example.com')
    def test_disabled_user_cannot_sign_in_via_google(self, mock_verify):
        User.objects.create_user(
            username='mevcut@example.com', email='mevcut@example.com', password='x',
            is_active=False,
        )
        response = self.client.post(
            reverse('google_login'), {'credential': 'sahte-jwt'}, follow=True
        )

        self.assertFalse(User.objects.get(email='mevcut@example.com').is_active)
        self.assertContains(response, 'devre dışı')
        self.assertFalse('_auth_user_id' in self.client.session)

    @patch('accounts.views.verify_google_credential', side_effect=GoogleTokenError('geçersiz'))
    def test_invalid_token_redirects_to_login_with_message(self, mock_verify):
        response = self.client.post(
            reverse('google_login'), {'credential': 'kotu-jwt'}, follow=True
        )
        self.assertContains(response, 'doğrulanamadı')


class InactiveLoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='pasif', email='pasif@example.com', password='parola-123456',
            is_active=False,
        )

    def test_inactive_user_blocked_with_custom_message(self):
        response = self.client.post(
            reverse('login'), {'username': 'pasif', 'password': 'parola-123456'}
        )
        self.assertContains(response, 'devre dışı')
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_active_user_can_log_in(self):
        self.user.is_active = True
        self.user.save(update_fields=['is_active'])
        response = self.client.post(
            reverse('login'), {'username': 'pasif', 'password': 'parola-123456'}
        )
        self.assertRedirects(response, reverse('panel'))


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='unutkan@example.com', email='unutkan@example.com',
            password='eski-parola-123', is_active=True,
        )

    def _reset_link_from_outbox(self):
        match = re.search(r'https?://[^/\s]+(/sifre-sifirla/[^\s]+/)', mail.outbox[0].body)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_full_reset_flow_changes_password(self):
        response = self.client.post(reverse('password_reset'), {'email': 'unutkan@example.com'})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['unutkan@example.com'])

        # Django geçerli jetonu oturuma alıp "set-password" adresine yönlendirir.
        confirm_page = self.client.get(self._reset_link_from_outbox(), follow=True)
        self.assertContains(confirm_page, 'Yeni şifre belirle')

        response = self.client.post(
            confirm_page.redirect_chain[-1][0],
            {'new_password1': 'yeni-guclu-parola-456', 'new_password2': 'yeni-guclu-parola-456'},
        )
        self.assertRedirects(response, reverse('password_reset_complete'))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('yeni-guclu-parola-456'))

    def test_unknown_email_shows_same_page_but_sends_nothing(self):
        response = self.client.post(reverse('password_reset'), {'email': 'yok@example.com'})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_google_only_user_gets_no_reset_email(self):
        google_user = User(username='g@example.com', email='g@example.com', is_active=True)
        google_user.set_unusable_password()
        google_user.save()

        self.client.post(reverse('password_reset'), {'email': 'g@example.com'})
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_link_shows_friendly_message(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.get(
            reverse('password_reset_confirm', args=[uidb64, 'gecersiz-jeton'])
        )
        self.assertContains(response, 'Yeni bağlantı iste')

    def test_login_page_links_to_reset(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, reverse('password_reset'))


class AccountDeleteTests(TestCase):
    def setUp(self):
        from interviews.models import Answer, Interview, Question

        self.user = User.objects.create_user(
            username='silinecek@example.com', email='silinecek@example.com',
            password='parola-123456', is_active=True,
        )
        interview = Interview.objects.create(
            user=self.user, position='junior_developer', level='junior',
            interview_type='technical', language='tr', question_count=5,
        )
        question = Question.objects.create(interview=interview, order=1, text='Soru?', category='teknik')
        Answer.objects.create(question=question, text='Cevap', score=7)
        self.models = (Interview, Question, Answer)

    def test_requires_login(self):
        response = self.client.get(reverse('account_delete'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_wrong_password_keeps_account(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('account_delete'), {'confirmation': 'yanlis'})

        self.assertContains(response, 'Parola hatalı.')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_correct_password_deletes_account_and_all_data(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('account_delete'), {'confirmation': 'parola-123456'}, follow=True
        )

        self.assertRedirects(response, reverse('home'))
        self.assertContains(response, 'Hesabın ve tüm verilerin silindi.')
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        for model in self.models:
            self.assertEqual(model.objects.count(), 0, model.__name__)
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_passwordless_google_account_confirms_with_email(self):
        self.user.set_unusable_password()
        self.user.save()
        self.client.force_login(self.user)

        wrong = self.client.post(reverse('account_delete'), {'confirmation': 'baska@example.com'})
        self.assertContains(wrong, 'eşleşmiyor')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

        self.client.post(reverse('account_delete'), {'confirmation': 'SILINECEK@example.com'})
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_page_states_interview_count(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('account_delete')), '1 mülakatın')

        self.user.interviews.all().delete()
        response = self.client.get(reverse('account_delete'))
        self.assertContains(response, 'Hesabın kalıcı olarak silinecek.')
        self.assertNotContains(response, '0 mülakat')

    def test_panel_links_to_delete_page(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('panel')), reverse('account_delete'))
