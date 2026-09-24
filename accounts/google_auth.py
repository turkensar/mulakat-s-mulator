from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


class GoogleTokenError(Exception):
    """Google kimlik doğrulama jetonu geçersiz ya da doğrulanamadığında fırlatılır."""


def verify_google_credential(credential):
    """Google Identity Services'ten gelen JWT'yi doğrular, doğrulanmış e-postayı döner."""
    try:
        payload = id_token.verify_oauth2_token(
            credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        raise GoogleTokenError(str(exc)) from exc

    if not payload.get('email_verified'):
        raise GoogleTokenError('E-posta Google tarafından doğrulanmamış.')

    return payload['email']
