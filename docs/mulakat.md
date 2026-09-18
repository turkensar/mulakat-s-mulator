# AI Mülakat Simülatörü (çalışma adı)

Bu doküman, projeyi Claude Code ile adım adım geliştirmek için hazırlanmış ana yol haritasıdır. Claude Code her yeni oturumda önce bu dosyayı okumalıdır.

---

## 1. Projenin Amacı

Üniversite öğrencilerinin ve yeni mezunların iş mülakatlarına gerçekçi bir ortamda, istedikleri kadar ve stres olmadan pratik yapabilmesini sağlamak.

Kullanıcı hedeflediği pozisyonu, seviyesini, mülakat türünü ve dilini seçer. Yapay zeka mülakatçı ona bu seçimlere uygun sorular sorar, her cevabı değerlendirir ve mülakat sonunda somut geri bildirimler içeren bir rapor sunar.

**Hedef kitle:** Üniversite öğrencileri, yeni mezunlar, staj ve junior pozisyonlara başvuranlar.

**Öncelik:** İlk hedef çalışan bir prototip. Gereksiz karmaşık teknolojilerden kaçınılacak, proje adım adım büyütülecek.

---

## 2. Özellikler

### 2.1 İlk Sürüm (Prototip / MVP)

**Kayıt ve giriş**
- E-posta, şifre ve kullanıcı adı ile kayıt.
- Giriş zorunludur (mülakat geçmişi kullanıcıya özeldir).
- E-posta hiçbir yerde görüntülenmez.

**Mülakat oluşturma**
- Pozisyon: Junior Yazılım Geliştirici, Frontend Geliştirici, Backend Geliştirici, Veri Analisti, İş Analisti, Stajyer (Genel)
- Seviye: Stajyer / Junior
- Mülakat türü: Teknik / İK (davranışsal) / Karışık
- Mülakat dili: Türkçe / English
- Soru sayısı: 5, 8 veya 10

**Mülakat ekranı**
- Sohbet benzeri arayüz.
- Sorular tek tek gösterilir, kullanıcı yazılı cevap verir.
- Üstte ilerleme göstergesi (ör. "3 / 8").
- Cevap gönderilince AI değerlendirir, ardından sıradaki soruya geçilir.
- Değerlendirme sırasında yükleniyor göstergesi.

**Değerlendirme raporu**
- En üstte genel skor (10 üzerinden) ve kısa genel değerlendirme.
- Her soru için: kullanıcının cevabı, puan (1–10), güçlü yönler, geliştirilecek yönler, örnek iyi cevap.
- İngilizce mülakatlarda ek olarak: dil kullanımı puanı ve kısa yorum (akıcılık, kelime seçimi, dil bilgisi).

**Panel (geçmiş mülakatlar)**
- Kullanıcının önceki mülakatları: pozisyon, dil, tarih, genel skor.
- Yarım kalan mülakata devam edebilme.

**Kullanım limiti**
- Kullanıcı başına günlük en fazla 3 mülakat (API maliyetini kontrol etmek için).

### 2.2 Sonraki Aşamalar

- **Sesli mülakat:** Soruların sesli okunması ve mikrofonla cevap verme. Başlangıçta tarayıcının Web Speech API'si (tr-TR / en-US), ileride Gemini 3.5 Transcribe.
- **CV'ye özel mülakat:** CV yüklenir (Supabase Storage), sorular kullanıcının deneyimleri üzerinden üretilir.
- **İlana özel mülakat:** İş ilanı metni yapıştırılır, sorular ilana göre üretilir.
- **Gelişim grafiği:** Zaman içindeki skor değişimi ve en zayıf konular (Chart.js).
- **AI takip soruları:** Cevaba göre AI'ın ek soru sorması.
- **İki dilli arayüz:** Menü ve butonların da İngilizce seçeneği.
- **Mobil uyum ve PWA.**

---

## 3. Teknolojiler

| Katman | Teknoloji |
|---|---|
| Backend | Python, Django |
| Kimlik doğrulama | Django'nun yerleşik auth sistemi |
| Veritabanı | Supabase (PostgreSQL) |
| Yapay zeka | Google Gemini API, model: `gemini-3.8-flash` |
| AI kütüphanesi | `google-genai` (Google'ın resmi Gen AI SDK'sı) |
| Frontend | Django template'leri içinde HTML, CSS, JavaScript (ayrı framework yok) |
| Stil | Sade CSS; istenirse Tailwind CSS (CDN) |
| Deploy | Vercel |
| Ortam değişkenleri | `python-dotenv` (lokal), Vercel Environment Variables (canlı) |

**Tasarım yönü:** Gençlere hitap eden modern, sade ve temiz bir arayüz. Mobilde de rahat kullanılabilmeli.

---

## 4. Gemini API Kuralları

