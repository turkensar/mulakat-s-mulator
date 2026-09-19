from django.conf import settings
from django.db import models

DAILY_INTERVIEW_LIMIT = 3

POSITION_CHOICES = [
    ('junior_developer', 'Junior Yazılım Geliştirici'),
    ('frontend_developer', 'Frontend Geliştirici'),
    ('backend_developer', 'Backend Geliştirici'),
    ('data_analyst', 'Veri Analisti'),
    ('business_analyst', 'İş Analisti'),
    ('intern_general', 'Stajyer (Genel)'),
]

LEVEL_CHOICES = [
    ('intern', 'Stajyer'),
    ('junior', 'Junior'),
]

INTERVIEW_TYPE_CHOICES = [
    ('technical', 'Teknik'),
    ('behavioral', 'İK (Davranışsal)'),
    ('mixed', 'Karışık'),
]

LANGUAGE_CHOICES = [
    ('tr', 'Türkçe'),
    ('en', 'English'),
]

QUESTION_COUNT_CHOICES = [
    (5, '5'),
    (8, '8'),
    (10, '10'),
]

STATUS_CHOICES = [
    ('in_progress', 'Devam Ediyor'),
    ('completed', 'Tamamlandı'),
]

CATEGORY_CHOICES = [
    ('teknik', 'Teknik'),
    ('davranissal', 'Davranışsal'),
]


class Interview(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interviews')
    position = models.CharField('Pozisyon', max_length=30, choices=POSITION_CHOICES)
    level = models.CharField('Seviye', max_length=10, choices=LEVEL_CHOICES)
    interview_type = models.CharField('Mülakat Türü', max_length=15, choices=INTERVIEW_TYPE_CHOICES)
    language = models.CharField('Mülakat Dili', max_length=2, choices=LANGUAGE_CHOICES)
    question_count = models.PositiveSmallIntegerField('Soru Sayısı', choices=QUESTION_COUNT_CHOICES)
    # İlana özel mülakatta yapıştırılan iş ilanı metni; boşsa genel mülakat. db_default,
    # şema değişikliği sırasında eski kodun (sütunu bilmeyen INSERT'ler) çalışmasını sağlar.
    job_posting = models.TextField('İş ilanı', blank=True, default='', db_default='')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='in_progress')
    overall_score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    summary = models.TextField(blank=True)
    top_strength = models.TextField(blank=True)
    top_improvement = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_position_display()} ({self.user.username})'


class Question(models.Model):
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name='questions')
    order = models.PositiveSmallIntegerField()
    text = models.TextField()
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.interview_id} - Soru {self.order}'


class Answer(models.Model):
    question = models.OneToOneField(Question, on_delete=models.CASCADE, related_name='answer')
    text = models.TextField()
    score = models.PositiveSmallIntegerField()
    strengths = models.TextField()
    improvements = models.TextField()
    sample_answer = models.TextField()
    language_score = models.PositiveSmallIntegerField(null=True, blank=True)
    language_feedback = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Cevap - Soru {self.question_id}'
