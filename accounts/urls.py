from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('kayit/', views.register, name='register'),
    path('giris/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('cikis/', auth_views.LogoutView.as_view(), name='logout'),
]
