from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .google_auth import GoogleTokenError


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'HTTP {self.status_code}')


def make_fake_post(captcha_ok=True, email_ok=True):
    # accounts.recaptcha ve accounts.emailing aynı `requests` modülünü paylaştığı
    # için tek bir `requests.post` sahtesi, URL'e göre iki farklı çağrıyı da yanıtlar.
    def fake_post(url, **kwargs):
        if 'siteverify' in url:
            return FakeResponse({'success': captcha_ok})
        if not email_ok:
            raise requests.RequestException('Resend API erişilemedi')
        return FakeResponse({'id': 'fake-email-id'})

    return fake_post


REGISTER_DATA = {
    'email': 'yeni@example.com',
    'password1': 'cok-guclu-parola-123',
    'password2': 'cok-guclu-parola-123',
    'kvkk_consent': 'on',
    'g-recaptcha-response': 'dummy-token',
}


@override_settings(RESEND_API_KEY='test-key')
class RegisterFlowTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch('requests.post', side_effect=make_fake_post())
    def test_register_creates_inactive_user_and_does_not_log_in(self, mock_post):
        response = self.client.post(reverse('register'), REGISTER_DATA)

        user = User.objects.get(email='yeni@example.com')
        self.assertEqual(user.username, 'yeni@example.com')
        self.assertFalse(user.is_active)
        self.assertTemplateUsed(response, 'accounts/verify_pending.html')
        self.assertFalse('_auth_user_id' in self.client.session)

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

    @patch('requests.post', side_effect=make_fake_post(email_ok=False))
    def test_register_rolls_back_user_if_email_fails(self, mock_post):
        response = self.client.post(reverse('register'), REGISTER_DATA)

        self.assertFalse(User.objects.filter(email='yeni@example.com').exists())
        self.assertContains(response, 'Doğrulama e-postası gönderilemedi')


class VerifyEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='dogrulanacak', email='dogrulanacak@example.com', password='parola-123456',
            is_active=False,
        )
        self.uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.token = default_token_generator.make_token(self.user)

    def test_valid_link_activates_and_logs_in(self):
        url = reverse('verify_email', args=[self.uidb64, self.token])
        response = self.client.get(url)

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertRedirects(response, reverse('panel'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_invalid_token_rejected(self):
        url = reverse('verify_email', args=[self.uidb64, 'gecersiz-token'])
        response = self.client.get(url)

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, 'accounts/verify_invalid.html')

    def test_already_used_link_rejected_on_second_visit(self):
        url = reverse('verify_email', args=[self.uidb64, self.token])
        self.client.get(url)
        self.client.logout()

        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)


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
    def test_existing_inactive_user_activated_via_google(self, mock_verify):
        User.objects.create_user(
            username='mevcut@example.com', email='mevcut@example.com', password='x',
            is_active=False,
        )
        response = self.client.post(reverse('google_login'), {'credential': 'sahte-jwt'})

        user = User.objects.get(email='mevcut@example.com')
        self.assertTrue(user.is_active)
        self.assertRedirects(response, reverse('panel'))

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
        self.assertContains(response, 'e-postana gönderdiğimiz bağlantıyla')
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_active_user_can_log_in(self):
        self.user.is_active = True
        self.user.save(update_fields=['is_active'])
        response = self.client.post(
            reverse('login'), {'username': 'pasif', 'password': 'parola-123456'}
        )
        self.assertRedirects(response, reverse('panel'))
