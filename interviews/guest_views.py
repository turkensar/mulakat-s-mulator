from decimal import Decimal

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from config.async_forms import json_error, json_redirect, wants_json
from config.ratelimit import client_ip

from .services.gemini import GeminiError, GeminiQuotaError, GeminiTimeoutError, evaluate_answer, generate_questions

SESSION_KEY = 'guest_trial'
GUEST_QUESTION_COUNT = 2

SLOW_MESSAGE = gettext_lazy('Yapay zeka servisi şu an yavaş ya da yoğun. Birkaç dakika sonra tekrar dene.')
QUOTA_MESSAGE = gettext_lazy(
    'Yapay zeka servisinin ücretsiz kullanım kotası şu an dolu. Birkaç dakika sonra tekrar dene.'
)


def _go(request, url_name):
    if wants_json(request):
        return json_redirect(reverse(url_name))
    return redirect(url_name)


def _fail(request, message, back_to):
    """Hata: arka planda gönderimde form yerinde kalır ve mesaj gösterilir; normal
    gönderimde mesaj bir sonraki sayfada görünür."""
    if wants_json(request):
        return json_error(message)
    messages.error(request, message)
    return redirect(back_to)


def _gemini_message(exc, default):
    if isinstance(exc, GeminiQuotaError):
        return QUOTA_MESSAGE
    if isinstance(exc, GeminiTimeoutError):
        return SLOW_MESSAGE
    return default


@require_POST
@ratelimit(key=client_ip, rate='3/d', method='POST', block=False)
def guest_trial_start(request):
    if request.user.is_authenticated:
        return _go(request, 'interview_create')

    if getattr(request, 'limited', False):
        return _fail(
            request,
            _('Bugünlük misafir deneme hakkını kullandın. Yarın tekrar deneyebilir ya da hesap açabilirsin.'),
            'home',
        )

    try:
        questions = generate_questions(
            position_label=_('Genel'),
            level_label=_('Junior'),
            interview_type_label=_('Karışık'),
            language=request.LANGUAGE_CODE,
            question_count=GUEST_QUESTION_COUNT,
        )
    except GeminiError as exc:
        return _fail(
            request,
            _gemini_message(exc, _('Sorular oluşturulurken bir hata oluştu. Lütfen tekrar dene.')),
            'home',
        )

    request.session[SESSION_KEY] = {
        'questions': [{'text': text, 'category': category} for text, category in questions],
        'answers': [],
        'language': request.LANGUAGE_CODE,
    }
    return _go(request, 'guest_trial')


def guest_trial(request):
    trial = request.session.get(SESSION_KEY)
    if not trial:
        return redirect('home')

    index = len(trial['answers'])
    if index >= len(trial['questions']):
        return redirect('guest_trial_result')

    context = {
        'question': trial['questions'][index],
        'question_number': index + 1,
        'total_questions': len(trial['questions']),
    }
    return render(request, 'interviews/guest_trial.html', context)


@require_POST
def guest_trial_answer(request):
    trial = request.session.get(SESSION_KEY)
    if not trial:
        return _go(request, 'home')

    index = len(trial['answers'])
    if index >= len(trial['questions']):
        return _go(request, 'guest_trial_result')

    answer_text = request.POST.get('answer', '').strip()
    if not answer_text:
        return _fail(request, _('Cevap boş olamaz.'), 'guest_trial')

    question = trial['questions'][index]
    try:
        result = evaluate_answer(
            position_label=_('Genel'),
            level_label=_('Junior'),
            language=trial['language'],
            question_text=question['text'],
            answer_text=answer_text,
        )
    except GeminiError as exc:
        return _fail(
            request,
            _gemini_message(exc, _('Değerlendirme sırasında bir hata oluştu. Lütfen tekrar dene.')),
            'guest_trial',
        )

    trial['answers'].append({'text': answer_text, 'score': result['score']})
    request.session[SESSION_KEY] = trial
    request.session.modified = True

    if len(trial['answers']) >= len(trial['questions']):
        return _go(request, 'guest_trial_result')
    return _go(request, 'guest_trial')


def guest_trial_result(request):
    trial = request.session.get(SESSION_KEY)
    if not trial or len(trial['answers']) < len(trial['questions']):
        return redirect('home')

    scores = [a['score'] for a in trial['answers']]
    average = Decimal(sum(scores)) / Decimal(len(scores))
    del request.session[SESSION_KEY]

    return render(request, 'interviews/guest_result.html', {'average_score': average})
