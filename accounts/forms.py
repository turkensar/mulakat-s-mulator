from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm,
)
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext as gettext_now
from django.utils.translation import gettext_lazy as _

from .recaptcha import ReCaptchaField
from .utils import unique_username


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label=_('E-posta'))
    password1 = forms.CharField(
        label=_('Parola'),
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text=_('En az 8 karakter.'),
    )
    password2 = forms.CharField(
        label=_('Parola (tekrar)'),
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text=_('Aynı parolayı bir daha yaz.'),
    )
    kvkk_consent = forms.BooleanField(
        required=True,
        label=_("Aydınlatma Metni'ni okudum, kabul ediyorum."),
        error_messages={'required': _("Devam etmek için Aydınlatma Metni'ni onaylaman gerekiyor.")},
    )
    captcha = ReCaptchaField()

    class Meta:
        model = User
        fields = ('email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['kvkk_consent'].help_text = format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>',
            reverse_lazy('kvkk'), gettext_now("Aydınlatma Metni'ni aç"),
        )

    error_messages = {
        'password_mismatch': _('Parolalar eşleşmiyor, tekrar dener misin?'),
    }

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(gettext_now('Bu e-posta adresi zaten kullanılıyor.'))
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data['email']
        user.email = email
        user.username = unique_username(email)
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label=_('E-posta'),
        widget=forms.TextInput(attrs={'autocomplete': 'email', 'autofocus': True}),
    )
    password = forms.CharField(
        label=_('Parola'),
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise forms.ValidationError(
                gettext_now('Bu hesap devre dışı bırakılmış.'),
                code='inactive',
            )

    def get_invalid_login_error(self):
        return forms.ValidationError(
            gettext_now('E-posta ya da parola hatalı.'),
            code='invalid_login',
        )


class ResetRequestForm(PasswordResetForm):
    email = forms.EmailField(
        label=_('E-posta'),
        max_length=254,
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'autofocus': True}),
    )


class NewPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label=_('Yeni parola'),
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'autofocus': True}),
        help_text=_('En az 8 karakter.'),
    )
    new_password2 = forms.CharField(
        label=_('Yeni parola (tekrar)'),
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text=_('Aynı parolayı bir daha yaz.'),
    )

    error_messages = {
        **SetPasswordForm.error_messages,
        'password_mismatch': _('Parolalar eşleşmiyor, tekrar dener misin?'),
    }


class AccountDeleteForm(forms.Form):
    """Hesap silme onayı: parolalı hesapta parola, Google ile açılmış (parolasız)
    hesapta e-posta adresi istenir; açık kalmış bir oturumdan tek tıkla silinmesin."""

    confirmation = forms.CharField(strip=False)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        field = self.fields['confirmation']
        if user.has_usable_password():
            field.label = _('Parolan')
            field.widget = forms.PasswordInput(attrs={'autocomplete': 'current-password'})
        else:
            field.label = _('E-posta adresin')
            field.widget = forms.EmailInput(attrs={'autocomplete': 'off'})

    def clean_confirmation(self):
        value = self.cleaned_data['confirmation']
        if self.user.has_usable_password():
            if not self.user.check_password(value):
                raise forms.ValidationError(gettext_now('Parola hatalı.'))
        elif value.strip().lower() != (self.user.email or '').lower():
            raise forms.ValidationError(gettext_now('E-posta adresin eşleşmiyor.'))
        return value
