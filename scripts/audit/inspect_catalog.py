"""Inspect the gettext catalogues to see whether English strings are recoverable."""

import os

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for locale in ('en', 'ar'):
    path = os.path.join(root, 'translations', locale, 'LC_MESSAGES', 'messages.po')
    with open(path, 'rb') as fh:
        raw = fh.read()
    print(locale, 'bytes', len(raw))
    for enc in ('utf-8', 'cp1256', 'cp1252', 'latin-1'):
        try:
            text = raw.decode(enc)
            sample = text[text.find('msgid "_') :][:300]
            print(f'  {enc}: ok | {sample[:180]!r}')
        except Exception as exc:
            print(f'  {enc}: FAIL {exc}')
