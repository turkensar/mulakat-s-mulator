from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('kayit/', views.register, name='register'),
    path('dogrula/<str:uidb64>/<str:token>/', views.verify_email, name='verify_email'),
    path('giris/', views.RateLimitedLoginView.as_view(), name='login'),
    path('google-giris/', views.google_login, name='google_login'),
    path('cikis/', auth_views.LogoutView.as_view(), name='logout'),
]
