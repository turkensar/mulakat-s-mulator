from django.urls import path

from . import guest_views, views

urlpatterns = [
    path('gelisim/', views.progress, name='progress'),
    path('mulakat/yeni/', views.create_interview, name='interview_create'),
    path('mulakat/<int:pk>/', views.interview_detail, name='interview_detail'),
    path('mulakat/<int:pk>/cevap/', views.submit_answer, name='interview_answer'),
    path('mulakat/<int:pk>/rapor/', views.interview_report, name='interview_report'),
    path('deneme/baslat/', guest_views.guest_trial_start, name='guest_trial_start'),
    path('deneme/', guest_views.guest_trial, name='guest_trial'),
    path('deneme/cevap/', guest_views.guest_trial_answer, name='guest_trial_answer'),
    path('deneme/sonuc/', guest_views.guest_trial_result, name='guest_trial_result'),
]
