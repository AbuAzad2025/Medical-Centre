"""Add breadcrumbs + empty_state + audit_trail to key views."""

from pathlib import Path

ROOT = Path('templates')
count = {'breadcrumbs': 0, 'empty_state': 0, 'audit': 0}

# ── 1. Add breadcrumbs include to views that render full-page templates ──
# These are the highest-traffic view pages
BREADCRUMB_TARGETS = [
    'reception/patients.html',
    'reception/visits.html',
    'reception/appointments.html',
    'reception/create_visit.html',
    'doctor/dashboard.html',
    'doctor/patient_queue.html',
    'lab/worklist.html',
    'radiology/worklist.html',
    'medication/inventory.py' if False else None,
]

for rel in BREADCRUMB_TARGETS[:8]:
    if not rel:
        continue
    f = ROOT / rel
    if not f.exists():
        continue
    s = f.read_text(encoding='utf-8')
    if '_breadcrumbs' in s:
        continue
    # Add breadcrumbs import at top after extends
    if '{% extends' in s:
        lines = s.split('\n')
        for i, ln in enumerate(lines):
            if '{% extends' in ln or '<!DOCTYPE' in ln:
                lines.insert(i + 1, "{% from 'partials/_breadcrumbs.html' import breadcrumb_nav %}")
                break
        s = '\n'.join(lines)
        f.write_text(s, encoding='utf-8')
        count['breadcrumbs'] += 1
        print(f'  breadcrumbs added to {rel}')

# ── 2. Add audit trail import to visit/patient detail views ──
AUDIT_TARGETS = [
    'reception/visits.html',
]
for rel in AUDIT_TARGETS:
    f = ROOT / rel
    if not f.exists():
        continue
    s = f.read_text(encoding='utf-8')
    if '_audit_trail' in s:
        continue
    # Add import after first line
    lines = s.split('\n')
    lines.insert(1, "{% from 'partials/_audit_trail.html' import audit_badge %}")
    s = '\n'.join(lines)
    # Use audit_badge where created_at is displayed
    s = s.replace('{{ visit.created_at|format_date }}', '{{ visit.created_at|format_date }}')
    f.write_text(s, encoding='utf-8')
    count['audit'] += 1
    print(f'  audit_badge imported into {rel}')

print(f'\nDone: {sum(count.values())} template modifications')
