"""Add English entries for portal/auth strings missing from the runtime catalog."""

import glob
import json
import os
import re
import sys

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

CATALOG = os.path.join(ROOT, 'app', 'shared', 'i18n_catalog.json')
SOURCES = (
    glob.glob(os.path.join(ROOT, 'templates', 'portal', '*.html'))
    + glob.glob(os.path.join(ROOT, 'templates', 'auth', '*.html'))
    + glob.glob(os.path.join(ROOT, 'templates', 'kiosk', '*.html'))
)
ENDPOINT = 'https://translate.googleapis.com/translate_a/single'

with open(CATALOG, encoding='utf-8') as fh:
    catalog = json.load(fh)

strings = set()
for path in SOURCES:
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    for match in re.finditer(r"_\(\s*'([^'\n]+)'\s*\)", text):
        value = match.group(1)
        if re.search(r'[\u0600-\u06ff]', value) and value not in catalog:
            strings.add(value)

items = sorted(strings)
print('missing', len(items))
for i in range(0, len(items), 40):
    chunk = items[i : i + 40]
    try:
        resp = requests.get(
            ENDPOINT,
            params={'client': 'gtx', 'sl': 'ar', 'tl': 'en', 'dt': 't', 'q': '\n'.join(chunk)},
            timeout=30,
        )
        segments = resp.json()[0]
        for source, seg in zip(chunk, segments, strict=False):
            value = seg[0].strip()
            if value and value != source:
                catalog[source] = value
    except Exception as exc:  # noqa: BLE001
        print('batch failed', str(exc)[:80])

with open(CATALOG, 'w', encoding='utf-8') as fh:
    json.dump(catalog, fh, ensure_ascii=False, indent=2)
    fh.write('\n')
print('catalog now', len(catalog))
