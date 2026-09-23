import logging

import requests
from django import forms
from django.conf import settings
from django.utils.html import format_html
from django.utils.translation import gettext as gettext_now

logger = logging.getLogger(__name__)

VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'


class ReCaptchaWidget(forms.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        return format_html(
            '<div class="g-recaptcha" data-sitekey="{}"></div>'
            '<script src="https://www.google.com/recaptcha/api.js" async defer></script>',
            settings.RECAPTCHA_PUBLIC_KEY,
        )

    def value_from_datadict(self, data, files, name):
        # Google'ın widget'ı yanıtı Django alan adından bağımsız, sabit bu isimle POST eder.
        return data.get('g-recaptcha-response')


class ReCaptchaField(forms.CharField):
    widget = ReCaptchaWidget

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', '')
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        try:
            response = requests.post(
                VERIFY_URL,
                data={'secret': settings.RECAPTCHA_PRIVATE_KEY, 'response': value},
                timeout=10,
            )
            result = response.json()
        except (requests.RequestException, ValueError):
            logger.warning('reCAPTCHA doğrulama servisine ulaşılamadı.')
            raise forms.ValidationError(
                gettext_now('Doğrulama servisine ulaşılamadı. Lütfen tekrar dene.')
            )
        if not result.get('success'):
            raise forms.ValidationError(gettext_now('Robot olmadığını doğrular mısın?'))
        return value
