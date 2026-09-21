import re

from django import forms
from django.utils.translation import gettext as gettext_now
from django.utils.translation import gettext_lazy as _

from .models import Interview

FIELD_NAMES = ['position', 'level', 'interview_type', 'language', 'question_count']

STEP_TITLES = {
    'position': _('Hangi pozisyon için hazırlanıyorsun?'),
    'level': _('Hangi seviyedesin?'),
    'interview_type': _('Nasıl bir mülakat olsun?'),
    'language': _('Hangi dilde konuşalım?'),
    'question_count': _('Kaç soru olsun?'),
}

# Özet çubuğundaki, henüz seçilmemiş alanın yer tutucu adı.
STEP_SHORT_NAMES = {
    'position': _('Pozisyon'),
    'level': _('Seviye'),
    'interview_type': _('Tür'),
    'language': _('Dil'),
    'question_count': _('Soru sayısı'),
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
        'other': {'icon': '✨'},
    },
    'interview_type': {
        'technical': {'color': 'violet', 'hint': _('Alanına özgü bilgi ve problem çözme')},
        'behavioral': {'color': 'coral', 'hint': _('Deneyim, iletişim ve motivasyon')},
        'mixed': {'color': 'sun', 'hint': _('İkisinden de biraz')},
    },
    'language': {
        'tr': {'flag': 'tr'},
        'en': {'flag': 'en'},
    },
    'question_count': {
        '5': {'duration': _('~10 dk'), 'summary': _('5 soru')},
        '8': {'duration': _('~16 dk'), 'summary': _('8 soru')},
        '10': {'duration': _('~20 dk'), 'summary': _('10 soru')},
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

    # "Diğer" pozisyon: yazılım dışı alanlar için kullanıcı mülakatı kısaca kendisi tarif eder.
    CUSTOM_POSITION_MIN = 3
    CUSTOM_POSITION_MAX = 160
    cv_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 10,
            'placeholder': _('Eğitim, deneyim, proje ve becerilerini buraya yapıştır (ad ve adresini çıkarabilirsin)'),
            'aria-describedby': 'cv-hint cv-privacy cv-count',
        }),
    )
    cv_consent = forms.BooleanField(required=False)

    class Meta:
        model = Interview
        fields = FIELD_NAMES + ['custom_position', 'job_posting']
        widgets = {
            **{name: forms.RadioSelect for name in FIELD_NAMES},
            'custom_position': forms.TextInput(attrs={
                'placeholder': _('Örn: Pazarlama uzmanı, e-ticaret şirketi'),
                'aria-describedby': 'other-hint',
                'autocomplete': 'off',
            }),
            'job_posting': forms.Textarea(attrs={
                'rows': 8,
                'placeholder': _('İlan metnini buraya yapıştır (görev tanımı, aranan nitelikler, kullanılan teknolojiler...)'),
                'aria-describedby': 'posting-hint posting-count',
            }),
        }

    def clean_custom_position(self):
        # Tek satır, boşluklar toplanır; < > istemdeki sınırlayıcıları taklit edemesin diye atılır.
        text = re.sub(r'\s+', ' ', self.cleaned_data.get('custom_position') or '').strip()
        return text.replace('<', '').replace('>', '')

    def clean_job_posting(self):
        text = (self.cleaned_data.get('job_posting') or '').replace('\r\n', '\n').strip()
        if not text:
            return ''
        if len(text) < self.JOB_POSTING_MIN:
            raise forms.ValidationError(
                gettext_now('İlan metni çok kısa. En az %(min)d karakter yapıştır ya da bu alanı boş bırak.')
                % {'min': self.JOB_POSTING_MIN}
            )
        if len(text) > self.JOB_POSTING_MAX:
            raise forms.ValidationError(
                gettext_now(
                    'İlan metni çok uzun (%(length)d karakter). En fazla %(max)d karakter '
                    'olabilir; görevler ve aranan nitelikler bölümünü bırakman yeterli.'
                ) % {'length': len(text), 'max': self.JOB_POSTING_MAX}
            )
        return text

    def clean_cv_text(self):
        text = (self.cleaned_data.get('cv_text') or '').replace('\r\n', '\n').strip()
        if not text:
            return ''
        if len(text) < self.CV_MIN:
            raise forms.ValidationError(
                gettext_now('CV metni çok kısa. En az %(min)d karakter yapıştır ya da bu alanı boş bırak.')
                % {'min': self.CV_MIN}
            )
        if len(text) > self.CV_MAX:
            raise forms.ValidationError(
                gettext_now(
                    'CV metni çok uzun (%(length)d karakter). En fazla %(max)d karakter '
                    'olabilir; eğitim, deneyim, proje ve beceri bölümlerini bırakman yeterli.'
                ) % {'length': len(text), 'max': self.CV_MAX}
            )
        return text

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('position') == 'other':
            custom = cleaned.get('custom_position', '')
            if len(custom) < self.CUSTOM_POSITION_MIN:
                self.add_error('custom_position', gettext_now(
                    'Diğer\'i seçtin; hazırlandığın mülakatı kısaca yaz (en az %(min)d karakter).'
                ) % {'min': self.CUSTOM_POSITION_MIN})
        elif 'position' in cleaned:
            cleaned['custom_position'] = ''  # başka pozisyon seçildiyse eski tarif saklanmaz
        if cleaned.get('cv_text') and not cleaned.get('cv_consent'):
            self.add_error(
                'cv_consent', gettext_now('CV metnini göndermek için gizlilik onayını işaretlemelisin.')
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
