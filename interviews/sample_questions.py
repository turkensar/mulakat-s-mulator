"""Faz 4'te Gemini soru üretimi gelince bu modül kaldırılacak."""

TECHNICAL_QUESTIONS = {
    'tr': [
        'Bir projede en son karşılaştığın zorlu bir teknik problemi ve çözümünü anlatır mısın?',
        'Değişken ile sabit arasındaki farkı nasıl açıklarsın?',
        'Bir kod parçasını test etmeye nasıl yaklaşırsın?',
        'Versiyon kontrol sistemlerini (örn. Git) hangi amaçla kullanırsın?',
        'Bir algoritmanın zaman karmaşıklığını nasıl değerlendirirsin?',
        'API nedir ve neden kullanılır, kısaca anlatır mısın?',
        'Veritabanı ile dosya sistemi arasındaki temel farklar nelerdir?',
        'Bir hatayı (bug) nasıl adım adım debug edersin?',
        'Nesne yönelimli programlamanın temel prensiplerinden birini örnekle açıklar mısın?',
        'Bir yazılım projesinde okunabilir kod yazmak için nelere dikkat edersin?',
    ],
    'en': [
        'Tell me about a challenging technical problem you solved recently.',
        'How would you explain the difference between a variable and a constant?',
        'How do you approach testing a piece of code?',
        'Why do you use version control systems such as Git?',
        'How do you evaluate the time complexity of an algorithm?',
        'Can you briefly explain what an API is and why it is used?',
        'What are the key differences between a database and a file system?',
        'How do you debug an issue step by step?',
        'Can you explain one core principle of object-oriented programming with an example?',
        'What do you pay attention to in order to write readable code?',
    ],
}

BEHAVIORAL_QUESTIONS = {
    'tr': [
        'Kendini kısaca tanıtır mısın?',
        'Takım içinde bir anlaşmazlık yaşadığın bir durumu nasıl çözdün?',
        'Baskı altında çalışman gereken bir dönemi nasıl yönettin?',
        'Bir hata yaptığında bunu nasıl fark ettin ve ne yaptın?',
        'Neden bu pozisyona başvurdun?',
        'Kendini geliştirmek için son zamanlarda ne yaptın?',
        'Zor bir geri bildirim aldığında nasıl tepki verirsin?',
        'Zamanını verimli yönetmek için hangi yöntemleri kullanıyorsun?',
        'Bir projede liderlik üstlendiğin bir anı anlatır mısın?',
        'Beş yıl sonra kendini nerede görüyorsun?',
    ],
    'en': [
        'Can you briefly introduce yourself?',
        'Tell me about a time you resolved a disagreement within a team.',
        'How did you manage a period where you had to work under pressure?',
        'How did you notice a mistake you made, and what did you do about it?',
        'Why did you apply for this position?',
        'What have you recently done to improve yourself?',
        'How do you react when you receive difficult feedback?',
        'What methods do you use to manage your time effectively?',
        'Tell me about a time you took a leadership role in a project.',
        'Where do you see yourself in five years?',
    ],
}


def build_questions(interview_type, language, question_count):
    """(soru_metni, kategori) çiftlerinden oluşan sabit bir soru listesi döner."""
    technical = [(q, 'teknik') for q in TECHNICAL_QUESTIONS[language]]
    behavioral = [(q, 'davranissal') for q in BEHAVIORAL_QUESTIONS[language]]

    if interview_type == 'technical':
        pool = technical
    elif interview_type == 'behavioral':
        pool = behavioral
    else:
        pool = [technical[i // 2] if i % 2 == 0 else behavioral[i // 2] for i in range(len(technical) * 2)]

    return [pool[i % len(pool)] for i in range(question_count)]
