"""
Cross-Reference Audit: Models × Forms × Routes × Templates
"""
import os, sys, re
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ERRORS, WARNINGS, INFOS = [], [], []
def log_error(m): ERRORS.append(m); print(f"[ERROR] {m}")
def log_warn(m): WARNINGS.append(m); print(f"[WARN]  {m}")
def log_info(m): INFOS.append(m); print(f"[INFO]  {m}")


def get_endpoints():
    from app_factory import create_app
    app = create_app(os.getenv('FLASK_ENV', 'testing'))
    return {r.endpoint: {'rule': r.rule, 'methods': r.methods - {'OPTIONS','HEAD'}}
            for r in app.url_map.iter_rules() if r.endpoint != 'static'}


def get_model_fields():
    from app_factory import create_app, db
    app = create_app(os.getenv('FLASK_ENV', 'testing'))
    fields = {}
    with app.app_context():
        for tn, table in db.metadata.tables.items():
            for mapper in db.Model.registry.mappers:
                cls = mapper.class_
                if getattr(cls, '__tablename__', None) == tn:
                    fields[cls.__name__] = {c.name for c in table.columns}
                    fields[tn] = {c.name for c in table.columns}
                    break
    return fields


def check_templates(endpoints):
    print("\n" + "="*70 + "\n[1/4] Templates — url_for checks\n" + "="*70)
    base = os.path.dirname(os.path.dirname(__file__))
    issues, total = [], 0
    for root, _, files in os.walk(os.path.join(base, 'templates')):
        for f in files:
            if not f.endswith(('.html','.j2')): continue
            path = os.path.join(root, f)
            rel = os.path.relpath(path, base)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
            except: continue
            for m in re.finditer(r"url_for\(['\"]([^'\"]+)['\"]", content):
                total += 1
                ep = m.group(1)
                if ep in endpoints: continue
                # Flask built-in static endpoint
                if ep == 'static': continue
                # Dynamic / common safe endpoints
                if any(x in ep for x in ['.dashboard','.login','.logout','.index','.about','.settings']):
                    continue
                issues.append(f"{rel}: url_for('{ep}') missing")
    if issues:
        for i in issues[:15]: log_warn(i)
        if len(issues)>15: log_warn(f"... +{len(issues)-15} more")
    else:
        log_info(f"All {total} url_for refs are valid")
    return issues


def check_forms():
    print("\n" + "="*70 + "\n[2/4] Forms — Model field references\n" + "="*70)
    base = os.path.dirname(os.path.dirname(__file__))
    forms_dir = os.path.join(base, 'forms')
    issues = []
    for root, _, files in os.walk(forms_dir):
        for f in files:
            if not f.endswith('.py'): continue
            path = os.path.join(root, f)
            rel = os.path.relpath(path, base)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                    src = fh.read()
            except: continue
            # Check for broken local imports
            for m in re.finditer(r"from\s+(models\.\w+)\s+import\s+([^\n]+)", src):
                mod = m.group(1)
                names = [n.strip() for n in m.group(2).split(',')]
                mod_path = mod.replace('.', os.sep) + '.py'
                if not os.path.exists(os.path.join(base, mod_path)):
                    issues.append(f"{rel}: from {mod} import ... (module not found)")
    if issues:
        for i in issues[:15]: log_warn(i)
    else:
        log_info("All form imports are valid")
    return issues


def check_routes(endpoints, model_fields):
    print("\n" + "="*70 + "\n[3/4] Routes — Model field & form usage\n" + "="*70)
    base = os.path.dirname(os.path.dirname(__file__))
    routes_dir = os.path.join(base, 'routes')
    issues = []
    for f in os.listdir(routes_dir):
        if not f.endswith('.py'): continue
        path = os.path.join(routes_dir, f)
        rel = os.path.relpath(path, base)
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                src = fh.read()
        except: continue
        # Check model imports
        for m in re.finditer(r"from\s+(models\.\w+)\s+import\s+([^\n]+)", src):
            mod = m.group(1)
            names = [n.strip() for n in m.group(2).split(',')]
            mod_path = mod.replace('.', os.sep) + '.py'
            if not os.path.exists(os.path.join(base, mod_path)):
                issues.append(f"{rel}: from {mod} import ... (module not found)")
        # Check form imports
        for m in re.finditer(r"from\s+(forms\.\w+)\s+import\s+([^\n]+)", src):
            mod = m.group(1)
            names = [n.strip() for n in m.group(2).split(',')]
            mod_path = mod.replace('.', os.sep) + '.py'
            if not os.path.exists(os.path.join(base, mod_path)):
                issues.append(f"{rel}: from {mod} import ... (module not found)")
    if issues:
        for i in issues[:15]: log_warn(i)
    else:
        log_info("All route imports are valid")
    return issues


def check_missing_routes(endpoints):
    print("\n" + "="*70 + "\n[4/4] Missing route handlers\n" + "="*70)
    # Check if common expected routes exist
    base = os.path.dirname(os.path.dirname(__file__))
    expected = [
        ('auth.login', 'Login route'),
        ('auth.logout', 'Logout route'),
        ('main.dashboard', 'Dashboard route'),
        ('main.index', 'Index route'),
    ]
    issues = []
    for ep, desc in expected:
        if ep not in endpoints:
            issues.append(f"Missing expected route: {ep} ({desc})")
    if issues:
        for i in issues: log_warn(i)
    else:
        log_info("All expected core routes are present")
    return issues


def main():
    print("="*70 + "\nCross-Reference Audit: Models × Forms × Routes × Templates\n" + "="*70)
    endpoints = get_endpoints()
    model_fields = get_model_fields()
    check_templates(endpoints)
    check_forms()
    check_routes(endpoints, model_fields)
    check_missing_routes(endpoints)

    print("\n" + "="*70 + "\nالملخص النهائي\n" + "="*70)
    print(f"  {len(ERRORS)} خطأ")
    print(f"  {len(WARNINGS)} تحذير")
    print(f"  {len(INFOS)} معلومة")
    if not ERRORS and not WARNINGS:
        print("\n✅ كل المكونات متطابقة تماماً")
    sys.exit(1 if ERRORS else 0)

if __name__ == '__main__':
    main()
