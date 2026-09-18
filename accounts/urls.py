from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('kayit/', views.register, name='register'),
    path('giris/', views.RateLimitedLoginView.as_view(), name='login'),
    path('cikis/', auth_views.LogoutView.as_view(), name='logout'),
]
