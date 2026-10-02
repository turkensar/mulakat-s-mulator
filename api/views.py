"""Mobil (Android) istemci için JSON API.

Web tarafındaki view/template'lere (interviews/, accounts/) dokunmadan, üzerlerine ince bir
JSON katmanı olarak eklendi. İş mantığının kendisi (Gemini çağrıları, günlük limit, mülakat
tamamlama) interviews/views.py ve interviews/forms.py'deki mevcut, test edilmiş fonksiyonlar
ve InterviewForm yeniden kullanılarak tekrarlanmaktan kaçınılır.
"""
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.google_auth import GoogleTokenError, verify_google_credential
from accounts.utils import unique_username
from config.ratelimit import client_ip
from interviews.forms import InterviewForm
from interviews.models import Answer, DAILY_INTERVIEW_LIMIT, MAX_ANSWER_LENGTH, Question
from interviews.services.gemini import (
    GeminiError, GeminiQuotaError, GeminiTimeoutError, evaluate_answer, generate_questions,
)
from interviews.views import (
    QUOTA_MESSAGE, SLOW_MESSAGE, _complete_interview, _current_question, _prompt_labels,
    _is_abandoned, _purge_abandoned,
    _today_interview_count, answer_too_long_message,
)

from .serializers import (
    AnsweredQuestionSerializer, GoogleLoginSerializer, InterviewListItemSerializer,
    LoginSerializer, QuestionSerializer, RegisterSerializer, ReportAnswerSerializer,
)


# Kimlik doğrulama uç noktaları web'deki sınırlarla aynıdır (accounts/views.py): web'de kayıt 5/saat,
# giriş 10/saat, Google 15/saat. Mobil kayıtta reCAPTCHA yok; sınırsız hesap açılıp paylaşılan Gemini
# kotasının tüketilmesini ve parola denemesini bu sınırlar engeller.
def _too_many_attempts():
    return Response(
        {'detail': 'Çok fazla deneme yapıldı. Lütfen bir süre sonra tekrar dene.'},
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )


def _gemini_error_response(exc):
    """GeminiError alt sınıflarını web'deki submit_answer/create_interview ile aynı mesaj+koda çevirir."""
    if isinstance(exc, GeminiQuotaError):
        return str(QUOTA_MESSAGE), status.HTTP_503_SERVICE_UNAVAILABLE
    if isinstance(exc, GeminiTimeoutError):
        return str(SLOW_MESSAGE), status.HTTP_503_SERVICE_UNAVAILABLE
    return 'Sorular oluşturulurken bir hata oluştu. Lütfen tekrar dene.', status.HTTP_502_BAD_GATEWAY


@method_decorator(ratelimit(key=client_ip, rate='5/h', method='POST', block=False), name='post')
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if getattr(request, 'limited', False):
            return _too_many_attempts()
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        token, _created = Token.objects.get_or_create(user=user)
        return Response({'token': token.key}, status=status.HTTP_201_CREATED)


@method_decorator(ratelimit(key=client_ip, rate='10/h', method='POST', block=False), name='post')
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if getattr(request, 'limited', False):
            return _too_many_attempts()
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data['email'],
            password=serializer.validated_data['password'],
        )
        if user is None:
            return Response(
                {'detail': 'E-posta ya da parola hatalı.'}, status=status.HTTP_400_BAD_REQUEST
            )
        if not user.is_active:
            return Response(
                {'detail': 'Bu hesap devre dışı bırakılmış.'}, status=status.HTTP_400_BAD_REQUEST
            )
        token, _created = Token.objects.get_or_create(user=user)
        return Response({'token': token.key})


