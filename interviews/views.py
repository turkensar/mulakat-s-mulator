import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import InterviewForm
from .models import Answer, Question
from .services.gemini import GeminiError, evaluate_answer, generate_questions, summarize_interview


def home(request):
    return render(request, 'home.html')


@login_required
def panel(request):
    interviews = request.user.interviews.all()
    return render(request, 'interviews/panel.html', {'interviews': interviews})


@login_required
def create_interview(request):
    if request.method == 'POST':
        form = InterviewForm(request.POST)
        if form.is_valid():
            interview = form.save(commit=False)

            try:
                questions = generate_questions(
                    position_label=interview.get_position_display(),
                    level_label=interview.get_level_display(),
                    interview_type_label=interview.get_interview_type_display(),
                    language=interview.language,
                    question_count=interview.question_count,
                )
            except GeminiError:
                form.add_error(
                    None, 'Sorular oluşturulurken bir hata oluştu. Lütfen tekrar dene.'
                )
            else:
                interview.user = request.user
                interview.save()
                Question.objects.bulk_create([
                    Question(interview=interview, order=order, text=text, category=category)
                    for order, (text, category) in enumerate(questions, start=1)
                ])
                return redirect('interview_detail', pk=interview.pk)
    else:
        form = InterviewForm()

    return render(request, 'interviews/create.html', {'form': form})


def _current_question(interview):
    return interview.questions.filter(answer__isnull=True).order_by('order').first()


@login_required
def interview_detail(request, pk):
    interview = get_object_or_404(request.user.interviews, pk=pk)
    if interview.status == 'completed':
        return redirect('interview_report', pk=interview.pk)

    answered_questions = interview.questions.filter(answer__isnull=False).order_by('order')
    context = {
        'interview': interview,
        'answered_questions': answered_questions,
        'current_question': _current_question(interview),
        'answered_count': answered_questions.count(),
        'total_count': interview.question_count,
    }
    return render(request, 'interviews/detail.html', context)


def _complete_interview(interview):
    answers = Answer.objects.filter(question__interview=interview).order_by('question__order')
    scores = [answer.score for answer in answers]
    interview.overall_score = Decimal(sum(scores)) / Decimal(len(scores))

    try:
        summary = summarize_interview(
            position_label=interview.get_position_display(),
            level_label=interview.get_level_display(),
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
        return JsonResponse({'status': 'error', 'message': 'Geçersiz istek.'}, status=400)

    if not answer_text:
        return JsonResponse(
            {'status': 'error', 'message': 'Cevap boş olamaz.'}, status=400
        )

    question = get_object_or_404(
        Question, pk=question_id, interview=interview, answer__isnull=True
    )

    try:
        result = evaluate_answer(
            position_label=interview.get_position_display(),
            level_label=interview.get_level_display(),
            language=interview.language,
            question_text=question.text,
            answer_text=answer_text,
        )
    except GeminiError:
        return JsonResponse(
            {
                'status': 'error',
                'message': 'Değerlendirme sırasında bir hata oluştu. Lütfen tekrar dene.',
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
