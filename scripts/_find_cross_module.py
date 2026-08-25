"""Find ALL cross-module url_for references in templates."""

import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

cross = []
for root, dirs, files in os.walk('templates'):
    parts = root.replace(os.sep, '/').split('/')
    if 'partials' in parts or 'errors' in parts or 'emails' in parts or 'layouts' in parts:
        continue
    own_module = None
    for p in parts:
        if p not in ('templates', '.'):
            own_module = p
            break
    if not own_module:
        continue

    for f in files:
        if not f.endswith('.html'):
            continue
        path = os.path.join(root, f)
        rel = path.replace(os.sep, '/')
        s = open(path, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r"url_for\(['\"](\w+)\.(\w+)", s):
            bp = m.group(1)
            if bp != own_module and bp not in ('main', 'static'):
                cross.append((rel, own_module, bp))

from collections import Counter

counter = Counter((src.split('/')[0], tgt) for _, src, tgt in cross)
print('Cross-module url_for references:')
print('=' * 50)
for (src_mod, tgt_bp), count in sorted(counter.items()):
    print(f'  {src_mod} -> {tgt_bp}: {count} refs')
print(f'\nTotal: {len(cross)} references across {len(counter)} module pairs')
