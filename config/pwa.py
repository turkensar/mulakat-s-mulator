"""PWA (docs §2.2): web uygulama manifesti, service worker ve çevrimdışı sayfa.

Bunlar WhiteNoise yerine view olarak servis edilir: WhiteNoise `.webmanifest` için doğru
MIME türünü vermez ve service worker'ın kapsamı için `/sw.js` kökten sunulmalıdır.
"""
from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import cache_control


@cache_control(max_age=3600)
def manifest(request):
    data = {
        'id': '/',
        'name': 'AI Mülakat Simülatörü',
        'short_name': 'Mülakat',
        'description': 'Yapay zekâ ile mülakat pratiği yap, anında geri bildirim al.',
        'lang': 'tr',
        'dir': 'ltr',
        'start_url': '/panel/',
        'scope': '/',
        'display': 'standalone',
        'orientation': 'any',
        # Değerler static/css/tokens.css'teki --bg ve --violet ile aynı olmalı.
        'background_color': '#F7F5FF',
        'theme_color': '#6B3BFF',
        'icons': [
            {'src': static('img/icon-192.png'), 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('img/icon-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('img/icon-maskable-512.png'), 'sizes': '512x512', 'type': 'image/png',
             'purpose': 'maskable'},
        ],
        'shortcuts': [
            {'name': 'Yeni mülakat', 'url': '/mulakat/yeni/'},
            {'name': 'Gelişimim', 'url': '/gelisim/'},
        ],
    }
    return JsonResponse(data, content_type='application/manifest+json')


# Tarayıcı service worker'ı her açılışta yeniden kontrol edebilsin (güncelleme gecikmesin).
@cache_control(no_cache=True)
def service_worker(request):
    return render(request, 'pwa/sw.js', content_type='text/javascript; charset=utf-8')


def offline(request):
    return render(request, 'pwa/offline.html')
