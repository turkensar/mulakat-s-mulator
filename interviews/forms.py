from django import forms

from .models import Interview


class InterviewForm(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ['position', 'level', 'interview_type', 'language', 'question_count']