@method_decorator(ratelimit(key=client_ip, rate='15/h', method='POST', block=False), name='post')
class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if getattr(request, 'limited', False):
            return _too_many_attempts()
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            email = verify_google_credential(serializer.validated_data['credential'])
        except GoogleTokenError:
            return Response(
                {'detail': 'Google ile giriş doğrulanamadı.'}, status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User(email=email, username=unique_username(email), is_active=True)
            user.set_unusable_password()
            user.save()
        elif not user.is_active:
            return Response(
                {'detail': 'Bu hesap devre dışı bırakılmış.'}, status=status.HTTP_400_BAD_REQUEST
            )

        token, _created = Token.objects.get_or_create(user=user)
        return Response({'token': token.key})


class InterviewListCreateView(APIView):
    def get(self, request):
        _purge_abandoned(request.user)
        interviews = request.user.interviews.annotate(
            answered_count=Count('questions', filter=Q(questions__answer__isnull=False))
        ).order_by('-created_at')
        in_progress = [i for i in interviews if i.status == 'in_progress']
        completed = [i for i in interviews if i.status == 'completed']
        return Response({
            'in_progress': InterviewListItemSerializer(in_progress, many=True).data,
            'completed': InterviewListItemSerializer(completed, many=True).data,
        })

    def post(self, request):
        _purge_abandoned(request.user)
        if _today_interview_count(request.user) >= DAILY_INTERVIEW_LIMIT:
            return Response({'limit_reached': True}, status=status.HTTP_409_CONFLICT)

        form = InterviewForm(request.data)
        if not form.is_valid():
            return Response({'errors': form.errors}, status=status.HTTP_400_BAD_REQUEST)

        interview = form.save(commit=False)
        interview.user = request.user
        # CV metni kişisel veridir: modele yazılmaz, yalnızca soru üretimine gider.
        cv_text = form.cleaned_data['cv_text']
        interview.cv_based = bool(cv_text)

        with transaction.atomic():
            # interviews/views.py::create_interview ile aynı kilitleme: aynı kullanıcının eşzamanlı
            # istekleri günlük limiti birlikte aşamasın.
            User.objects.select_for_update().get(pk=request.user.pk)
            if _today_interview_count(request.user) >= DAILY_INTERVIEW_LIMIT:
                return Response({'limit_reached': True}, status=status.HTTP_409_CONFLICT)
            interview.save()

        try:
            questions = generate_questions(
                **_prompt_labels(interview),
                position_is_custom=interview.position == 'other',
                language=interview.language,
                question_count=interview.question_count,
                job_posting=interview.job_posting,
                cv_text=cv_text,
            )
        except GeminiError as exc:
            interview.delete()
            message, code = _gemini_error_response(exc)
            return Response({'detail': message}, status=code)

        Question.objects.bulk_create([
            Question(interview=interview, order=order, text=text, category=category)
            for order, (text, category) in enumerate(questions, start=1)
        ])
        current_question = interview.questions.order_by('order').first()
        return Response({
            'id': interview.id,
            'current_question': QuestionSerializer(current_question).data,
            'total_count': interview.question_count,
        }, status=status.HTTP_201_CREATED)


class InterviewDetailView(APIView):
    def get(self, request, pk):
        interview = get_object_or_404(request.user.interviews, pk=pk)
        if interview.status == 'completed':
            return Response({'id': interview.id, 'status': 'completed'})

        current_question = _current_question(interview)
        if current_question is None and not interview.questions.exists():
            # interviews/views.py::interview_detail ile aynı: soruları hiç üretilememiş mülakat.
            if _is_abandoned(interview):
                interview.delete()
                return Response(
                    {'detail': 'Bu mülakatın soruları hazırlanamamıştı, bu yüzden silindi. '
                               'Yeni bir mülakat başlatabilirsin.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {'detail': 'Bu mülakatın soruları hâlâ hazırlanıyor. Birkaç dakika sonra tekrar dene.'},
                status=status.HTTP_409_CONFLICT,
            )
        if current_question is None:
            # interviews/views.py::interview_detail ile aynı kurtarma: tüm sorular
            # cevaplanmış ama tamamlama adımı önceki bir hata/zaman aşımından kalmışsa tekrar dener.
            _complete_interview(interview)
            return Response({'id': interview.id, 'status': 'completed'})

        answered = interview.questions.filter(answer__isnull=False).order_by('order')
        return Response({
            'id': interview.id,
            'status': interview.status,
            'language': interview.language,
            'question_count': interview.question_count,
            'answered_count': answered.count(),
            'current_question': QuestionSerializer(current_question).data,
            'answered_questions': AnsweredQuestionSerializer(answered, many=True).data,
        })


class AnswerView(APIView):
    def post(self, request, pk):
        interview = get_object_or_404(request.user.interviews, pk=pk)

        question_id = request.data.get('question_id')
        answer_text = str(request.data.get('text', '')).strip()
        if not question_id or not answer_text:
            return Response({'detail': 'Cevap boş olamaz.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(answer_text) > MAX_ANSWER_LENGTH:
            return Response({'detail': answer_too_long_message()}, status=status.HTTP_400_BAD_REQUEST)

        question = get_object_or_404(
            Question, pk=question_id, interview=interview, answer__isnull=True
        )

        try:
            labels = _prompt_labels(interview)
            result = evaluate_answer(
                position_label=labels['position_label'],
                level_label=labels['level_label'],
                language=interview.language,
                question_text=question.text,
                answer_text=answer_text,
            )
        except GeminiError as exc:
            message, code = _gemini_error_response(exc)
            return Response({'detail': f'{message} Yazdığın cevap korundu.'}, status=code)

        Answer.objects.create(question=question, text=answer_text, **result)

        next_question = _current_question(interview)
        if next_question:
            return Response({'done': False, 'next_question': QuestionSerializer(next_question).data})

        _complete_interview(interview)
        return Response({'done': True, 'report_url': f'/api/v1/interviews/{interview.pk}/report/'})


class InterviewReportView(APIView):
    def get(self, request, pk):
        interview = get_object_or_404(request.user.interviews, pk=pk, status='completed')
        answers = Answer.objects.filter(question__interview=interview).order_by('question__order')
        return Response({
            'overall_score': interview.overall_score,
            'summary': interview.summary,
            'top_strength': interview.top_strength,
            'top_improvement': interview.top_improvement,
            'answers': ReportAnswerSerializer(answers, many=True).data,
        })
