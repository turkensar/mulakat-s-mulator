import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from .forms import InterviewForm
from .models import Answer, DAILY_INTERVIEW_LIMIT, Question
from .services.gemini import (
    GeminiError, GeminiQuotaError, evaluate_answer, generate_questions, summarize_interview,
)
from .stats import build_progress

QUOTA_MESSAGE = gettext_lazy(
    'Yapay zeka servisinin ücretsiz kullanım kotası şu an dolu. '
    'Birkaç dakika sonra ya da yarın tekrar dene.'
)


def home(request):
    return render(request, 'home.html')


@login_required
def panel(request):
    # Meta.ordering, aggregate içeren sorgularda uygulanmaz; sıralamayı açıkça veriyoruz.
    interviews = request.user.interviews.annotate(
        answered_count=Count('questions', filter=Q(questions__answer__isnull=False))
    ).order_by('-created_at')
    context = {
        'in_progress': [i for i in interviews if i.status == 'in_progress'],
        'completed': [i for i in interviews if i.status == 'completed'],
    }
    return render(request, 'interviews/panel.html', context)


@login_required
def progress(request):
    return render(request, 'interviews/progress.html', build_progress(request.user))


def _today_interview_count(user):
    # created_at__date yerel saat diliminde (TIME_ZONE) karşılaştırır; now().date()
    # ise UTC tarihini verir ve gece yarısından sonraki ilk saatlerde tutmaz.
    return user.interviews.filter(created_at__date=timezone.localdate()).count()


@login_required
def create_interview(request):
    if request.method == 'POST':
        form = InterviewForm(request.POST)
        if form.is_valid():
            interview = form.save(commit=False)
            interview.user = request.user
            # CV metni kişisel veridir: modele yazılmaz, yalnızca soru üretimine gider.
            cv_text = form.cleaned_data['cv_text']
            interview.cv_based = bool(cv_text)

            with transaction.atomic():
                # Ayni kullanicinin ayni anda gonderdigi istekleri
                # serilestirmek icin kullanici satirini kilitliyoruz; aksi
                # halde iki istek ayni "gunluk say" degerini okuyup limiti
                # birlikte asabilir (race condition).
                User.objects.select_for_update().get(pk=request.user.pk)
                if _today_interview_count(request.user) >= DAILY_INTERVIEW_LIMIT:
                    return render(request, 'interviews/create.html', {'limit_reached': True})
                interview.save()

            try:
                questions = generate_questions(
                    **_prompt_labels(interview),
                    language=interview.language,
                    question_count=interview.question_count,
                    job_posting=interview.job_posting,
                    cv_text=cv_text,
                )
            except GeminiQuotaError:
                interview.delete()
                form.add_error(None, QUOTA_MESSAGE)
            except GeminiError:
                interview.delete()
                form.add_error(
                    None, _('Sorular oluşturulurken bir hata oluştu. Lütfen tekrar dene.')
                )
            else:
                Question.objects.bulk_create([
                    Question(interview=interview, order=order, text=text, category=category)
                    for order, (text, category) in enumerate(questions, start=1)
                ])
                return redirect('interview_detail', pk=interview.pk)
    else:
        if _today_interview_count(request.user) >= DAILY_INTERVIEW_LIMIT:
            return render(request, 'interviews/create.html', {'limit_reached': True})
        form = InterviewForm()

    return render(request, 'interviews/create.html', {'form': form})


def _prompt_labels(interview):
    """Gemini istemlerine giden pozisyon/seviye/tür etiketleri.

    İstemler Türkçe yazıldığı ve modelin davranışı buna göre denendiği için, arayüz
    İngilizce iken bile etiketler her zaman Türkçe gider (mülakat dili ayrı bir ayardır).
    """
    with translation.override('tr'):
        return {
            'position_label': interview.get_position_display(),
            'level_label': interview.get_level_display(),
            'interview_type_label': interview.get_interview_type_display(),
        }


def _current_question(interview):
    return interview.questions.filter(answer__isnull=True).order_by('order').first()


