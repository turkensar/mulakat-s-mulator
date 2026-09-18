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

**Tasarım yönü:** Gençlere hitap eden, canlı renkli, enerjik ve modern bir arayüz. Ayrıntılar Bölüm 12'de; arayüzle ilgili her işte önce o bölüm okunmalı.

---

## 4. Gemini API Kuralları

- Model adı: `gemini-3.8-flash` (settings içinde tek bir sabitte tutulacak, ör. `GEMINI_MODEL`, böylece ileride kolayca değiştirilebilir).
- API anahtarı: `GEMINI_API_KEY` ortam değişkeninden okunur. **Asla** frontend koduna, template'e ya da GitHub'a girmez. `.env` dosyası `.gitignore` içinde olmalı.
- **Düşünme seviyesi (thinking level):**
  - Soru üretme: `low` (hızlı cevap, Vercel süre sınırına takılmamak için)
  - Cevap değerlendirme ve genel özet: `medium`
- **Süreler:** Her çağrının yanıt bekleme zaman aşımı 45 sn'dir (`_CALL_TIMEOUT_SECONDS`); bu toplam süre sınırı değil, "hiç veri gelmeden bekleme" sınırıdır. SDK yalnızca hızlı dönen 5xx hatalarını yeniden dener (`attempts=2` = 1 ilk istek + 2 tekrar), zaman aşımını ve 429'u denemez. Son cevapta iki çağrı (değerlendirme + özet) arka arkaya çalıştığı için `vercel.json`'da `maxDuration` 120 sn'dir (Fluid compute açıkken Hobby planında varsayılan ve en fazla 300 sn). Her çağrının süresi `logger.info` ile kaydedilir; canlıda gerçek gecikmelere göre ayar yapılır.
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

- [x] **Faz 1 – Kurulum:** Django projesi, ortam değişkenleri, ana sayfa, Supabase bağlantısı (PostgreSQL) hazır ve test edildi; Vercel'de yayında (https://mulakat-s-mulator.vercel.app, bölge fra1). Canlıda doğrulananlar: sayfalar ve statik dosyalar, HTTPS yönlendirmesi, güvenli çerez, CSRF, canlı veritabanı sorgusu. Canlıda henüz gerçek Gemini ile uçtan uca mülakat denenmedi.
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

---

## 12. Arayüz ve Tasarım Sistemi

**Konsept:** "Mülakattan önce prova." Site gergin bir sınav ortamı gibi değil, enerjik ve cesaret veren bir antrenman alanı gibi hissettirmeli. Açık zemin üzerinde canlı, doygun renkler; büyük ve karakterli başlıklar; dokunması keyifli, iri seçim butonları.

**Yapılmayacaklar:** Koyu lacivert/siyah zemin üzerine tek bir mor vurgu, standart `<select>` açılır menüler, her şeyin aynı gri gölgeli kartlarla doldurulması, BÜYÜK HARFLİ küçük etiketler, her bölümde tekrarlanan giriş animasyonları.

### 12.1 Renk Paleti

Tüm renkler `static/css/tokens.css` içinde CSS değişkeni olarak tanımlanır; kodda renk kodu doğrudan yazılmaz.

| Değişken | Hex | Kullanım |
|---|---|---|
| `--bg` | `#F7F5FF` | Sayfa zemini (hafif lila beyaz) |
| `--surface` | `#FFFFFF` | Form alanları, rapor blokları |
| `--ink` | `#1C1240` | Ana metin ve başlıklar (koyu mürdüm) |
| `--ink-soft` | `#5B5378` | İkincil metin |
| `--violet` | `#6B3BFF` | Ana marka rengi, birincil butonlar, **Teknik** mülakat |
| `--coral` | `#FF5A7A` | **İK** mülakat, düşük puan (1–4) |
| `--sun` | `#FFC93C` | **Karışık** mülakat, orta puan (5–7), vurgu |
| `--mint` | `#1FCB94` | Yüksek puan (8–10), başarı mesajları |
| `--line` | `#E4DEF7` | İnce kenarlıklar |

Renkler anlam taşır: mülakat türü ve puan aralığı her ekranda aynı renkle gösterilir (panelde, raporda, mülakat ekranında). Böylece kullanıcı renge bakarak neyle karşı karşıya olduğunu anlar.

