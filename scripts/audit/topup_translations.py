"""Second pass: translate strings missed by the batch run, one per request."""

import json
import os
import time

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'ui_strings.json')
OUT = os.path.join(ROOT, 'app', 'shared', 'i18n_catalog.json')
ENDPOINT = 'https://translate.googleapis.com/translate_a/single'

with open(SRC, encoding='utf-8') as fh:
    strings = json.load(fh)['strings']
with open(OUT, encoding='utf-8') as fh:
    catalog = json.load(fh)

missing = [s for s in strings if s not in catalog and '\n' not in s and len(s) <= 60]
print(f'top-up: {len(missing)} strings')
added = 0
for index, source in enumerate(missing):
    params = {'client': 'gtx', 'sl': 'ar', 'tl': 'en', 'dt': 't', 'q': source}
    for attempt in range(3):
        try:
            resp = requests.get(ENDPOINT, params=params, timeout=20)
            data = resp.json()
            target = data[0][0][0].strip()
            if target and target != source:
                catalog[source] = target
                added += 1
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.6 * (attempt + 1))
    if index % 200 == 0:
        print(f'  {index}/{len(missing)} +{added}')

with open(OUT, 'w', encoding='utf-8') as fh:
    json.dump(catalog, fh, ensure_ascii=False, indent=2)
    fh.write('\n')
print('added', added, 'total', len(catalog))
