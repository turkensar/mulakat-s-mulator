from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.utils.translation import gettext as gettext_now
from django.utils.translation import gettext_lazy as _

from .recaptcha import ReCaptchaField


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label=_('E-posta'))
    captcha = ReCaptchaField()

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(gettext_now('Bu e-posta adresi zaten kullanılıyor.'))
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise forms.ValidationError(
                gettext_now(
                    'Hesabını kullanmadan önce e-postana gönderdiğimiz bağlantıyla '
                    'doğrulaman gerekiyor.'
                ),
                code='inactive',
            )
