"""Çeviri katalogu araçları (docs §2.2 iki dilli arayüz).

Django'nun `makemessages`/`compilemessages` komutları GNU gettext (xgettext, msgfmt) ister;
bu projede Windows'ta o araçlar yoktur, bu yüzden aynı işi yapan küçük bir betik kullanılır.
Yalnızca Python standart kütüphanesi ve Django'nun kendi `templatize` işlevi gerekir.

Kaynak metinler Türkçedir (msgid = Türkçe cümle); İngilizce çeviri
locale/en/LC_MESSAGES/django.po dosyasındadır.

Kullanım (proje kökünden, sanal ortam açıkken):

    python scripts/messages.py check      # eksik/artık/hatalı çeviri var mı? (çıkış kodu 1 = sorun)
    python scripts/messages.py update     # yeni metinleri django.po'ya boş çeviriyle ekler, artıkları siler
    python scripts/messages.py compile    # django.po -> django.mo (Django yalnızca .mo'yu okur)

Yeni bir metin eklerken: şablonda {% trans "..." %} / {% blocktrans %}, Python'da _("...") kullan,
sonra `update`, çeviriyi django.po'ya yaz, `check` ve `compile` çalıştır. .mo dosyası depoya
girer (Vercel derlemede gettext çalıştırmaz).
"""

import ast
import os
import re
import struct
import sys
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PO_PATH = ROOT / 'locale' / 'en' / 'LC_MESSAGES' / 'django.po'
MO_PATH = PO_PATH.with_suffix('.mo')

SCAN_DIRS = ['templates', 'accounts', 'interviews', 'config']
SKIP_PARTS = {'migrations', '__pycache__', 'tests.py'}
GETTEXT_NAMES = {'_', 'gettext', 'gettext_lazy', 'gettext_now', 'ngettext', 'ngettext_lazy'}
PLURAL_NAMES = {'ngettext', 'ngettext_lazy'}

HEADER = (
    'Project-Id-Version: mulakat-simulatoru\n'
    'Language: en\n'
    'MIME-Version: 1.0\n'
    'Content-Type: text/plain; charset=UTF-8\n'
    'Content-Transfer-Encoding: 8bit\n'
    'Plural-Forms: nplurals=2; plural=(n != 1);\n'
)


# ---- Çıkarma ---------------------------------------------------------------

def _django_setup():
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()


def _calls_in_python_source(source, filename):
    """(msgid, msgid_plural|None, satır) üçlüleri."""
    tree = ast.parse(source, filename=filename)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        if name not in GETTEXT_NAMES or not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        plural = None
        if name in PLURAL_NAMES and len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
            plural = node.args[1].value
        found.append((first.value, plural, node.lineno))
    return found


def _read_literal(source, position):
    """position'dan başlayan (u'...' / '...' / "...") Python dize sabitini okur → (değer, bitiş)."""
    while source[position] in ' \t\n':
        position += 1
    start = position
    if source[position] in 'uU':
        position += 1
    quote = source[position]
    assert quote in '\'"', source[start:start + 30]
    position += 1
    while source[position] != quote:
        position += 2 if source[position] == '\\' else 1
    return ast.literal_eval(source[start:position + 1]), position + 1


def _calls_in_templatized_source(source):
    """Django'nun templatize çıktısı (xgettext için maskelenmiş, geçerli Python DEĞİL) içindeki
    gettext(...)/ngettext(...) çağrıları → (msgid, msgid_plural|None, satır)."""
    found = []
    for match in re.finditer(r'\b(n?gettext)\(', source):
        line = source.count('\n', 0, match.start()) + 1
        msgid, end = _read_literal(source, match.end())
        plural = None
        if match.group(1) == 'ngettext':
            comma = source.index(',', end)
            plural, end = _read_literal(source, comma + 1)
        found.append((msgid, plural, line))
    return found


def extract():
    """{(msgid, msgid_plural): [konum, ...]} sözlüğü."""
    _django_setup()
    from django.utils.translation.template import templatize

    result = {}
    for directory in SCAN_DIRS:
        for path in sorted((ROOT / directory).rglob('*')):
            if path.suffix not in ('.py', '.html') or SKIP_PARTS & set(path.parts):
                continue
            rel = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding='utf-8')
            if path.suffix == '.py':
                calls = _calls_in_python_source(text, rel)
            else:
                if '{% trans' not in text and '{% blocktrans' not in text and '{% translate' not in text \
                        and '{% blocktranslate' not in text:
                    continue
                calls = _calls_in_templatized_source(templatize(text))
            for msgid, plural, line in calls:
                result.setdefault((msgid, plural), []).append(f'{rel}:{line}')
    return result


# ---- .po okuma / yazma -----------------------------------------------------

_ESCAPES = {'n': '\n', 't': '\t', '"': '"', '\\': '\\', 'r': '\r'}


def _unquote(fragment):
    body = fragment.strip()
    assert body.startswith('"') and body.endswith('"'), fragment
    body = body[1:-1]
    return re.sub(r'\\(.)', lambda m: _ESCAPES.get(m.group(1), m.group(1)), body)


def _quote(text):
    escaped = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')
    return f'"{escaped}"'


