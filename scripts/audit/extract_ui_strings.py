"""Extract Arabic UI strings from templates for translation coverage.

Collects (a) literals passed to _() and (b) hardcoded Arabic text nodes and
common UI attributes. Outputs a JSON list used by the translation generator.
"""

import glob
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
AR = re.compile(r'[\u0600-\u06ff]')

gettext_call = re.compile(r"_\(\s*(['\"])((?:\\.|(?!\1).)+)\1\s*\)")
text_node = re.compile(r'>\s*([^<>]*[\u0600-\u06ff][^<>]*)\s*<')
attr = re.compile(r'(title|placeholder|aria-label|alt)\s*=\s*"([^"]*[\u0600-\u06ff][^"]*)"')

strings = set()
per_file = {}
for path in glob.glob(os.path.join(ROOT, 'templates', '**', '*.html'), recursive=True):
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    found = set()
    for m in gettext_call.finditer(text):
        value = m.group(2)
        if AR.search(value):
            found.add(value)
    # skip script/style bodies for text nodes
    cleaned = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.I)
    for m in text_node.finditer(cleaned):
        value = m.group(1).strip()
        if value and AR.search(value) and len(value) < 300:
            found.add(value)
    for m in attr.finditer(cleaned):
        found.add(m.group(2).strip())
    if found:
        per_file[os.path.relpath(path, ROOT).replace('\\', '/')] = sorted(found)
        strings.update(found)

out = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'ui_strings.json')
with open(out, 'w', encoding='utf-8') as fh:
    json.dump(
        {'total': len(strings), 'strings': sorted(strings), 'per_file': per_file},
        fh,
        ensure_ascii=False,
        indent=2,
    )
    fh.write('\n')
print('unique strings', len(strings))
print('files', len(per_file))
print('wrote', out)
