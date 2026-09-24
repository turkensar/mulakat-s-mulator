from decimal import Decimal

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .services.gemini import GeminiError, GeminiQuotaError, GeminiTimeoutError, evaluate_answer, generate_questions

SESSION_KEY = 'guest_trial'
GUEST_QUESTION_COUNT = 2

SLOW_MESSAGE = _('Yapay zeka servisi şu an yavaş ya da yoğun. Birkaç dakika sonra tekrar dene.')
QUOTA_MESSAGE = _(
    'Yapay zeka servisinin ücretsiz kullanım kotası şu an dolu. Birkaç dakika sonra tekrar dene.'
)


@require_POST
@ratelimit(key='ip', rate='3/d', method='POST', block=False)
def guest_trial_start(request):
    if request.user.is_authenticated:
        return redirect('interview_create')

    if getattr(request, 'limited', False):
        messages.error(
            request,
            _('Bugünlük misafir deneme hakkını kullandın. Yarın tekrar deneyebilir ya da hesap açabilirsin.'),
        )
        return redirect('home')

    try:
        questions = generate_questions(
            position_label=_('Genel'),
            level_label=_('Junior'),
            interview_type_label=_('Karışık'),
            language=request.LANGUAGE_CODE,
            question_count=GUEST_QUESTION_COUNT,
        )
    except GeminiQuotaError:
        messages.error(request, QUOTA_MESSAGE)
        return redirect('home')
    except GeminiTimeoutError:
        messages.error(request, SLOW_MESSAGE)
        return redirect('home')
    except GeminiError:
        messages.error(request, _('Sorular oluşturulurken bir hata oluştu. Lütfen tekrar dene.'))
        return redirect('home')

    request.session[SESSION_KEY] = {
        'questions': [{'text': text, 'category': category} for text, category in questions],
        'answers': [],
        'language': request.LANGUAGE_CODE,
    }
    return redirect('guest_trial')


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
        return redirect('home')

    index = len(trial['answers'])
    if index >= len(trial['questions']):
        return redirect('guest_trial_result')

    answer_text = request.POST.get('answer', '').strip()
    if not answer_text:
        messages.error(request, _('Cevap boş olamaz.'))
        return redirect('guest_trial')

    question = trial['questions'][index]
    try:
        result = evaluate_answer(
            position_label=_('Genel'),
            level_label=_('Junior'),
            language=trial['language'],
            question_text=question['text'],
            answer_text=answer_text,
        )
    except GeminiQuotaError:
        messages.error(request, QUOTA_MESSAGE)
        return redirect('guest_trial')
    except GeminiTimeoutError:
        messages.error(request, SLOW_MESSAGE)
        return redirect('guest_trial')
    except GeminiError:
        messages.error(request, _('Değerlendirme sırasında bir hata oluştu. Lütfen tekrar dene.'))
        return redirect('guest_trial')

    trial['answers'].append({'text': answer_text, 'score': result['score']})
    request.session[SESSION_KEY] = trial
    request.session.modified = True

    if len(trial['answers']) >= len(trial['questions']):
        return redirect('guest_trial_result')
    return redirect('guest_trial')


def guest_trial_result(request):
    trial = request.session.get(SESSION_KEY)
    if not trial or len(trial['answers']) < len(trial['questions']):
        return redirect('home')

    scores = [a['score'] for a in trial['answers']]
    average = Decimal(sum(scores)) / Decimal(len(scores))
    del request.session[SESSION_KEY]

    return render(request, 'interviews/guest_result.html', {'average_score': average})
