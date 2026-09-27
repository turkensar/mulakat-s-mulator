from django.urls import path

from . import views

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='api_register'),
    path('auth/login/', views.LoginView.as_view(), name='api_login'),
    path('auth/google/', views.GoogleLoginView.as_view(), name='api_google_login'),
    path('interviews/', views.InterviewListCreateView.as_view(), name='api_interview_list_create'),
    path('interviews/<int:pk>/', views.InterviewDetailView.as_view(), name='api_interview_detail'),
    path('interviews/<int:pk>/answer/', views.AnswerView.as_view(), name='api_interview_answer'),
    path('interviews/<int:pk>/report/', views.InterviewReportView.as_view(), name='api_interview_report'),
]