def _detail_js_strings():
    """Mülakat ekranındaki JavaScript'in (şablondaki betik ve voice.js) kullandığı metinler.

    Tek kaynak burasıdır; şablon bunları json_script ile sayfaya gömer, böylece JS dosyalarında
    çevrilecek düz metin kalmaz. %(ad)s yer tutucuları JS tarafında doldurulur.
    """
    return {
        'answerEmpty': _('Cevap boş olamaz.'),
        'thinking': _('Cevabın değerlendiriliyor'),
        'thinkingFinal': _('Cevabın değerlendiriliyor ve raporun hazırlanıyor'),
        'networkError': _('Bağlantı hatası. Lütfen tekrar dene.'),
        'genericError': _('Bir hata oluştu. Lütfen tekrar dene.'),
        'question': _('Soru'),
        'listen': _('🔊 Dinle'),
        'listenStop': _('⏹ Durdur'),
        'listenAria': _('Soruyu sesli oku'),
        'noVoice': _(
            'Bu cihazda %(lang)s konuşma sesi bulunamadı; soruları sesli okuma kullanılamıyor.'
        ),
        'micStart': _('🎙️ Sesle yaz'),
        'micStarting': _('⏳ Başlıyor…'),
        'micStop': _('⏹ Bitir'),
        'micBusy': _('Cevap gönderilirken sesle yazılamaz; değerlendirme bitince tekrar dene.'),
        'micSlow': _(
            'Ses tanıma henüz başlamadı. Adres çubuğunda mikrofon izni penceresi varsa "İzin ver"e bas; '
            'yoksa sayfayı Ctrl+F5 ile yenileyip tekrar dene ya da Chrome/Edge kullan.'
        ),
        'micClosed': _('Ses tanıma başlamadan kapandı. Tekrar dene; sürerse Chrome/Edge kullan.'),
        'micFailed': _('Ses tanıma başlatılamadı (%(error)s). Birkaç saniye sonra tekrar dene.'),
        'micGeneric': _('Ses tanıma sırasında bir sorun oluştu (%(error)s).'),
        'unknownError': _('bilinmeyen hata'),
        'speechErrors': {
            'not-allowed': _(
                'Mikrofon izni verilmedi. Tarayıcının adres çubuğundaki izin ayarından mikrofona izin ver.'
            ),
            'service-not-allowed': _('Bu tarayıcı ses tanıma hizmetine izin vermiyor.'),
            'no-speech': _('Ses algılanmadı. Mikrofona yakın konuşup tekrar dene.'),
            'audio-capture': _('Mikrofon bulunamadı. Bir mikrofon bağlı olduğundan emin ol.'),
            'network': _(
                'Ses tanıma hizmetine ulaşılamadı. İnternet bağlantını kontrol edip tekrar dene.'
            ),
            'language-not-supported': _('%(lang)s için ses tanıma bu tarayıcıda desteklenmiyor.'),
        },
    }


@login_required
def interview_detail(request, pk):
    interview = get_object_or_404(request.user.interviews, pk=pk)
    if interview.status == 'completed':
        return redirect('interview_report', pk=interview.pk)

    current_question = _current_question(interview)
    if current_question is None:
        # Tum sorular cevaplanmis ama mulakat "completed" olarak
        # isaretlenmemis: son cevaptan sonraki tamamlama adimi (ozet +
        # durum guncelleme) daha once bir zaman asimi/hata yuzunden
        # bitmemis olabilir. Kullaniciyi bos bir sayfada birakmamak icin
        # tamamlama adimini burada tekrar deneyip rapora yonlendiriyoruz.
        _complete_interview(interview)
        return redirect('interview_report', pk=interview.pk)

    answered_questions = interview.questions.filter(answer__isnull=False).order_by('order')
    context = {
        'interview': interview,
        'answered_questions': answered_questions,
        'current_question': current_question,
        'answered_count': answered_questions.count(),
        'total_count': interview.question_count,
        'js_strings': _detail_js_strings(),
        # Sesli okuma/dikte için mülakat dilinin adı, ARAYÜZ dilinde gösterilir.
        'speech_name': _('Türkçe') if interview.language == 'tr' else _('İngilizce'),
    }
    return render(request, 'interviews/detail.html', context)


def _complete_interview(interview):
    answers = Answer.objects.filter(question__interview=interview).order_by('question__order')
    scores = [answer.score for answer in answers]
    interview.overall_score = Decimal(sum(scores)) / Decimal(len(scores))

    try:
        labels = _prompt_labels(interview)
        summary = summarize_interview(
            position_label=labels['position_label'],
            level_label=labels['level_label'],
            language=interview.language,
            qa_pairs=[(a.question.text, a.text, a.score) for a in answers],
        )
    except GeminiError:
        summary = None

    if summary:
        interview.summary = summary['summary']
        interview.top_strength = summary['top_strength']
        interview.top_improvement = summary['top_improvement']

    interview.status = 'completed'
    interview.completed_at = timezone.now()
    interview.save()


@login_required
@require_POST
def submit_answer(request, pk):
    interview = get_object_or_404(request.user.interviews, pk=pk)

    try:
        payload = json.loads(request.body)
        question_id = int(payload['question_id'])
        answer_text = str(payload['text']).strip()
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'status': 'error', 'message': _('Geçersiz istek.')}, status=400)

    if not answer_text:
        return JsonResponse(
            {'status': 'error', 'message': _('Cevap boş olamaz.')}, status=400
        )

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
    except GeminiQuotaError:
        return JsonResponse(
            {'status': 'error', 'message': f"{QUOTA_MESSAGE} {_('Yazdığın cevap korundu.')}"},
            status=503,
        )
    except GeminiError:
        return JsonResponse(
            {
                'status': 'error',
                'message': _('Değerlendirme sırasında bir hata oluştu. Lütfen tekrar dene.'),
            },
            status=502,
        )

    Answer.objects.create(question=question, text=answer_text, **result)

    next_question = _current_question(interview)
    if next_question:
        return JsonResponse({
            'status': 'ok',
            'done': False,
            'next_question': {
                'id': next_question.id,
                'order': next_question.order,
                'text': next_question.text,
                'category': next_question.get_category_display(),
            },
        })

    _complete_interview(interview)
    return JsonResponse({
        'status': 'ok',
        'done': True,
        'report_url': reverse('interview_report', kwargs={'pk': interview.pk}),
    })


@login_required
def interview_report(request, pk):
    interview = get_object_or_404(request.user.interviews, pk=pk, status='completed')
    answers = Answer.objects.filter(question__interview=interview).order_by('question__order')
    return render(request, 'interviews/report.html', {'interview': interview, 'answers': answers})
