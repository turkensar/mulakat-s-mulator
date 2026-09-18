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
    class Meta:
        model = Interview
        fields = FIELD_NAMES
        widgets = {name: forms.RadioSelect for name in FIELD_NAMES}

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
