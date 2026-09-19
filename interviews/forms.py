from django import forms

from .models import Interview

FIELD_NAMES = ['position', 'level', 'interview_type', 'language', 'question_count']

STEP_TITLES = {
    'position': 'Hangi pozisyon için hazırlanıyorsun?',
    'level': 'Hangi seviyedesin?',
    'interview_type': 'Nasıl bir mülakat olsun?',
    'language': 'Hangi dilde konuşalım?',
    'question_count': 'Kaç soru olsun?',
}

# Özet çubuğundaki, henüz seçilmemiş alanın yer tutucu adı.
STEP_SHORT_NAMES = {
    'position': 'Pozisyon',
    'level': 'Seviye',
    'interview_type': 'Tür',
    'language': 'Dil',
    'question_count': 'Soru sayısı',
}

# Seçeneklerin görsel bilgisi (docs/mulakat2.md §12.3). Anahtarlar seçenek değerinin str hâlidir.
OPTION_META = {
    'position': {
        'junior_developer': {'icon': '💻'},
        'frontend_developer': {'icon': '🎨'},
        'backend_developer': {'icon': '⚙️'},
        'data_analyst': {'icon': '📊'},
        'business_analyst': {'icon': '💼'},
        'intern_general': {'icon': '🌱'},
    },
    'interview_type': {
        'technical': {'color': 'violet', 'hint': 'Kod, kavram ve problem çözme'},
        'behavioral': {'color': 'coral', 'hint': 'Deneyim, iletişim ve motivasyon'},
        'mixed': {'color': 'sun', 'hint': 'İkisinden de biraz'},
    },
    'language': {
        'tr': {'flag': 'tr'},
        'en': {'flag': 'en'},
    },
    'question_count': {
        '5': {'duration': '~10 dk', 'summary': '5 soru'},
        '8': {'duration': '~16 dk', 'summary': '8 soru'},
        '10': {'duration': '~20 dk', 'summary': '10 soru'},
    },
}


class InterviewForm(forms.ModelForm):
    # İlana özel mülakat: isteğe bağlı iş ilanı metni. Çok kısa metin soruları ilana
    # özelleştirmez; çok uzun metin istem boyutunu ve gecikmeyi büyütür.
    JOB_POSTING_MIN = 50
    JOB_POSTING_MAX = 6000

    # CV'ye özel mülakat: CV metni modelin alanı değildir (kişisel veri; saklanmaz), yalnızca
    # soru üretimine gider. Kişisel veri Gemini'nin ücretsiz katmanına gideceği için açık onay
    # ister (docs §2.2).
    CV_MIN = 100
    CV_MAX = 8000
    cv_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 10,
            'placeholder': 'Eğitim, deneyim, proje ve becerilerini buraya yapıştır (ad ve adresini çıkarabilirsin)',
            'aria-describedby': 'cv-hint cv-privacy cv-count',
        }),
    )
    cv_consent = forms.BooleanField(required=False)

    class Meta:
        model = Interview
        fields = FIELD_NAMES + ['job_posting']
        widgets = {
            **{name: forms.RadioSelect for name in FIELD_NAMES},
            'job_posting': forms.Textarea(attrs={
                'rows': 8,
                'placeholder': 'İlan metnini buraya yapıştır (görev tanımı, aranan nitelikler, kullanılan teknolojiler...)',
                'aria-describedby': 'posting-hint posting-count',
            }),
        }

    def clean_job_posting(self):
        text = (self.cleaned_data.get('job_posting') or '').replace('\r\n', '\n').strip()
        if not text:
            return ''
        if len(text) < self.JOB_POSTING_MIN:
            raise forms.ValidationError(
                f'İlan metni çok kısa. En az {self.JOB_POSTING_MIN} karakter yapıştır ya da bu alanı boş bırak.'
            )
        if len(text) > self.JOB_POSTING_MAX:
            raise forms.ValidationError(
                f'İlan metni çok uzun ({len(text)} karakter). En fazla {self.JOB_POSTING_MAX} karakter '
                'olabilir; görevler ve aranan nitelikler bölümünü bırakman yeterli.'
            )
        return text

    def clean_cv_text(self):
        text = (self.cleaned_data.get('cv_text') or '').replace('\r\n', '\n').strip()
        if not text:
            return ''
        if len(text) < self.CV_MIN:
            raise forms.ValidationError(
                f'CV metni çok kısa. En az {self.CV_MIN} karakter yapıştır ya da bu alanı boş bırak.'
            )
        if len(text) > self.CV_MAX:
            raise forms.ValidationError(
                f'CV metni çok uzun ({len(text)} karakter). En fazla {self.CV_MAX} karakter '
                'olabilir; eğitim, deneyim, proje ve beceri bölümlerini bırakman yeterli.'
            )
        return text

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('cv_text') and not cleaned.get('cv_consent'):
            self.add_error(
                'cv_consent', 'CV metnini göndermek için gizlilik onayını işaretlemelisin.'
            )
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Radio grubunda "---------" boş seçeneği anlamsız; seçim zorunlu.
        for name in FIELD_NAMES:
            field = self.fields[name]
            field.choices = [choice for choice in field.choices if choice[0] != '']

    @property
    def steps(self):
        """Şablonun çip gruplarını çizmesi için adım adım seçenek listesi."""
        steps = []
        for number, name in enumerate(FIELD_NAMES, start=1):
            bound_field = self[name]
            options = []
            for radio in bound_field:
                value = str(radio.data['value'])
                meta = OPTION_META.get(name, {}).get(value, {})
                options.append({
                    'id': radio.id_for_label,
                    'name': radio.data['name'],
                    'value': value,
                    'label': radio.choice_label,
                    'checked': radio.data['selected'],
                    'summary': meta.get('summary', radio.choice_label),
                    **meta,
                })
            steps.append({
                'number': number,
                'name': name,
                'title': STEP_TITLES[name],
                'short_name': STEP_SHORT_NAMES[name],
                'options': options,
                'errors': bound_field.errors,
            })
        return steps
