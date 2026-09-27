"""static/js/async_form.js ile gönderilen formlar için sunucu tarafı sözleşmesi.

Betik isteğe `X-Requested-With: fetch` başlığı ekler. Sunucu bu durumda HTML
yerine kısa bir JSON döner:
  {"redirect": url}  -> tarayıcı o adrese gider
  {"error": mesaj}   -> mesaj formun üstünde gösterilir, form olduğu gibi kalır
  {"invalid": true}  -> alan hataları var; betik formu normal yolla yeniden gönderir
                        ve sunucu hataları her zamanki gibi sayfada gösterir
"""
from django.http import JsonResponse


def wants_json(request):
    return request.headers.get('X-Requested-With') == 'fetch'


def json_redirect(url):
    return JsonResponse({'redirect': url})


def json_error(message, status=503):
    return JsonResponse({'error': str(message)}, status=status)


def json_invalid():
    return JsonResponse({'invalid': True}, status=400)
