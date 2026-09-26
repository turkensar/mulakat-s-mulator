from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('kayit/', views.register, name='register'),
    path('dogrula/<str:uidb64>/<str:token>/', views.verify_email, name='verify_email'),
    path('giris/', views.RateLimitedLoginView.as_view(), name='login'),
    path('google-giris/', views.google_login, name='google_login'),
    path('cikis/', auth_views.LogoutView.as_view(), name='logout'),
    path('sifremi-unuttum/', views.RateLimitedPasswordResetView.as_view(), name='password_reset'),
    path(
        'sifremi-unuttum/gonderildi/',
        auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'),
        name='password_reset_done',
    ),
    path('sifre-sifirla/<uidb64>/<token>/', views.NewPasswordView.as_view(), name='password_reset_confirm'),
    path(
        'sifre-sifirla/tamam/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html'
        ),
        name='password_reset_complete',
    ),
]
