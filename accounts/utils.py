def display_name(user):
    """Selamlamalarda gösterilen kısa ad. Yeni kullanıcılarda username=email
    olduğu için @ öncesi kısım kullanılır; eski kullanıcılarda username aynen."""
    username = user.username
    return username.split('@', 1)[0] if '@' in username else username


def unique_username(email):
    """E-postayı username olarak kullanır; çakışırsa -2, -3… eki eklenir."""
    from django.contrib.auth.models import User

    base = email[:150]
    if not User.objects.filter(username__iexact=base).exists():
        return base
    suffix = 2
    while True:
        candidate = f'{email[:145]}-{suffix}'
        if not User.objects.filter(username__iexact=candidate).exists():
            return candidate
        suffix += 1
