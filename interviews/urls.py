from django.urls import path

from . import views

urlpatterns = [
    path('mulakat/yeni/', views.create_interview, name='interview_create'),
    path('mulakat/<int:pk>/', views.interview_detail, name='interview_detail'),
]
