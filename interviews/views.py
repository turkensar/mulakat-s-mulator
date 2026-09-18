from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import InterviewForm
from .models import Question
from .services.gemini import GeminiError, generate_questions


def home(request):
    return render(request, 'home.html')


@login_required
def panel(request):
    return render(request, 'interviews/panel.html')


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


@login_required
def interview_detail(request, pk):
    interview = get_object_or_404(request.user.interviews, pk=pk)
    return render(request, 'interviews/detail.html', {'interview': interview})
