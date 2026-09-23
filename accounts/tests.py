from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


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
    'username': 'yenikullanici',
    'email': 'yeni@example.com',
    'password1': 'cok-guclu-parola-123',
    'password2': 'cok-guclu-parola-123',
    'g-recaptcha-response': 'dummy-token',
}


@override_settings(RESEND_API_KEY='test-key')
class RegisterFlowTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch('requests.post', side_effect=make_fake_post())
    def test_register_creates_inactive_user_and_does_not_log_in(self, mock_post):
        response = self.client.post(reverse('register'), REGISTER_DATA)

        user = User.objects.get(username='yenikullanici')
        self.assertFalse(user.is_active)
        self.assertTemplateUsed(response, 'accounts/verify_pending.html')
        self.assertFalse('_auth_user_id' in self.client.session)

    @patch('requests.post', side_effect=make_fake_post(captcha_ok=False))
    def test_register_rejects_failed_captcha(self, mock_post):
        response = self.client.post(reverse('register'), REGISTER_DATA)

        self.assertFalse(User.objects.filter(username='yenikullanici').exists())
        self.assertContains(response, 'Robot olmadığını doğrular mısın?')

    @patch('requests.post', side_effect=make_fake_post(email_ok=False))
    def test_register_rolls_back_user_if_email_fails(self, mock_post):
        response = self.client.post(reverse('register'), REGISTER_DATA)

        self.assertFalse(User.objects.filter(username='yenikullanici').exists())
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
