"""GEÇİCİ: Sentry'nin canlıda hata aldığını doğrulamak için. Doğrulanınca bu dosya ve urls.py'deki satır silinir."""
import json
import os
import uuid
from urllib.parse import urlsplit

import requests
import sentry_sdk
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


def _diagnose():
    """DSN'in anahtarını göstermeden: Sentry başlatılmış mı, DSN biçimi sağlam mı, Sentry'ye ulaşılıyor mu."""
    raw = settings.SENTRY_DSN
    info = {
        'vercel_env': os.environ.get('VERCEL_ENV'),
        'dsn_set': bool(raw),
        'dsn_length': len(raw),
        'dsn_has_outer_space_or_quote': raw != raw.strip().strip('"\''),
        'sdk_active': sentry_sdk.get_client().is_active(),
    }
    try:
        parsed = urlsplit(raw.strip().strip('"\''))
        info['host'] = parsed.hostname
        info['project_id'] = parsed.path.strip('/')
        key = parsed.username
        envelope = '\n'.join([
            json.dumps({'event_id': uuid.uuid4().hex, 'dsn': raw.strip().strip('"\'')}),
            json.dumps({'type': 'event'}),
            json.dumps({'message': 'Sentry tani istegi (dogrudan POST)', 'level': 'info', 'platform': 'python'}),
        ])
        response = requests.post(
            f'https://{parsed.hostname}/api/{info["project_id"]}/envelope/',
            data=envelope.encode(),
            headers={'X-Sentry-Auth': f'Sentry sentry_version=7, sentry_key={key}'},
            timeout=8,
        )
        info['direct_post_status'] = response.status_code
        info['direct_post_body'] = response.text[:200]
    except Exception as exc:  # tanı aracı: her hatayı raporla
        info['direct_post_error'] = f'{type(exc).__name__}: {exc}'[:200]

    # SDK yolu: olay gönderilip bitmesi beklenir (sunucusuz ortamda donma varsayımını sınar).
    sentry_sdk.capture_message('Sentry tani istegi (SDK, flush ile)')
    sentry_sdk.flush(timeout=5)
    info['sdk_message_sent_and_flushed'] = True
    return info


@login_required
def sentry_test(request):
    if request.GET.get('diag'):
        return JsonResponse(_diagnose())
    cv_text = 'GIZLI-' + 'DENEME'  # include_local_variables=False ise Sentry'de görünmemeli
    raise RuntimeError(f'Sentry test hatası (geçici, silinecek) {len(cv_text)}')