### 12.2 Tipografi

Google Fonts üzerinden (Türkçe karakter desteği var):
- **Başlıklar:** Bricolage Grotesque (700–800), büyük ve sıkı satır aralığıyla. Ana sayfa başlığı masaüstünde 64–72px, mobilde 40px civarı.
- **Metin ve arayüz:** DM Sans (400, 500, 700), gövde metni 17px, satır aralığı 1.6.
- Metin satırları 70 karakteri geçmez.

### 12.3 Temel Bileşenler

- **Seçim çipleri (en önemli bileşen):** Mülakat oluşturma formundaki tüm açılır menüler kaldırılır. Her seçenek, tıklanabilir iri bir çip/kart olur. Seçilince ilgili renkle dolar, hafifçe büyür. Arka planda gerçek radio input'lar durur (erişilebilirlik ve form gönderimi için), görünüm CSS ile verilir.
  - Pozisyon: ikonlu kartlar (her pozisyona bir emoji veya basit ikon).
  - Tür: Teknik (violet), İK (coral), Karışık (sun).
  - Dil: bayraklı iki büyük buton (🇹🇷 Türkçe / 🇬🇧 English).
  - Soru sayısı: 5 / 8 / 10 yazan yuvarlak rozetler, yanında tahmini süre ("~10 dk").
- **Butonlar:** Birincil buton violet zemin, beyaz yazı, tam yuvarlak kenar (pill), 52px yükseklik. Üzerine gelince hafif yukarı kalkar ve altında aynı renkte, kaydırılmış düz bir gölge belirir (bulanık gri gölge değil).
- **Köşe yuvarlaklığı:** Hiyerarşiye göre değişir: çipler ve butonlar tam yuvarlak, form blokları 20px, küçük rozetler 8px.
- **Puan halkası:** Raporda genel skor büyük, renkli bir dairesel halka içinde gösterilir; halkanın rengi puan aralığına göre değişir.

### 12.4 Sayfa Bazında Yönlendirme

- **Ana sayfa:** Solda büyük başlık ("Mülakattan önce provanı yap" gibi) ve tek bir birincil buton, sağda örnek bir mülakat sohbetinden canlandırılmış bir kesit (AI sorusu + kullanıcı cevabı + küçük puan rozeti). Sayfadaki tek animasyon bu kesitte: mesajların sırayla belirmesi.
- **Mülakat oluşturma:** Seçimler adım adım gruplanır (Pozisyon → Seviye → Tür → Dil → Soru sayısı). Her grup başlığı sade ve cümle düzeninde. Sayfanın altında sabit bir özet çubuğu seçimleri gösterir ve "Mülakatı başlat" butonunu barındırır.
- **Mülakat ekranı:** Sohbet düzeni. AI soruları solda violet tonlu balonlarda, kullanıcı cevapları sağda beyaz balonlarda. Üstte renkli ilerleme çubuğu. Değerlendirme beklenirken "Cevabın değerlendiriliyor" yazan, üç noktası nabız gibi atan bir gösterge.
- **Rapor:** En üstte puan halkası ve genel özet. Altında her soru için açılır bölüm; puan rozeti rengi puan aralığını gösterir. Güçlü yönler mint, gelişim alanları coral kenar çizgisiyle ayrılır.
- **Panel:** Mülakatlar liste halinde; her satırda tür rengi, pozisyon, dil bayrağı, tarih ve puan rozeti. Hiç mülakat yoksa boş durum ekranı ve "İlk mülakatını başlat" butonu.

### 12.5 Kalite Kuralları

- Mobil öncelikli: 375px genişlikte her ekran rahat kullanılmalı, çipler alt alta sarılmalı.
- Klavye ile gezinmede görünür odak halkası (violet).
- `prefers-reduced-motion` açıksa animasyonlar kapatılır.
- Metin ve zemin arasında yeterli kontrast (özellikle sun sarısı üzerinde koyu metin kullanılır, beyaz değil).
- Koyu tema şimdilik yok; ileride aynı değişkenlerin koyu versiyonlarıyla eklenebilir.