def read_po(path):
    """{(msgid, plural|None): [msgstr, ...]} sözlüğü ve başlık metni."""
    entries = {}
    header = ''
    for block in re.split(r'\n\s*\n', path.read_text(encoding='utf-8')):
        fields = {}
        field = None
        for raw in block.splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):  # yorumlar ve '#~' (eski) kayıtlar
                continue
            match = re.match(r'(msgid_plural|msgid|msgstr\[\d+\]|msgstr)\s*(".*")$', line)
            if match:
                field = match.group(1)
                fields[field] = _unquote(match.group(2))
            elif line.startswith('"') and field:
                fields[field] += _unquote(line)
        if 'msgid' not in fields:
            continue
        forms = [fields[key] for key in sorted(k for k in fields if k.startswith('msgstr'))]
        if fields['msgid'] == '' and 'msgid_plural' not in fields:
            header = forms[0] if forms else ''
        else:
            entries[(fields['msgid'], fields.get('msgid_plural'))] = forms
    return entries, header


def write_po(path, extracted, translations):
    lines = ['# Çeviri kataloğu (İngilizce). Kaynak metinler Türkçedir.',
             '# Bakım: python scripts/messages.py update | check | compile', '#',
             'msgid ""', 'msgstr ""']
    for header_line in HEADER.splitlines():
        lines.append(_quote(header_line + '\n'))
    for (msgid, plural), locations in sorted(extracted.items(), key=lambda kv: (kv[1][0], kv[0][0])):
        lines.append('')
        lines.append('#: ' + ' '.join(sorted(set(locations))[:3]))
        forms = translations.get((msgid, plural), [])
        lines.append(f'msgid {_quote(msgid)}')
        if plural is not None:
            lines.append(f'msgid_plural {_quote(plural)}')
            forms = (forms + ['', ''])[:2]
            lines.append(f'msgstr[0] {_quote(forms[0])}')
            lines.append(f'msgstr[1] {_quote(forms[1])}')
        else:
            lines.append(f'msgstr {_quote(forms[0] if forms else "")}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')


# ---- Doğrulama -------------------------------------------------------------

_PLACEHOLDER = re.compile(r'%\(\w+\)[sd]|%[sd]')
_TAG = re.compile(r'</?\w+[^>]*>')


def check():
    extracted = extract()
    entries, _header = read_po(PO_PATH)
    problems = []
    for key in extracted:
        if key not in entries:
            problems.append(f'EKSİK   {key[0][:80]!r}  ({extracted[key][0]})')
    for key in entries:
        if key not in extracted:
            problems.append(f'ARTIK   {key[0][:80]!r} (kodda yok)')
    for (msgid, plural), forms in entries.items():
        if (msgid, plural) not in extracted:
            continue
        if not forms or any(not form for form in forms):
            problems.append(f'BOŞ     {msgid[:80]!r}')
            continue
        source_forms = [msgid] + ([plural] if plural is not None else [])
        for index, form in enumerate(forms):
            source = source_forms[min(index, len(source_forms) - 1)]
            # Çeviri, kaynaktaki bir yer tutucuyu atlayabilir ya da tekrar kullanabilir (ör. cümle yapısı
            # farklıysa), ama kaynakta olmayan bir yer tutucu ekleyemez.
            if not set(_PLACEHOLDER.findall(form)) <= set(_PLACEHOLDER.findall(source)):
                problems.append(f'YER TUTUCU {msgid[:70]!r} -> {form[:70]!r}')
            if sorted(_TAG.findall(source)) != sorted(_TAG.findall(form)):
                problems.append(f'ETİKET  {msgid[:70]!r} -> {form[:70]!r}')
            if source != source.strip() and form != form.strip() and (source[:1].isspace() != form[:1].isspace()):
                problems.append(f'BOŞLUK  {msgid[:70]!r}')
    print(f'{len(extracted)} metin kodda, {len(entries)} kayıt django.po\'da.')
    for problem in problems:
        print(problem)
    print('SONUC', 'temiz' if not problems else f'{len(problems)} sorun')
    return not problems


def update():
    extracted = extract()
    entries, _header = read_po(PO_PATH) if PO_PATH.exists() else ({}, '')
    write_po(PO_PATH, extracted, entries)
    new = sum(1 for key in extracted if key not in entries)
    gone = sum(1 for key in entries if key not in extracted)
    print(f'django.po güncellendi: {len(extracted)} metin, {new} yeni (boş çeviri), {gone} artık silindi.')


# ---- .mo yazma -------------------------------------------------------------

def compile_mo():
    entries, header = read_po(PO_PATH)
    messages = {b'': (header or HEADER).encode('utf-8')}
    for (msgid, plural), forms in entries.items():
        if not forms or any(not form for form in forms):
            continue  # çevrilmemiş kayıt .mo'ya girmez; Django kaynak metni gösterir
        key = msgid if plural is None else msgid + '\0' + plural
        messages[key.encode('utf-8')] = '\0'.join(forms).encode('utf-8')
    keys = sorted(messages)
    ids = strs = b''
    offsets = []
    for key in keys:
        offsets.append((len(ids), len(key), len(strs), len(messages[key])))
        ids += key + b'\0'
        strs += messages[key] + b'\0'
    key_start = 7 * 4 + 16 * len(keys)
    value_start = key_start + len(ids)
    key_offsets, value_offsets = [], []
    for id_offset, id_length, str_offset, str_length in offsets:
        key_offsets += [id_length, id_offset + key_start]
        value_offsets += [str_length, str_offset + value_start]
    output = struct.pack('Iiiiiii', 0x950412DE, 0, len(keys), 7 * 4, 7 * 4 + len(keys) * 8, 0, 0)
    output += array('i', key_offsets + value_offsets).tobytes()
    output += ids + strs
    MO_PATH.write_bytes(output)
    print(f'{MO_PATH.relative_to(ROOT)} yazıldı ({len(keys) - 1} çeviri).')


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else ''
    if command == 'check':
        sys.exit(0 if check() else 1)
    elif command == 'update':
        update()
    elif command == 'compile':
        compile_mo()
    else:
        print(__doc__)
        sys.exit(2)
