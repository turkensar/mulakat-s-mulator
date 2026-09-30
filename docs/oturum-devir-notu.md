# Oturum Devir Notu — Mülakat Simülatörü

Son güncelleme: 2026-09-30. Yeni oturumda **önce bu dosyayı**, sonra `docs/mulakat2.md`'yi oku.

## 1. Yeni oturuma başlarken ilk iş

Yerel depo `main` dalında ve güncel. Başka bir oturum (ör. bulut) yeni commit atmış olabilir,
o yüzden önce güncelle:

```bash
git pull origin main
```

Sonra yerel sunucuyu başlat (proje `.venv`'i ile):

```bash
.venv/Scripts/python manage.py runserver 8000
```

`--noreload` kullanırsan şablon değişiklikleri görünmez (Django 6 şablonları DEBUG'da da
önbelleğe alıyor, önbelleği yalnızca autoreloader temizliyor). Görünmüyorsa sunucuyu yeniden başlat.

## 2. Canlı ortam

- **Adres:** https://mulakat-simulatoru.vercel.app. Eski adres `mulakat-s-mulator.vercel.app`, 308 ile yeniye yönleniyor.
- **Deploy:** `main`'e her push otomatik production deploy'u tetikler (~30 sn).
- **Veritabanı:** Supabase Postgres, yerel ve canlı **aynı veritabanını** kullanır. Yerelde çalıştırılan `migrate` canlıyı anında etkiler.
- **Vercel ortam değişkenleri (production):** `SECRET_KEY`, `DEBUG`, `DATABASE_URL`, `ALLOWED_HOSTS`,
  `GEMINI_API_KEY`, `GEMINI_MODEL`, `RECAPTCHA_PUBLIC_KEY`, `RECAPTCHA_PRIVATE_KEY`, `GMAIL_ADDRESS`,
  `GMAIL_APP_PASSWORD`, `GOOGLE_CLIENT_ID`.
  - **`SENTRY_DSN` henüz eklenmedi**, bu yüzden hata takibi kapalı.
- **İletişim adresi:** `mulakatsimulatoru@gmail.com` (`config/settings.py` → `CONTACT_EMAIL`).

## 3. Bu oturumda yapılanlar (hepsi canlıda)

Sırasıyla:

1. **Hız sınırı düzeltmesi.** Vercel proxy'si yüzünden bütün ziyaretçiler tek bir sayacı paylaşıyordu.
   Gerçek IP artık `X-Forwarded-For`'dan okunuyor (`config/ratelimit.py`).
2. **Vercel süre sınırı** 120 saniyeden 300 saniyeye çıkarıldı (`vercel.json`).
3. **Footer'daki İletişim linki** Gmail'i tarayıcıda açıyor. Adres uygulamanın hesabı, kişisel e-posta sitede hiçbir yerde geçmiyor.
4. **E-posta gönderimi Resend'den Gmail SMTP'ye taşındı** (Django 6.1 `MAILERS`). Ortam değişkenleri: `GMAIL_ADDRESS` ve `GMAIL_APP_PASSWORD` (uygulama şifresi).
5. **Şifremi unuttum** akışı eklendi (`/sifremi-unuttum/`, `/sifre-sifirla/...`).
6. **Kayıttaki e-posta doğrulaması kaldırıldı.** Hesap anında aktif olur, kullanıcı panele düşer. reCAPTCHA ve KVKK onayı yerinde.
7. **Hesabımı sil** (`/hesabim/sil/`). Parolalı hesapta parola, Google hesabında e-posta ile onaylanır.
   Mülakatlar, sorular ve cevaplar da silinir (CASCADE).
8. **Rapordan "Aynı ayarlarla tekrar dene"** (`/mulakat/yeni/?tekrar=<id>`).
9. **Yapay zekayı bekleyen formlar sayfa yenilenmeden gönderiliyor** (`static/js/async_form.js`, `config/async_forms.py`, `templates/_async_progress.html`).
   - Beklerken adım adım ilerleyen bir durum ve geçen süre görünür.
   - Hata olursa form ve yapıştırılan metinler olduğu gibi kalır.
   - Misafir hata mesajlarının hep Türkçe çıkması da bu sırada düzeltildi.
10. **Sentry hata takibi** (`sentry-sdk`). `SENTRY_DSN` boşsa kapalı. Form içerikleri, çerezler ve IP gönderilmez; bu, sahte bir alıcıyla test edildi.
11. **Gizlilik/KVKK metinleri güncellendi:** hesap silme, Gmail ve Sentry eklendi, Resend çıkarıldı.
12. **Logo paketi** hazırlanıp kullanıcıya gönderildi (SVG ve 1024 px PNG).
    - Yeniden üretmek için: `static/img/logo-mark.svg` (şeffaf) ve `static/img/icon.svg` (uygulama simgesi) kaynak dosyalar.

**Başka bir Claude oturumunda (bulutta) yapılan ve `main`'e birleşen iş:** Android uygulaması için JSON API.
- Konum: `api/` uygulaması, adres `/api/v1/`. DRF ve token kimlik doğrulaması kullanıyor.
- Yeni bağımlılık: `djangorestframework`.
- `authtoken` migration'ı paylaşımlı veritabanına uygulanmış durumda.
- Canlıda doğru yanıt veriyor: giriş yapılmadan 401, eksik alanla 400.
- Mobil kayıtta reCAPTCHA bilerek yok, hız sınırı var.

Testler: `manage.py test accounts interviews --keepdb` (API dalıyla birlikte toplam 54 test).

## 4. Kullanıcının yapması gerekenler (bekleyenler)

- [ ] **Sentry:** sentry.io'da hesap aç (veri konumu olarak EU seç), bir Django projesi oluştur, DSN'i Vercel'e `SENTRY_DSN` olarak ekle, sonra yeniden deploy et.
- [ ] **Google ile girişi canlıda dene.** Buton zaten görünüyor. `origin_mismatch` hatası çıkarsa Google Cloud'da origin olarak `https://mulakat-simulatoru.vercel.app` ekli mi kontrol et.
  Google OAuth consent screen "In production" olmalı, yoksa yalnızca test kullanıcıları girebilir.
- [ ] **Şifremi unuttum'u canlıda dene.** Mail `mulakatsimulatoru@gmail.com` adresinden gelmeli.
  - Gmail değişkenleri yeni hesaba geçirildi mi, bu doğrulanmadı.
  - Yeni hesapta uygulama şifresi alınırken "ayar kullanılamıyor" hatası çıkmıştı. Sebep: o hesapta iki adımlı doğrulama kapalıydı.

## 5. Açık kalanlar / fikirler

- **AI takip soruları:** ertelendi, her cevaba ek bir Gemini çağrısı demek (kota).
- **Resend'de domain doğrulaması:** artık gerek yok, Gmail kullanılıyor.
- **Yatay logo** (işaret ve "Mülakat Simülatörü" yazısı): teklif edildi, kullanıcı henüz istemedi.
- **Bilinen risk:** Vercel bir soru üretimini yarıda keserse sorusuz bir mülakat kalabilir. Böyle bir mülakat açılınca `_complete_interview` sıfıra bölme hatası verir. 300 sn sınırıyla olasılığı çok düşük ama kodda koruma yok.
- **HSTS:** `max-age=3600`. İleride artırılabilir, `check --deploy` uyarıları W005/W021 bilinçli.

## 6. Çalışma kuralları (kullanıcı tercihleri)

- Türkçe, kısa ve samimi ("sen" dili) iletişim. Arayüzdeki her yeni metin TR ve EN olmalı:
  `python scripts/messages.py update | check | compile`. `.txt` e-posta şablonları da taranıyor.
- **Commit ve push yalnızca kullanıcı söyleyince.** "commitle" ve "push et" genelde ayrı ayrı gelir. Kullanıcı birden fazla işi "parça parça" commit'lemeyi tercih ediyor.
  Commit mesajları ASCII Türkçe ve önekli (`ozellik:`, `duzeltme:`, `docs:`, `yapilandirma:`, `bagimlilik:`, ...).
- **Sırlar:** Sırları kullanıcı kendisi Vercel'e girer. Sohbette, commit'te ya da hafızada asla değer yazılmaz. `.env` sır içerir, içeriği ekrana basılmaz.
- **Ücretsiz katman:** Her şey ücretsiz katmanda kalmalı. Yeni paket eklemeden önce gerekçesi açıklanır.
- **Kotasız test:** Gemini çağrıları sahtelenir (testlerde `patch`; arayüz için sahte Gemini'li `runserver` betiği).
  Canlı veritabanında test kullanıcısı `probe_*` adıyla açılır ve hemen silinir. Kullanıcının gerçek hesabı `turkensar` asla silinmez.
- **Windows notları:**
  - Genel `python`'da Django yok, `.venv/Scripts/python` kullanılır.
  - Türkçe karakterli betikler heredoc ile değil, dosyaya yazılıp çalıştırılır.
  - Arka plandaki `runserver` görevleri sık sık "exit code 4/127" ile düşer; bu normal, yeniden başlatılır.
  - Git "LF → CRLF" uyarıları zararsız.
- **Vercel:** Runtime loglarına MCP ile erişilemiyor (403). Ortam değişkenlerinin adları `filter_project_envs` ile (değerleri çözmeden) görülebiliyor.
