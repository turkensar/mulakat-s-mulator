-- Supabase "public" şeması için RLS ve API rolü kısıtı (idempotent: her migrate'ten sonra tekrar çalıştırılabilir).
--
-- Neden: Uygulama veritabanına Django ile doğrudan Postgres bağlantısıyla (postgres rolü) erişir; Supabase'in
-- Data API'sini (PostgREST, anon/authenticated rolleri) HİÇ kullanmaz. Supabase public şemasındaki her tabloyu
-- varsayılan olarak bu API'ye açar ve anon/authenticated rollerine tam yetki verir. RLS kapalıyken proje URL'si
-- ve anon anahtarını bilen herkes auth_user (parola özetleri), authtoken_token, django_session (oturumlar)
-- ve tüm mülakat verisini okuyabilir/değiştirebilir/silebilir.
--
-- Çözüm: her tabloda RLS açık + anon/authenticated için "hiçbir satıra erişim yok" policy'si + bu rollerden
-- tüm tablo/sekans yetkilerinin geri alınması (TRUNCATE/REFERENCES/TRIGGER RLS'ten bağımsızdır, yetkiyle kapatılır).
-- Django'nun kullandığı postgres rolü tabloların sahibidir ve BYPASSRLS özelliği vardır, bu yüzden etkilenmez.
-- service_role (Supabase'in yönetim anahtarı) RLS'i zaten atlar.
--
-- Not: FORCE ROW LEVEL SECURITY KULLANILMAZ (sahibe de uygulanır; uygulamayı gereksiz riske sokar).
-- Çalıştırma: python scripts/apply_supabase_rls.py   (Django bağlantısını kullanır, sonucu doğrular)

SET LOCAL lock_timeout = '5s';

DO $$
DECLARE
    t record;
BEGIN
    FOR t IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.relname);
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon, authenticated', t.relname);
        EXECUTE format('DROP POLICY IF EXISTS deny_api_access ON public.%I', t.relname);
        EXECUTE format(
            'CREATE POLICY deny_api_access ON public.%I FOR ALL TO anon, authenticated USING (false) WITH CHECK (false)',
            t.relname
        );
    END LOOP;
END
$$;

REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;

-- Bundan sonra Django migration'larının oluşturacağı tablo/sekans/fonksiyonlar bu rollere yetki ile doğmasın.
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon, authenticated;
