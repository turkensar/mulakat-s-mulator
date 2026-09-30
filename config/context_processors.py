from django.conf import settings

from accounts.utils import display_name


def google_client_id(request):
    return {'GOOGLE_CLIENT_ID': settings.GOOGLE_CLIENT_ID}


def contact_email(request):
    return {'CONTACT_EMAIL': settings.CONTACT_EMAIL}


def profile_menu(request):
    """Navbar'daki profil menüsü için kısa ad ve avatar harfi (yalnızca giriş yapmış kullanıcıda)."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}
    name = display_name(user)
    first = name[:1]
    # Python 'i'.upper() 'I' verir; Türkçe baş harf 'İ' olmalı.
    initial = 'İ' if first == 'i' else first.upper()
    return {'profile_name': name, 'profile_initial': initial or '?'}
