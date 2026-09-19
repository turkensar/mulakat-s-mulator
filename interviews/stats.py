"""Gelişim sayfası için istatistikler; yalnızca veritabanındaki tamamlanmış mülakatlardan
hesaplanır, Gemini çağrısı gerektirmez."""

from django.db.models import Avg, Count
from django.utils import formats, timezone

from .models import Answer, CATEGORY_CHOICES

# Bu puanın altındaki cevaplar "üzerinde çalış" listesine girer (8 ve üstü "yüksek" aralıktır).
WEAK_SCORE_LIMIT = 8
WEAKEST_COUNT = 3


def _number(value):
    return formats.number_format(value, decimal_pos=1)


def _category_insight(categories):
    """İki kategori arasında belirgin (>= 0,5 puan) fark varsa kısa bir yönlendirme cümlesi."""
    if len(categories) != 2:
        return ''
    low, high = sorted(categories, key=lambda c: c['avg'])
    if high['avg'] - low['avg'] < 0.5:
        return ''
    return (
        f"{low['label']} sorularında ortalaman {_number(low['avg'])}, "
        f"{high['label'].lower()} sorularında {_number(high['avg'])}. "
        f"Önce {low['label'].lower()} alana odaklanabilirsin."
    )


def build_progress(user):
    completed = list(
        user.interviews.filter(status='completed', overall_score__isnull=False)
        .order_by('completed_at')
    )

    points = []
    for interview in completed:
        local = timezone.localtime(interview.completed_at)
        points.append({
            'id': interview.pk,
            'label': formats.date_format(local, 'j E'),
            'date': formats.date_format(local, 'j E Y'),
            'score': round(float(interview.overall_score), 1),
            'score_text': _number(interview.overall_score),
            'position': interview.get_position_display(),
            'type': interview.get_interview_type_display(),
        })

    stats = {'count': len(points)}
    if points:
        scores = [point['score'] for point in points]
        stats['average'] = round(sum(scores) / len(scores), 1)
        stats['average_text'] = _number(stats['average'])
        stats['best'] = max(scores)
        stats['best_text'] = _number(stats['best'])
        stats['last'] = scores[-1]
        stats['last_text'] = _number(scores[-1])
        if len(scores) >= 2:
            delta = round(scores[-1] - scores[-2], 1)
            stats['delta_text'] = ('+' if delta > 0 else '') + _number(delta)
            stats['trend'] = 'up' if delta > 0 else 'down' if delta < 0 else 'flat'

    answers = Answer.objects.filter(
        question__interview__user=user, question__interview__status='completed'
    )
    labels = dict(CATEGORY_CHOICES)
    categories = [
        {
            'key': row['question__category'],
            'label': labels.get(row['question__category'], row['question__category']),
            'avg': round(float(row['avg']), 1),
            'avg_text': _number(row['avg']),
            'percent': round(float(row['avg']) * 10),
            'count': row['count'],
        }
        for row in answers.values('question__category')
        .annotate(avg=Avg('score'), count=Count('id'))
        .order_by('question__category')
    ]

    weakest = list(
        answers.filter(score__lt=WEAK_SCORE_LIMIT)
        .select_related('question__interview')
        .order_by('score', '-created_at')[:WEAKEST_COUNT]
    )

    return {
        'points': points,
        'chart_data': {'points': points},
        'stats': stats,
        'categories': categories,
        'category_insight': _category_insight(categories),
        'weakest': weakest,
    }
