from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import InterviewForm
from .models import Question
from .sample_questions import build_questions


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
            interview.user = request.user
            interview.save()

            questions = build_questions(
                interview.interview_type, interview.language, interview.question_count
            )
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
