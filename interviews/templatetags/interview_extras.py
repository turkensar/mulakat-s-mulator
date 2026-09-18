import re

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def score_band(value):
    """Puanı renk aralığına çevirir: 1-4 'low' (coral), 5-7 'mid' (sun), 8-10 'high' (mint).

    Genel skor ondalıklı olabildiği için sınırlar 5 ve 8'den küçük/büyük olarak alınır.
    """
    try:
        score = float(value)
    except (TypeError, ValueError):
        return ''
    if score < 5:
        return 'low'
    if score < 8:
        return 'mid'
    return 'high'


@register.filter
def inline_markup(value):
    """AI metnindeki **kalın** ve `kod` işaretlerini HTML'e çevirir.

    Önce tüm metin escape edildiği için üretilen etiketler dışında HTML geçemez.
    """
    text = str(conditional_escape(value))
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', text)
    return mark_safe(text)
