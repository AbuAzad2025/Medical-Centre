"""
Dashboard + Front-End Quality Audit (simplified)
"""
import os, sys, re
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ISSUES = []

def issue(msg):
    ISSUES.append(msg)
    print(f"  [ISSUE] {msg}")

print("=" * 70)
print(" DASHBOARD + FRONT-END QUALITY AUDIT")
print("=" * 70)

route_files = list((ROOT / 'routes').rglob('*.py'))
template_files = list((ROOT / 'templates').rglob('*.html'))

# 1. Dashboard routes
print("\n--- 1. DASHBOARD ROUTES ---")
dashboards = []
for rf in route_files:
    text = rf.read_text(encoding='utf-8')
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if 'dashboard' in line.lower() and "route(" in line:
            func = None
            for j in range(i, min(len(lines), i+8)):
                m = re.search(r"^def\s+(\w+)", lines[j])
                if m:
                    func = m.group(1)
                    break
            if func:
                roles = []
                has_login = False
                # Decorators are between route() and def() — search after route line too
                for j in range(max(0, i-3), min(len(lines), i+6)):
                    if any(x in lines[j] for x in ['login_required', 'super_admin_required', 'reception_only', 'can_create_visits', 'can_modify_patient_data', 'role_required_json', 'AccessControlService.require_permission']):
                        has_login = True
                    if 'role_required' in lines[j]:
                        # Extract quoted strings
                        roles = re.findall(r"['\"]([a-zA-Z_]+)['\"]", lines[j])
                dashboards.append({'file': rf.name, 'func': func, 'roles': roles, 'login': has_login})

for d in sorted(dashboards, key=lambda x: x['file']):
    r = ', '.join(d['roles']) if d['roles'] else 'NO ROLES'
    l = 'login' if d['login'] else 'NO LOGIN'
    print(f"  {d['file']:25} | {d['func']:20} | {r:25} | {l}")
    if not d['login']:
        issue(f"{d['file']}:{d['func']} missing @login_required")

# 2. Duplicate dashboards
print("\n--- 2. DUPLICATE DASHBOARDS ---")
dash_templates = [t for t in template_files if 'dashboard' in t.name.lower()]
by_name = {}
for t in dash_templates:
    base = t.name.replace('_new', '').replace('_old', '')
    by_name.setdefault(base, []).append(str(t.relative_to(ROOT / 'templates')))

for name, paths in by_name.items():
    if len(paths) > 1:
        print(f"  DUPLICATE: {name}")
        for p in paths:
            print(f"    - {p}")
        # Check usage
        used = []
        for rf in route_files:
            txt = rf.read_text(encoding='utf-8')
            for p in paths:
                if p.replace('\\', '/') in txt:
                    used.append(p)
        unused = [p for p in paths if p not in used]
        if unused:
            issue(f"Orphan dashboards (unused): {unused}")

# 3. Visual consistency
print("\n--- 3. VISUAL CONSISTENCY ---")
for t in dash_templates[:40]:
    txt = t.read_text(encoding='utf-8')
    has_extends = '{% extends' in txt
    has_card = 'card' in txt.lower()
    has_bootstrap = 'bootstrap' in txt.lower() or 'col-' in txt.lower()
    if not has_extends:
        issue(f"{t.name} missing extends")
    if not has_bootstrap:
        issue(f"{t.name} no Bootstrap")

# 4. Missing template folders
print("\n--- 4. BLUEPRINT TEMPLATE FOLDERS ---")
bps = set()
for rf in route_files:
    txt = rf.read_text(encoding='utf-8')
    for m in re.finditer(r"Blueprint\s*\(\s*['\"](\w+)['\"]", txt):
        bps.add(m.group(1))

ok_without_folder = {'auth','main','fhir','barcode','cds','pathway','or','referral','vaccination','clinical_coding','security','sso','mfa','backup_restore','ai_imaging','telemedicine','patient_education','what_if','biometric','nursing_assessment','emar'}
for bp in sorted(bps):
    if not (ROOT / 'templates' / bp).exists() and bp not in ok_without_folder:
        issue(f"Blueprint '{bp}' missing template folder")

# Summary
print("\n" + "=" * 70)
print(f" TOTAL ISSUES: {len(ISSUES)}")
print("=" * 70)
for i in ISSUES:
    print(f"  - {i}")
if not ISSUES:
    print("  All checks passed")
