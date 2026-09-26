import logging
import smtplib

from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import translation
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext as _

from .utils import display_name

logger = logging.getLogger(__name__)


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

    try:
        send_mail(subject, body, None, [user.email])
    except (smtplib.SMTPException, OSError) as exc:
        # OSError: bağlantı reddi / zaman aşımı gibi ağ hataları (socket.timeout dahil).
        logger.warning('Doğrulama e-postası gönderilemedi (%s): %s', user.email, exc)
        raise EmailSendError(str(exc)) from exc
