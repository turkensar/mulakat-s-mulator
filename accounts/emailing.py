import logging

import requests
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils import translation
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext as _

from .utils import display_name

logger = logging.getLogger(__name__)

RESEND_URL = 'https://api.resend.com/emails'


class EmailSendError(Exception):
    """Doğrulama e-postası gönderilemediğinde fırlatılır."""


def verification_link(user, request):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    path = reverse('verify_email', args=[uidb64, token])
    return request.build_absolute_uri(path)


def send_verification_email(user, request):
    link = verification_link(user, request)
    with translation.override(request.LANGUAGE_CODE):
        subject = _('E-posta adresini doğrula')
        body = _(
            'Merhaba %(username)s,\n\n'
            'Mülakat Simülatörü hesabını etkinleştirmek için aşağıdaki bağlantıya tıkla:\n'
            '%(link)s\n\n'
            'Bu bağlantı 3 gün geçerlidir. Bu hesabı sen açmadıysan bu e-postayı yok sayabilirsin.'
        ) % {'username': display_name(user), 'link': link}

    if not settings.RESEND_API_KEY:
        # Yerel geliştirmede gerçek Resend hesabı gerekmesin diye bağlantı konsola yazılır.
        logger.info('RESEND_API_KEY yok; doğrulama bağlantısı (%s): %s', user.email, link)
        return

    try:
        response = requests.post(
            RESEND_URL,
            headers={'Authorization': f'Bearer {settings.RESEND_API_KEY}'},
            json={
                'from': settings.RESEND_FROM_EMAIL,
                'to': [user.email],
                'subject': str(subject),
                'text': body,
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning('Doğrulama e-postası gönderilemedi (%s): %s', user.email, exc)
        raise EmailSendError(str(exc)) from exc
