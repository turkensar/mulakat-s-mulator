"""Supabase public şemasında RLS'i açar ve API rollerinin erişimini kapatır (scripts/supabase_rls.sql).

Kullanım (proje kökünden, DATABASE_URL Supabase'i göstermeli):

    .venv/Scripts/python scripts/apply_supabase_rls.py          # uygula + doğrula
    .venv/Scripts/python scripts/apply_supabase_rls.py --check  # yalnızca durumu göster (değiştirmez)
    .venv/Scripts/python scripts/apply_supabase_rls.py --undo   # eski duruma dön (RLS kapalı, yetkiler açık)

Yeni bir tablo ekleyen her migration'dan sonra (python manage.py migrate) bir kez çalıştırın:
yeni tablolar varsayılan olarak RLS'siz doğar ve Supabase yeniden uyarı gönderir.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('SENTRY_DSN', '')

import django  # noqa: E402

django.setup()

from django.db import connection, transaction  # noqa: E402

UNDO_SQL = """
DO $$
DECLARE t record;
BEGIN
    FOR t IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS deny_api_access ON public.%I', t.relname);
        EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', t.relname);
        EXECUTE format('GRANT ALL ON TABLE public.%I TO anon, authenticated', t.relname);
    END LOOP;
END $$;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;
"""


def report():
    """Her public tablo için RLS durumu, policy sayısı ve API rollerinin yetkisi. Sorun varsa False döner."""
    ok = True
    with connection.cursor() as c:
        c.execute("select current_user, (select rolbypassrls from pg_roles where rolname = current_user)")
        user, bypass = c.fetchone()
        print(f'Bağlantı rolü: {user} (BYPASSRLS={bypass})')
        c.execute("""
            select c.relname, c.relrowsecurity,
                   (select count(*) from pg_policies p where p.schemaname = 'public' and p.tablename = c.relname),
                   (select count(*) from information_schema.role_table_grants g
                     where g.table_schema = 'public' and g.table_name = c.relname
                       and g.grantee in ('anon', 'authenticated'))
            from pg_class c join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'public' and c.relkind in ('r', 'p') order by 1
        """)
        for name, rls, policies, grants in c.fetchall():
            good = rls and grants == 0
            ok = ok and good
            print(f'  {"OK " if good else "!! "}{name:34s} RLS={"açık" if rls else "KAPALI"} '
                  f'policy={policies} API-yetkisi={grants}')
    return ok


def main():
    if 'postgresql' not in connection.settings_dict['ENGINE']:
        sys.exit('DATABASE_URL Postgres (Supabase) değil; yapılacak bir şey yok.')
    arg = sys.argv[1] if len(sys.argv) > 1 else ''
    if arg == '--check':
        sys.exit(0 if report() else 1)
    if arg == '--undo':
        with transaction.atomic():
            connection.cursor().execute(UNDO_SQL)
        print('Eski duruma dönüldü.')
        report()
        return
    sql = (ROOT / 'scripts' / 'supabase_rls.sql').read_text(encoding='utf-8')
    with transaction.atomic():
        connection.cursor().execute(sql)
    print('RLS uygulandı.')
    sys.exit(0 if report() else 1)


if __name__ == '__main__':
    main()
