"""GEÇİCİ: Sentry'nin canlıda hata aldığını doğrulamak için. Doğrulanınca bu dosya ve urls.py'deki satır silinir."""
from django.contrib.auth.decorators import login_required


@login_required
def sentry_test(request):
    # Değer kaynağa yazılı değil, çalışma zamanında üretilir; include_local_variables=False ise Sentry'de görünmemeli.
    cv_text = 'GIZLI-' + 'DENEME'
    raise RuntimeError(f'Sentry test hatası (geçici, silinecek) {len(cv_text)}')
