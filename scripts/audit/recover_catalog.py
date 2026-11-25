"""Recover a usable Arabic→English dictionary from the mangled gettext PO.

The catalog was extracted from `_(_('...'))` template calls, so each msgid is a
Python expression wrapping the real Arabic string. This unwraps it and keeps
only entries whose msgstr is a genuine English translation.
"""

import os
import re

import polib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PO = os.path.join(ROOT, 'translations', 'en', 'LC_MESSAGES', 'messages.po')

WRAPPER = re.compile(r'^_\("(?:_\("\s*)*(.+?)(?:"\)\)*)?$')


def unwrap(value):
    # repeated removal of _( "..." ) wrappers
    current = value
    for _ in range(8):
        m = re.fullmatch(r'_\("(.*)"\)', current, re.DOTALL)
        if not m:
            break
        current = m.group(1).strip()
    # remove trailing quote-escapes artifacts
    return current.replace('\\"', '"').strip()


po = polib.pofile(PO)
recovered = {}
for entry in po:
    arabic = unwrap(entry.msgid)
    english = unwrap(entry.msgstr)
    if not arabic or not english:
        continue
    if arabic == english:
        continue
    if not re.search(r'[\u0600-\u06ff]', arabic):
        continue
    recovered[arabic] = english

print(f'entries={len(po)} recovered={len(recovered)}')
for ar, en in list(recovered.items())[:25]:
    print(f'  {ar[:45]!r} -> {en[:55]!r}')

out = os.path.join(ROOT, 'app', 'shared', 'i18n_catalog.json')
import json

with open(out, 'w', encoding='utf-8') as fh:
    json.dump(recovered, fh, ensure_ascii=False, indent=2)
    fh.write('\n')
print('wrote', out)
