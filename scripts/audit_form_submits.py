"""Audit ALL POST forms across ALL templates for proper submit handling."""

import os
import re

results = []
total_forms = 0
no_protection = []

for root, dirs, files in os.walk('templates'):
    for f in files:
        if not f.endswith('.html'):
            continue
        path = os.path.join(root, f)
        rel = path.replace(os.sep, '/')
        s = open(path, encoding='utf-8', errors='replace').read()

        post_forms = re.findall(r'<form[^>]*method\s*=\s*["\']?POST["\']?', s, re.I)
        if not post_forms:
            continue

        has_js = bool(re.search(r'addEventListener.*submit|\.submit\(|fetch.*POST', s))
        has_disabled = bool(
            re.search(r'\.disabled\s*=\s*true|btn-loading|spinner-border|submitting', s)
        )

        total_forms += len(post_forms)
        if not has_disabled:
            no_protection.append((rel, len(post_forms)))

        results.append((rel, len(post_forms), has_js, has_disabled))

print(f'Total files with POST forms: {len(results)}')
print(f'Total POST forms: {total_forms}')
print(f'Files WITH disabled/loading state: {sum(1 for r in results if r[3])}')
print(f'Files WITHOUT protection: {len(no_protection)}')
print()

if no_protection:
    print('FILES NEEDING FIX:')
    for f, n in sorted(no_protection):
        print(f'  {f} ({n} form(s))')
