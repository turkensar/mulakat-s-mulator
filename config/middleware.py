from django.conf import settings
from django.utils import translation
from django.utils.cache import patch_vary_headers


class CookieLocaleMiddleware:
    """Arayüz dilini yalnızca çerezden seçer (docs §2.2 iki dilli arayüz).

    Django'nun LocaleMiddleware'i çerez yoksa tarayıcının Accept-Language başlığına bakar;
    bu site Türkçe konuşan öğrencilere yönelik olduğu için dil, kullanıcı seçene kadar
    HER ZAMAN Türkçe'dir. Çerezi `set_language` görünümü (/i18n/setlang/) yazar.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.supported = {code for code, _ in settings.LANGUAGES}

    def __call__(self, request):
        language = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if language not in self.supported:
            language = settings.LANGUAGE_CODE
        translation.activate(language)
        request.LANGUAGE_CODE = language
        try:
            response = self.get_response(request)
        finally:
            translation.deactivate()
        response.headers.setdefault('Content-Language', language)
        # Aynı adres çereze göre farklı dilde döner; ara önbellekler karıştırmasın.
        patch_vary_headers(response, ('Cookie',))
        return response
