from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailAuthBackend(ModelBackend):
    """Yeni kullanıcılar e-postayla (username=email), eski kullanıcılar kendi
    kullanıcı adıyla giriş yapabilir. is_active kontrolü burada değil,
    LoginForm.confirm_login_allowed'da yapılır (özel "doğrulaman gerekiyor"
    mesajı gösterebilmek için authenticate() inaktif hesabı reddetmemeli).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None or password is None:
            return None
        try:
            user = UserModel._default_manager.get(
                Q(email__iexact=username) | Q(username__iexact=username)
            )
        except UserModel.DoesNotExist:
            # Zamanlama saldırısına karşı: kullanıcı yokken de bir hash karşılaştırması yap.
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            user = (
                UserModel._default_manager.filter(
                    Q(email__iexact=username) | Q(username__iexact=username)
                )
                .order_by('id')
                .first()
            )
        if user.check_password(password):
            return user
        return None