- Model adı: `gemini-3.8-flash` (settings içinde tek bir sabitte tutulacak, ör. `GEMINI_MODEL`, böylece ileride kolayca değiştirilebilir).
- API anahtarı: `GEMINI_API_KEY` ortam değişkeninden okunur. **Asla** frontend koduna, template'e ya da GitHub'a girmez. `.env` dosyası `.gitignore` içinde olmalı.
- **Düşünme seviyesi (thinking level):**
  - Soru üretme: `low` (hızlı cevap, Vercel süre sınırına takılmamak için)
  - Cevap değerlendirme ve genel özet: `medium`
- **temperature, top_p, top_k kullanılmayacak.** Bu parametreler Gemini'de deprecated.
- Tüm AI yanıtları **structured output (JSON şeması)** ile alınacak. Serbest metin parse edilmeyecek.
- Tüm Gemini çağrıları tek bir servis dosyasında toplanacak: `interviews/services/gemini.py`.
- Her çağrı try/except ile sarılacak; hata durumunda kullanıcıya anlaşılır bir mesaj gösterilip tekrar deneme imkânı verilecek.
- SDK kullanımı (parametre adları, thinking ayarı) yazılmadan önce güncel dokümantasyondan doğrulanacak: https://ai.google.dev/gemini-api/docs

---

## 5. Mülakat Akışı

