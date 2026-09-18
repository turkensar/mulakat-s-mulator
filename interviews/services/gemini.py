"""Tüm Gemini API çağrıları bu dosyada toplanır."""

import logging

from django.conf import settings
from google import genai
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_client = None


class GeminiError(Exception):
    """Gemini API çağrısı başarısız olduğunda veya beklenmeyen bir yanıt geldiğinde fırlatılır."""


class _QuestionItem(BaseModel):
    order: int
    text: str
    category: str


class _QuestionList(BaseModel):
    questions: list[_QuestionItem]


class _AnswerEvaluation(BaseModel):
    score: int
    strengths: str
    improvements: str
    sample_answer: str
    language_score: int | None = None
    language_feedback: str | None = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


_LANGUAGE_NAMES = {
    'tr': 'Türkçe',
    'en': 'English',
}


def _create_interaction(*, prompt, system_instruction, schema, thinking_level):
    try:
        interaction = _get_client().interactions.create(
            model=settings.GEMINI_MODEL,
            input=prompt,
            system_instruction=system_instruction,
            response_format={
                'type': 'text',
                'mime_type': 'application/json',
                'schema_': schema,
            },
            generation_config={'thinking_level': thinking_level},
            timeout=60,
        )
    except Exception as exc:
        logger.exception('Gemini API çağrısı başarısız oldu.')
        raise GeminiError('Gemini API çağrısı başarısız oldu.') from exc

    if interaction.output_text is None:
        raise GeminiError('Gemini API boş bir yanıt döndürdü.')

    return interaction.output_text


def generate_questions(*, position_label, level_label, interview_type_label, language, question_count):
    """Verilen kritere uygun mülakat sorularını Gemini ile üretir.

    Dönen liste (text, category) çiftlerinden oluşur; category 'teknik' ya da
    'davranissal' değerini alır.
    """
    language_name = _LANGUAGE_NAMES[language]

    system_instruction = (
        'Deneyimli bir işe alım uzmanı ve teknik mülakatçı gibi davran. '
        'Verilen pozisyon, seviye ve mülakat türüne uygun, birbirini tekrar etmeyen, '
        'gerçek mülakatlarda sorulan tarzda sorular üret. Seviye stajyer/junior '
        'olduğu için sorular bu seviyeye uygun zorlukta olmalı. '
        f'Tüm soruları {language_name} dilinde üret. '
        "Her sorunun category alanı 'teknik' veya 'davranissal' değerlerinden biri olmalı; "
        "mülakat türü teknikse tüm sorular 'teknik', davranışsalsa tüm sorular 'davranissal', "
        "karışıksa ikisinin dengeli bir karışımı olmalı."
    )

    prompt = (
        f'Pozisyon: {position_label}\n'
        f'Seviye: {level_label}\n'
        f'Mülakat türü: {interview_type_label}\n'
        f'Soru sayısı: {question_count}\n'
        f'Tam olarak {question_count} adet soru üret.'
    )

    output_text = _create_interaction(
        prompt=prompt,
        system_instruction=system_instruction,
        schema=_QuestionList.model_json_schema(),
        thinking_level='low',
    )

    try:
        parsed = _QuestionList.model_validate_json(output_text)
    except Exception as exc:
        raise GeminiError('Gemini API yanıtı beklenen JSON şemasına uymuyor.') from exc

    if len(parsed.questions) != question_count:
        raise GeminiError('Gemini API istenen sayıda soru döndürmedi.')

    return [(item.text, item.category) for item in parsed.questions]


def evaluate_answer(*, position_label, level_label, language, question_text, answer_text):
    """Kullanıcının bir soruya verdiği cevabı Gemini ile değerlendirir.

    Dönen değer bir sözlüktür: score, strengths, improvements, sample_answer,
    language_score, language_feedback. language_score/language_feedback sadece
    İngilizce mülakatlarda dolu olur, aksi halde None'dır.
    """
    language_name = _LANGUAGE_NAMES[language]

    system_instruction = (
        'Deneyimli, adil ve yapıcı bir mülakatçı gibi davran. Kullanıcının verdiği '
        'cevabı, pozisyon ve seviyeye uygun bir beklentiyle değerlendir. Boş, alakasız '
        'veya çok kısa cevaplara düşük puan ver ve nedenini açıkla. '
        f'strengths, improvements ve sample_answer alanlarını {language_name} dilinde yaz. '
        + (
            'Bu mülakat İngilizce olduğu için ayrıca language_score (1-10) ve '
            'language_feedback (akıcılık, kelime seçimi, dil bilgisi hakkında kısa bir '
            'yorum, Türkçe yazılabilir) alanlarını da doldur.'
            if language == 'en'
            else 'Bu mülakat Türkçe olduğu için language_score ve language_feedback '
            'alanlarını null bırak.'
        )
    )

    prompt = (
        f'Pozisyon: {position_label}\n'
        f'Seviye: {level_label}\n'
        f'Soru: {question_text}\n'
        f'Kullanıcının cevabı: {answer_text}'
    )

    output_text = _create_interaction(
        prompt=prompt,
        system_instruction=system_instruction,
        schema=_AnswerEvaluation.model_json_schema(),
        thinking_level='medium',
    )

    try:
        parsed = _AnswerEvaluation.model_validate_json(output_text)
    except Exception as exc:
        raise GeminiError('Gemini API yanıtı beklenen JSON şemasına uymuyor.') from exc

    if not 1 <= parsed.score <= 10:
        raise GeminiError('Gemini API geçersiz bir puan döndürdü.')

    return {
        'score': parsed.score,
        'strengths': parsed.strengths,
        'improvements': parsed.improvements,
        'sample_answer': parsed.sample_answer,
        'language_score': parsed.language_score,
        'language_feedback': parsed.language_feedback or '',
    }
