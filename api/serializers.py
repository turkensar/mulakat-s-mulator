"""Mobil (Android) istemci için DRF serializer'ları.

Web tarafının form doğrulaması (interviews/forms.py::InterviewForm) mülakat oluşturmada
doğrudan yeniden kullanılır; burada yalnızca web'de karşılığı olmayan (kayıt/giriş) ya da
JSON şekli web'in HTML şablonlarından farklı olan (liste, rapor) alanlar için serializer var.
"""
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.utils import unique_username
from interviews.models import Answer, Question


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    kvkk_consent = serializers.BooleanField()

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Bu e-posta adresi zaten kullanılıyor.')
        return value

    def validate_kvkk_consent(self, value):
        if not value:
            raise serializers.ValidationError(
                "Devam etmek için Aydınlatma Metni'ni onaylaman gerekiyor."
            )
        return value

    def validate_password(self, value):
        # Django'nun AUTH_PASSWORD_VALIDATORS ayarındaki kurallarla aynı doğrulama.
        validate_password(value)
        return value

    def create(self, validated_data):
        email = validated_data['email']
        user = User(email=email, username=unique_username(email))
        user.set_password(validated_data['password'])
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(write_only=True)


class GoogleLoginSerializer(serializers.Serializer):
    credential = serializers.CharField()


class QuestionSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='get_category_display')

    class Meta:
        model = Question
        fields = ['id', 'order', 'text', 'category']


class AnsweredQuestionSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='get_category_display')
    answer_text = serializers.CharField(source='answer.text')
    score = serializers.IntegerField(source='answer.score')

    class Meta:
        model = Question
        fields = ['id', 'order', 'text', 'category', 'answer_text', 'score']


class InterviewListItemSerializer(serializers.Serializer):
    """Panel listesi: web'deki panel.html ile aynı alanlar (bkz. templates/interviews/panel.html)."""

    id = serializers.IntegerField()
    position = serializers.CharField()
    display_position = serializers.CharField()
    interview_type = serializers.CharField()
    interview_type_display = serializers.CharField(source='get_interview_type_display')
    language = serializers.CharField()
    language_display = serializers.CharField(source='get_language_display')
    job_posting = serializers.SerializerMethodField()
    cv_based = serializers.BooleanField()
    status = serializers.CharField()
    answered_count = serializers.IntegerField(default=None)
    question_count = serializers.IntegerField()
    overall_score = serializers.DecimalField(max_digits=4, decimal_places=2, allow_null=True)
    created_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)

    def get_job_posting(self, interview):
        return bool(interview.job_posting)


class ReportAnswerSerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(source='question.order')
    question = serializers.CharField(source='question.text')
    answer = serializers.CharField(source='text')

    class Meta:
        model = Answer
        fields = [
            'order', 'question', 'answer', 'score', 'strengths', 'improvements',
            'sample_answer', 'language_score', 'language_feedback',
        ]