1. Kullanıcı mülakat oluşturma formunu doldurur.
2. Günlük limit kontrol edilir.
3. **Tek bir Gemini çağrısıyla** tüm sorular üretilir ve veritabanına kaydedilir.
4. Mülakat ekranında ilk soru gösterilir.
5. Kullanıcı cevap gönderir (fetch ile JSON isteği).
6. **Sadece o cevap için** bir değerlendirme çağrısı yapılır ve sonuç kaydedilir. (Tüm cevapları sonda tek seferde değerlendirmek yerine soru soru değerlendirme yapılır; bu, Vercel'deki fonksiyon süre sınırına karşı daha güvenlidir.)
7. Sıradaki soru gösterilir. Son soruya kadar 5–6 adımları tekrarlanır.
8. Son cevaptan sonra genel skor, cevap puanlarının ortalaması olarak hesaplanır ve kısa bir genel özet için son bir Gemini çağrısı yapılır.
9. Mülakat "tamamlandı" olarak işaretlenir, kullanıcı rapor sayfasına yönlendirilir.

---

## 6. AI İstemleri (Prompt) ve JSON Şemaları

**Dil kuralı:** Tüm istemlerde mülakat dili açıkça belirtilir. `language = "tr"` ise sorular, geri bildirimler ve örnek cevaplar Türkçe; `language = "en"` ise İngilizce üretilir.

### 6.1 Soru Üretme

Sistem talimatı özeti: Deneyimli bir işe alım uzmanı ve teknik mülakatçı gibi davran. Verilen pozisyon, seviye ve türe uygun, birbirini tekrar etmeyen, gerçek mülakatlarda sorulan tarzda sorular üret. Seviye stajyer/junior olduğu için sorular bu seviyeye uygun zorlukta olmalı.

Beklenen JSON:
```json
{
  "questions": [
    { "order": 1, "text": "Soru metni", "category": "teknik" }
  ]
}
```
`category` değerleri: `teknik`, `davranissal`

### 6.2 Cevap Değerlendirme

Girdi: pozisyon, seviye, dil, soru, kullanıcının cevabı.

Sistem talimatı özeti: Cevabı adil, yapıcı ve somut şekilde değerlendir. Seviyeye uygun beklentiyle puanla. Boş, alakasız veya çok kısa cevaplara düşük puan ver ve nedenini açıkla.

Beklenen JSON:
```json
{
  "score": 7,
  "strengths": "Güçlü yönler",
  "improvements": "Geliştirilecek yönler",
  "sample_answer": "Bu soruya verilebilecek örnek iyi bir cevap",
  "language_score": null,
  "language_feedback": null
}
```
- `score`: 1–10 arası tam sayı.
- `language_score` ve `language_feedback`: sadece İngilizce mülakatlarda doldurulur, Türkçe mülakatlarda `null`.

### 6.3 Genel Özet

Girdi: tüm sorular, cevaplar ve puanlar.

Beklenen JSON:
```json
{
  "summary": "Mülakatın genel değerlendirmesi (3-4 cümle)",
  "top_strength": "En belirgin güçlü yön",
  "top_improvement": "Öncelikli gelişim alanı"
}
```

---

## 7. Veri Modeli

**User:** Django'nun yerleşik User modeli (username, email, password).

**Interview**
| Alan | Tür | Açıklama |
|---|---|---|
| user | ForeignKey(User) | Mülakat sahibi |
| position | CharField (choices) | Pozisyon |
| level | CharField (choices) | `intern` / `junior` |
| interview_type | CharField (choices) | `technical` / `behavioral` / `mixed` |
| language | CharField (choices) | `tr` / `en` |
| question_count | PositiveSmallIntegerField | 5, 8 veya 10 |
| status | CharField (choices) | `in_progress` / `completed` |
| overall_score | DecimalField (null) | Genel skor |
| summary | TextField (blank) | Genel değerlendirme |
| top_strength | TextField (blank) | |
| top_improvement | TextField (blank) | |
| created_at | DateTimeField | |
| completed_at | DateTimeField (null) | |

**Question**
| Alan | Tür | Açıklama |
|---|---|---|
| interview | ForeignKey(Interview) | |
| order | PositiveSmallIntegerField | Soru sırası |
| text | TextField | Soru metni |
| category | CharField | `teknik` / `davranissal` |

**Answer**
| Alan | Tür | Açıklama |
|---|---|---|
| question | OneToOneField(Question) | |
| text | TextField | Kullanıcının cevabı |
| score | PositiveSmallIntegerField | 1–10 |
| strengths | TextField | |
| improvements | TextField | |
| sample_answer | TextField | |
| language_score | PositiveSmallIntegerField (null) | Sadece İngilizce |
| language_feedback | TextField (blank) | Sadece İngilizce |
| created_at | DateTimeField | |

---

## 8. Sayfalar ve URL'ler

| URL | Sayfa / İşlev |
|---|---|
| `/` | Tanıtım (landing) sayfası |
| `/kayit/` | Kayıt |
| `/giris/` | Giriş |
| `/cikis/` | Çıkış |
| `/panel/` | Geçmiş mülakatlar |
| `/mulakat/yeni/` | Mülakat oluşturma formu |
| `/mulakat/<id>/` | Mülakat ekranı |
| `/mulakat/<id>/cevap/` | Cevap gönderme (POST, JSON) |
| `/mulakat/<id>/rapor/` | Değerlendirme raporu |

Kullanıcı sadece kendi mülakatlarına erişebilir; başkasının mülakat id'sine erişim denemesi 404 döner.

---

## 9. Proje Yapısı (Öneri)

```
mulakat-simulatoru/
├── config/              # Django proje ayarları (settings, urls, wsgi)
├── accounts/            # Kayıt, giriş, çıkış
├── interviews/          # Mülakat modelleri, view'lar, url'ler
│   └── services/
│       └── gemini.py    # Tüm Gemini API çağrıları
├── templates/
├── static/
├── .env                 # Lokal ortam değişkenleri (git'e girmez)
├── .env.example         # Değişken isimleri, değerler boş
├── .gitignore
├── requirements.txt
├── vercel.json
└── PROJE.md             # Bu dosya
```

**Ortam değişkenleri (`.env.example`):**
```
SECRET_KEY=
DEBUG=
DATABASE_URL=
GEMINI_API_KEY=
ALLOWED_HOSTS=
```

---

## 10. Geliştirme Adımları

Her faz bitince çalıştığı test edilir, commit atılır, sonra bir sonrakine geçilir.

- [~] **Faz 1 – Kurulum:** Django projesi, ortam değişkenleri, basit bir ana sayfa hazır. Supabase bağlantısı ve Vercel'de yayına alma bilinçli olarak sona bırakıldı (şu an SQLite ile lokal çalışıyor).
- [x] **Faz 2 – Kullanıcı sistemi:** Kayıt, giriş, çıkış, giriş gerektiren sayfaların korunması.
- [x] **Faz 3 – Modeller ve form:** Interview, Question, Answer modelleri; mülakat oluşturma formu. Bu aşamada AI yok, sabit örnek sorular kullanılır.
- [x] **Faz 4 – Gemini ile soru üretme:** `gemini.py` servisi, soru üretme çağrısı, JSON şeması, hata yönetimi.
- [x] **Faz 5 – Mülakat ekranı ve değerlendirme:** Sohbet arayüzü, cevap gönderme, soru soru değerlendirme.
- [x] **Faz 6 – Rapor ve panel:** Genel skor, genel özet, rapor sayfası, geçmiş mülakatlar paneli.
- [x] **Faz 7 – Cilalama:** Günlük limit, hata mesajları, yükleniyor göstergeleri, mobil uyum, arayüz iyileştirmeleri.
- [ ] **Sonraki aşamalar:** Bölüm 2.2'deki özellikler.

---

## 11. Claude Code İçin Çalışma Kuralları

- Her seferinde tek bir faz üzerinde çalış; bir fazı bitirmeden sonrakine geçme.
- Basit tut: ayrı bir frontend framework'ü, gereksiz kütüphane veya karmaşık mimari ekleme.
- Yeni bir paket eklemeden önce nedenini açıkla.
- API anahtarlarını ve gizli bilgileri asla koda yazma.
- Gemini çağrılarında temperature / top_p / top_k kullanma; JSON şemasıyla structured output kullan.
- Arayüz metinleri Türkçe; kod, değişken ve fonksiyon isimleri İngilizce.
- Her fazın sonunda neyin yapıldığını ve nasıl test edileceğini kısaca özetle.
