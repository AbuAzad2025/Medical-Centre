"""Remove phone-number literals accidentally captured from templates into the catalog."""

import json
import re

ROOT = 'app/shared/i18n_catalog.json'
with open(ROOT, encoding='utf-8') as fh:
    catalog = json.load(fh)

pattern = re.compile(r'(\+?\d[\d\s\-()]{7,}\d)')
removed = []
for key in list(catalog):
    if pattern.search(key) or pattern.search(catalog[key]):
        removed.append(key)
        del catalog[key]

with open(ROOT, 'w', encoding='utf-8') as fh:
    json.dump(catalog, fh, ensure_ascii=False, indent=2)
    fh.write('\n')
print('removed', len(removed), 'entries')
