# Oturum Devir Notu — Mülakat Simülatörü

Son güncelleme: 2026-10-01. Yeni oturumda **önce bu dosyayı**, sonra `docs/mulakat2.md`'yi oku.

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
  - Yerel `.env`'de `DATABASE_URL` açıksa (satır başında `#` yok) Supabase, yorumdaysa yerel SQLite kullanılır. Android oturumu SQLite'a geçmişti; 2026-09-30'da web için Supabase'e döndürüldü.
  - Canlı veriye dokunmadan denemek için ayrı SQLite sunucusu: PowerShell'de `$env:DATABASE_URL='sqlite:///C:/Users/turke/PycharmProjects/MulakatSımulatoru/db.sqlite3'; .venv/Scripts/python manage.py runserver 8001` (kabuk değişkeni `.env`'yi geçersiz kılar).
- **Vercel ortam değişkenleri (production):** `SECRET_KEY`, `DEBUG`, `DATABASE_URL`, `ALLOWED_HOSTS`,
  `GEMINI_API_KEY`, `GEMINI_MODEL`, `RECAPTCHA_PUBLIC_KEY`, `RECAPTCHA_PRIVATE_KEY`, `GMAIL_ADDRESS`,
  `GMAIL_APP_PASSWORD`, `GOOGLE_CLIENT_ID`.
  - `SENTRY_DSN` (2026-10-01'de eklendi ve canlıda doğrulandı, bkz. §3 madde 13).
  - `GEMINI_MODEL` Vercel'de tanımlıysa kodun varsayılanını (`gemini-3.6-flash`) ezer; model değiştirirken orayı da kontrol et.
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
    - 2026-10-01'de canlıda gerçek bir hatayla doğrulandı: olay Sentry'ye ulaştı, yerel değişkenler, istek içeriği, çerez ve IP kaydında yok. (DSN ilk girişte eski/başka bir projeye aitti, `ProjectId` reddi aldı; doğru projenin DSN'iyle düzeldi. Bozuk biçimli, ör. tırnaklı bir DSN `sentry_sdk.init` sırasında `BadDsn` ile tüm siteyi çökertir.)
11. **Gizlilik/KVKK metinleri güncellendi:** hesap silme, Gmail ve Sentry eklendi, Resend çıkarıldı.
12. **Logo paketi** hazırlanıp kullanıcıya gönderildi (SVG ve 1024 px PNG).
    - Yeniden üretmek için: `static/img/logo-mark.svg` (şeffaf) ve `static/img/icon.svg` (uygulama simgesi) kaynak dosyalar.
13. **Sentry doğrulaması** (2026-10-01): geçici bir hata adresiyle yapıldı ve sonra silindi (`5a40deb`'e kadar olan commit'ler). Olaylar `flush` beklemeden de ulaşıyor, Vercel'de ek düzeltme gerekmedi. Sentry panelinde proje `python-django`, veri konumu EU.
14. **Gemini modeli ve istemi** (2026-09-30): varsayılan model `gemini-3.6-flash`, yedekler `3.5 → 3.7 → 3.8 → 3.1-flash-lite`. `3.8` ve `3.7` o gün 30+ sn'de zaman aşımına düşüyordu; `3.1-flash-lite` yavaş ve sorular daha genel. Soru üretme istemi güçlendirildi (senaryo, çeşitlilik, somut deneyim). Takılan denemeler için deneme süresi 25 sn, bütçeler 120/100/80 sn (Vercel `maxDuration` 300).
15. **Google girişi düzeltildi:** `SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'`. Django'nun varsayılanı (`same-origin`) Google popup'ını boş bırakıyordu.
16. **Profil menüsü** (navbar, §12.8): ad, e-posta, hesap türü, üyelik tarihi, Çıkış ve "Hesabımı sil" burada. Panelin altındaki eski bağlantı kaldırıldı.

**Başka bir Claude oturumunda (bulutta) yapılan ve `main`'e birleşen iş:** Android uygulaması için JSON API.
- Konum: `api/` uygulaması, adres `/api/v1/`. DRF ve token kimlik doğrulaması kullanıyor.
- Yeni bağımlılık: `djangorestframework`.
- `authtoken` migration'ı paylaşımlı veritabanına uygulanmış durumda.
- Canlıda doğru yanıt veriyor: giriş yapılmadan 401, eksik alanla 400.
- Mobil kayıtta reCAPTCHA bilerek yok, hız sınırı var.

Testler: `manage.py test accounts interviews --keepdb` (API dalıyla birlikte toplam 54 test).

## 4. Kullanıcının yapması gerekenler (bekleyenler)

Bekleyen iş yok. "Şifremi unuttum" mailinin canlıda çalıştığı 2026-10-01'de kullanıcı tarafından doğrulandı (mail `mulakatsimulatoru@gmail.com` hesabı üzerinden gidiyor, Gmail değişkenleri doğru).

## 5. Açık kalanlar / fikirler

- **AI takip soruları:** ertelendi, her cevaba ek bir Gemini çağrısı demek (kota).
- **Resend'de domain doğrulaması:** artık gerek yok, Gmail kullanılıyor.
- ~~Yatay logo~~ **Yapıldı (2026-10-01):** `static/img/logo-horizontal.svg` (yazı çizgiye çevrilmiş) ve `.png`; ayrıntı docs §12.6. İngilizce sürümü ve koyu zemin sürümü yok.
- ~~Sorusuz mülakat riski~~ **Çözüldü (2026-10-01):** 10 dakikadan eski sorusuz mülakat açılınca/panel ve mülakat oluşturma sayfası yüklenince silinir (günlük hak geri gelir), daha yeni olana dokunulmaz (üretim sürüyor olabilir); `_complete_interview` cevapsız mülakatta çökmez. Web ve API'de aynı (`interviews/views.py::_purge_abandoned`, `ABANDONED_AFTER`).
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
