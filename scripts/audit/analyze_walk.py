"""Summarise the walkthrough, separating expected gaps from real defects."""

import collections
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'walk_results.json')
OUT = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'findings.md')

with open(SRC, encoding='utf-8') as fh:
    data = json.load(fh)

results = data['results']
placeholder = re.compile(r'/1(?:/|$)')


def is_expected_404(r):
    return r.get('status') == 404 and bool(placeholder.search(r['path']))


real = []
for r in results:
    status = r.get('status')
    if status == 200 and not r.get('markers') and not r.get('console_errors'):
        continue
    if is_expected_404(r):
        continue
    if status == 404 and r.get('final_url', '').endswith('/login'):
        continue
    real.append(r)

lines = [
    '# نتائج الجولة البصرية والوظيفية',
    '',
    f'صفحات تمت زيارتها: **{len(results)}** — لقطات شاشة: **{sum(1 for r in results if r.get("screenshot"))}**.',
    '',
    'التوزيع: '
    + ', '.join(
        f'{k}: {v}'
        for k, v in sorted(collections.Counter(str(r.get('status')) for r in results).items())
    ),
    '',
    '> المسارات ذات المعرّف الرقمي (`/1/`) أُزورت بمعرّف تجريبي؛ نتيجة 404 فيها متوقعة لأن البيانات السريرية تُدخل عبر الواجهة ولا توجد بعد في المستأجر التجريبي.',
    '',
    '## علل تحتاج مراجعة',
    '',
    '| الدور | الحالة | المسار | Endpoint | ملاحظة |',
    '|---|---:|---|---|---|',
]
for r in real:
    notes = []
    if r.get('markers'):
        notes.append('marker:' + ','.join(r['markers']))
    if r.get('console_errors'):
        notes.append('console:' + (r['console_errors'][0][:70] if r['console_errors'] else ''))
    if r.get('error'):
        notes.append('error:' + r['error'][:70])
    lines.append(
        f'| `{r["role"]}` | {r.get("status")} | `{r["path"]}` | `{r["endpoint"]}` | {" / ".join(notes)} |'
    )

lines += ['', '## صفحات سليمة حسب الدور', '']
ok = collections.Counter(r['role'] for r in results if r.get('status') == 200)
for role, count in sorted(ok.items()):
    lines.append(f'- `{role}`: {count} صفحة نجحت (200)')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(lines) + '\n')

print(
    f'results={len(results)} real_issues={len(real)} screenshots={sum(1 for r in results if r.get("screenshot"))}'
)
print('\nSTATUS != 200 / with markers:')
for r in real[:120]:
    print(f'  {r["role"]:12} {r.get("status")!s:5} {r["path"]}')
