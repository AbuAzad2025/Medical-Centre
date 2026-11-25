import os

import polib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
po = polib.pofile(os.path.join(ROOT, 'translations', 'en', 'LC_MESSAGES', 'messages.po'))
for entry in po:
    if 'المريض:' in entry.msgid and len(entry.msgid) < 300:
        print('MSGID', repr(entry.msgid))
        print('MSGSTR', repr(entry.msgstr))
        print('OCC', entry.occurrences[:4])
        break
for entry in po:
    if 'الطريقة:' in entry.msgid and len(entry.msgid) < 300:
        print('---')
        print('MSGID', repr(entry.msgid))
        print('MSGSTR', repr(entry.msgstr))
        print('OCC', entry.occurrences[:4])
        break
