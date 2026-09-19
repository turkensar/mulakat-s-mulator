"""CV metnini yapay zekaya göndermeden önce hazırlar (docs §2.2 "CV'ye özel mülakat").

Gemini'nin ücretsiz katmanında gönderilen içerik Google tarafından ürün geliştirmede
kullanılabilir ve insanlar tarafından okunabilir; bu yüzden soru üretmeye gerekmeyen
iletişim bilgileri gönderilmeden önce silinir. Ad ve adres gibi serbest metin bilgileri
güvenilir biçimde ayıklanamaz; bunları kullanıcı kendisi çıkarır (formda söylenir).
"""

import re

EMAIL = '[e-posta]'
PHONE = '[telefon]'
LINK = '[bağlantı]'
NUMBER = '[numara]'

_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_URL_RE = re.compile(r'(?:https?://|www\.)\S+', re.IGNORECASE)
# Şemasız profil bağlantıları (linkedin.com/in/ad, github.com/kullanici ...).
_PROFILE_RE = re.compile(
    r'\b(?:[\w-]+\.)?(?:linkedin\.com|github\.com|gitlab\.com|behance\.net|dribbble\.com|'
    r'medium\.com|kaggle\.com|twitter\.com|x\.com|instagram\.com|facebook\.com)/?\S*',
    re.IGNORECASE,
)
_IBAN_RE = re.compile(r'\bTR\d{2}(?:[ ]?\d{4}){5}[ ]?\d{2}\b', re.IGNORECASE)
# 11 haneli kesintisiz sayı (T.C. kimlik no gibi).
_LONG_NUMBER_RE = re.compile(r'(?<!\d)\d{11}(?!\d)')
# Telefon adayı: rakam, boşluk, nokta, tire, parantez; başı + / 0 / ( / 5 ile başlar.
# Yıl aralıkları ("2019 - 2023") 1 ya da 2 ile başladığı için yakalanmaz.
_PHONE_RE = re.compile(r'(?<![\w.])(?:\+|\(|0|5)[\d\s().-]{7,}\d(?![\w])')


def _replace_phone(match):
    digits = re.sub(r'\D', '', match.group(0))
    return PHONE if 10 <= len(digits) <= 13 else match.group(0)


def redact_contact_info(text):
    """E-posta, telefon, bağlantı, IBAN ve 11 haneli numaraları yer tutucuyla değiştirir."""
    text = (text or '').replace('\r\n', '\n')
    text = _EMAIL_RE.sub(EMAIL, text)
    text = _URL_RE.sub(LINK, text)
    text = _PROFILE_RE.sub(LINK, text)
    text = _IBAN_RE.sub(NUMBER, text)
    text = _LONG_NUMBER_RE.sub(NUMBER, text)
    text = _PHONE_RE.sub(_replace_phone, text)
    return text.strip()


def clean_cv_text(text):
    """Soru üretme isteminde kullanılacak CV metni.

    İletişim bilgileri silinir; CV kullanıcıdan gelen güvenilmez bir metin olduğu için
    sınırlayıcı etiketi (<cv>) de kaldırılır, böylece istemin geri kalanını taklit edemez.
    """
    text = re.sub(r'<\s*/?\s*cv\s*>', '', text or '', flags=re.IGNORECASE)
    return redact_contact_info(text)
