def client_ip(group, request):
    """django-ratelimit icin IP anahtari. Vercel gibi bir ters proxy arkasinda
    `REMOTE_ADDR` proxy'nin kendi adresi olabilir (butun ziyaretcilerde ayni
    cikip hiz sinirini istemeden PAYLASIMLI hale getirir); once gercek
    istemci IP'sini tasiyan `X-Forwarded-For` basligina bakilir."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')
