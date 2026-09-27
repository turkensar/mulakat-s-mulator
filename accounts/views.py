from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from config.ratelimit import client_ip

from .forms import (
    AccountDeleteForm, LoginForm, NewPasswordForm, RegisterForm, ResetRequestForm,
)
from .google_auth import GoogleTokenError, verify_google_credential
from .utils import unique_username


@ratelimit(key=client_ip, rate='5/h', method='POST', block=False)
def register(request):
    if request.user.is_authenticated:
        return redirect('panel')

    if request.method == 'POST':
        if getattr(request, 'limited', False):
            form = RegisterForm(request.POST)
            form.add_error(
                None, _('Çok fazla kayıt denemesi yapıldı. Lütfen bir süre sonra tekrar dene.')
            )
        else:
            form = RegisterForm(request.POST)
            if form.is_valid():
                user = form.save()
                login(request, user, backend='accounts.auth_backends.EmailAuthBackend')
                return redirect('panel')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


@require_POST
@ratelimit(key=client_ip, rate='15/h', method='POST', block=False)
def google_login(request):
    if getattr(request, 'limited', False):
        messages.error(request, _('Çok fazla deneme yapıldı. Lütfen bir süre sonra tekrar dene.'))
        return redirect('login')

    credential = request.POST.get('credential', '')
    try:
        email = verify_google_credential(credential)
    except GoogleTokenError:
        messages.error(request, _('Google ile giriş doğrulanamadı. Lütfen tekrar dene.'))
        return redirect('login')

    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User(email=email, username=unique_username(email), is_active=True)
        user.set_unusable_password()
        user.save()
    elif not user.is_active:
        messages.error(request, _('Bu hesap devre dışı bırakılmış.'))
        return redirect('login')

    login(request, user, backend='accounts.auth_backends.EmailAuthBackend')
    return redirect('panel')


@method_decorator(ratelimit(key=client_ip, rate='10/h', method='POST', block=False), name='post')
class RateLimitedLoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm

    def post(self, request, *args, **kwargs):
        if getattr(request, 'limited', False):
            form = self.get_form()
            form.add_error(
                None, _('Çok fazla giriş denemesi yapıldı. Lütfen bir süre sonra tekrar dene.')
            )
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)


# Her POST bir e-posta gönderebildiği için hız sınırı, formu başkasının adresine
# e-posta yağdırmak için kullanılmasını engeller.
@method_decorator(ratelimit(key=client_ip, rate='5/h', method='POST', block=False), name='post')
class RateLimitedPasswordResetView(auth_views.PasswordResetView):
    template_name = 'accounts/password_reset_form.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    email_template_name = 'accounts/password_reset_email.txt'
    form_class = ResetRequestForm

    def post(self, request, *args, **kwargs):
        if getattr(request, 'limited', False):
            form = self.get_form()
            form.add_error(
                None, _('Çok fazla deneme yapıldı. Lütfen bir süre sonra tekrar dene.')
            )
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)


class NewPasswordView(auth_views.PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    form_class = NewPasswordForm


@login_required
def account_delete(request):
    user = request.user
    if request.method == 'POST':
        form = AccountDeleteForm(user, request.POST)
        if form.is_valid():
            logout(request)
            # Mülakatlar, sorular ve cevaplar CASCADE ile birlikte silinir.
            user.delete()
            messages.success(request, _('Hesabın ve tüm verilerin silindi.'))
            return redirect('home')
    else:
        form = AccountDeleteForm(user)

    return render(request, 'accounts/account_delete.html', {
        'form': form,
        'interview_count': user.interviews.count(),
    })
