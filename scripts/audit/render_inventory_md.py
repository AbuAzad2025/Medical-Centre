"""Render docs/PAGE_AUDIT/inventory.md from inventory.json."""

import collections
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'inventory.json')
OUT = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'inventory.md')

with open(SRC, encoding='utf-8') as fh:
    data = json.load(fh)

routes = data['routes']
by_role = collections.defaultdict(list)
for r in routes:
    by_role[r['role']].append(r)

lines = [
    '# جرد صفحات النظام وروابطه',
    '',
    f'إجمالي المسارات المسجّلة: **{len(routes)}** — منها **{sum(1 for r in routes if r["is_get"])}** مسار GET (صفحات/واجهات قابلة للفتح).',
    '',
    'المصدر: `route_inventory.json` المولّد من التطبيق الحيّ، مع تصنيف المسار إلى وحدة منتج ودور مستخدم عبر `app/core/module_route_map.py`.',
    '',
    '## توزيع المسارات حسب الدور',
    '',
    '| الدور | إجمالي المسارات | صفحات GET |',
    '|---|---:|---:|',
]
for role in sorted(by_role):
    items = by_role[role]
    lines.append(f'| `{role}` | {len(items)} | {sum(1 for r in items if r["is_get"])} |')

lines += [
    '',
    '## توزيع المسارات حسب الوحدة',
    '',
    '| الوحدة | المسارات |',
    '|---|---:|',
]
by_module = collections.Counter(r['module'] for r in routes)
for module, count in by_module.most_common():
    lines.append(f'| `{module}` | {count} |')

lines += [
    '',
    '## قائمة الصفحات التفصيلية',
    '',
    'الرموز: `GET` صفحة/واجهة، `POST` إجراء، `API` واجهة JSON، `page` واجهة HTML.',
]
for role in sorted(by_role):
    gets = [r for r in by_role[role] if r['is_get']]
    if not gets:
        continue
    lines += ['', f'### الدور: `{role}` ({len(gets)} صفحة)', '']
    lines += ['| الوحدة | المسار | Endpoint | النوع |', '|---|---|---|---|']
    for r in gets:
        kind = 'API' if r['is_api'] else 'page'
        lines.append(f'| `{r["module"]}` | `{r["path"]}` | `{r["endpoint"]}` | {kind} |')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(lines) + '\n')
print(f'wrote {OUT}: {len(lines)} lines')
