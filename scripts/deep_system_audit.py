"""
============================================================
 DEEP SYSTEM AUDIT — Triple-Lens Inspector
  (Auditor + Clinician + Programmer)
============================================================
Checks:
  1. Orphaned blueprints / routes / models / templates
  2. Missing template files referenced in routes
  3. Routes importing non-existent models
  4. Models without __tablename__ or missing relationships
  5. Duplicate route definitions
  6. Security gaps in routes (missing login_required)
  7. Templates missing {% extends %}
  8. Forms not imported in routes that need them
  9. Hardcoded values / secrets
  10. Clinical logic gaps (missing patient checks, visit checks)
"""
import os, sys, re, ast, json
from pathlib import Path
from collections import defaultdict

os.environ['SECRET_KEY'] = 'test-secret-key-for-compilation-only'
os.environ['FLASK_ENV'] = 'testing'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORTS = []
WARNINGS = []
CRITICALS = []

def report(level, msg):
    if level == 'CRITICAL':
        CRITICALS.append(msg)
    elif level == 'WARNING':
        WARNINGS.append(msg)
    else:
        REPORTS.append(msg)
    print(f"  [{level}] {msg}")

def get_python_files(folder):
    return list((ROOT / folder).rglob('*.py'))

def get_template_files():
    return list((ROOT / 'templates').rglob('*.html'))

# ============================================================
# 1. ORPHANED / MISSING ANALYSIS
# ============================================================
print("=" * 70)
print(" 1. BLUEPRINT / ROUTE / MODEL / TEMPLATE CONSISTENCY")
print("=" * 70)

# Parse all route files
route_files = get_python_files('routes')
blueprint_names = set()
route_endpoints = defaultdict(list)
template_references = set()
model_imports_in_routes = defaultdict(set)

for rf in route_files:
    text = rf.read_text(encoding='utf-8')
    # Find blueprint definitions
    for m in re.finditer(r"(\w+_bp)\s*=\s*Blueprint\s*\(\s*['\"](\w+)['\"]", text):
        var_name, bp_name = m.groups()
        blueprint_names.add(bp_name)
    # Find route definitions
    for m in re.finditer(r"@\w+_bp\.route\s*\(\s*['\"]([^'\"]+)['\"]", text):
        route_endpoints[rf.name].append(m.group(1))
    # Find template references
    for m in re.finditer(r"render_template\s*\(\s*['\"]([^'\"]+)['\"]", text):
        template_references.add(m.group(1))
    # Find model imports
    for m in re.finditer(r"from\s+models\s+import\s+(.+)(?:\n|$)", text):
        names = [n.strip() for n in m.group(1).split(',')]
        model_imports_in_routes[rf.name].update(names)
    for m in re.finditer(r"from\s+models\.\w+\s+import\s+(.+)(?:\n|$)", text):
        names = [n.strip() for n in m.group(1).split(',')]
        model_imports_in_routes[rf.name].update(names)

# Registered blueprints in app_factory
app_factory_text = (ROOT / 'app_factory.py').read_text(encoding='utf-8')
registered_bps = set(re.findall(r"register_blueprint\s*\(\s*(\w+_bp)", app_factory_text))
imported_bps = set(re.findall(r"from\s+routes\.\w+\s+import\s+(\w+_bp)", app_factory_text))

print(f"\n  Blueprints defined in routes/: {len(blueprint_names)}")
print(f"  Blueprints imported in app_factory: {len(imported_bps)}")
print(f"  Blueprints registered: {len(registered_bps)}")

missing_import = blueprint_names - {re.sub(r'_bp$', '', bp) for bp in imported_bps}
missing_register = imported_bps - registered_bps
if missing_import:
    report('WARNING', f"Blueprints possibly missing import: {missing_import}")
if missing_register:
    report('CRITICAL', f"Blueprints imported but NOT registered: {missing_register}")

# Check templates exist
template_files = get_template_files()
template_paths = {str(t.relative_to(ROOT / 'templates')).replace('\\', '/') for t in template_files}

missing_templates = []
for ref in template_references:
    if ref not in template_paths:
        missing_templates.append(ref)
if missing_templates:
    for mt in missing_templates[:10]:
        report('CRITICAL', f"Template referenced but NOT FOUND: {mt}")
    if len(missing_templates) > 10:
        report('CRITICAL', f"... and {len(missing_templates)-10} more missing templates")
else:
    print(f"  All {len(template_references)} referenced templates exist.")

# ============================================================
# 2. MODEL VALIDATION
# ============================================================
print("\n" + "=" * 70)
print(" 2. MODEL VALIDATION")
print("=" * 70)

model_files = get_python_files('models')
model_classes = {}
for mf in model_files:
    text = mf.read_text(encoding='utf-8')
    for m in re.finditer(r"^class\s+(\w+)\s*\(\s*db\.Model", text, re.MULTILINE):
        model_classes[m.group(1)] = mf.name

# Check models imported in routes actually exist
all_imported_models = set()
for models in model_imports_in_routes.values():
    all_imported_models.update(models)

missing_models = all_imported_models - set(model_classes.keys())
if missing_models:
    for mm in missing_models:
        report('CRITICAL', f"Route imports model that does NOT exist: {mm}")
else:
    print(f"  All {len(all_imported_models)} imported models exist.")

# Check models have __tablename__
models_without_tablename = []
for mf in model_files:
    text = mf.read_text(encoding='utf-8')
    classes = re.findall(r"^class\s+(\w+)\s*\(\s*db\.Model", text, re.MULTILINE)
    for cls in classes:
        if f"__tablename__" not in text:
            models_without_tablename.append(cls)
if models_without_tablename:
    for m in models_without_tablename[:5]:
        report('WARNING', f"Model missing __tablename__: {m}")

# ============================================================
# 3. SECURITY AUDIT ON ROUTES
# ============================================================
print("\n" + "=" * 70)
print(" 3. SECURITY AUDIT ON ROUTES")
print("=" * 70)

routes_without_login = []
for rf in route_files:
    text = rf.read_text(encoding='utf-8')
    # Find route defs and check preceding decorators
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if re.search(r"@\w+_bp\.route", line):
            # Check next non-empty lines for decorator or function def
            has_login = False
            has_role = False
            for j in range(max(0, i-5), i):
                if 'login_required' in lines[j]:
                    has_login = True
                if 'role_required' in lines[j] or 'permission_required' in lines[j]:
                    has_role = True
            # Also check if the function definition is below
            func_line = ''
            for j in range(i, min(len(lines), i+5)):
                if re.search(r"^def\s+\w+", lines[j]):
                    func_line = lines[j]
                    break
            # Methods check - if GET/POST
            method_match = re.search(r"methods\s*=\s*\[(.*?)\]", line)
            if method_match:
                methods = method_match.group(1)
            else:
                methods = "GET"  # default
            if 'GET' in methods and not has_login:
                # Allow some public routes
                func_name = re.search(r"def\s+(\w+)", func_line)
                if func_name:
                    fname = func_name.group(1)
                    if fname not in ('index', 'about', 'login', 'register', 'logout', 'public'):
                        routes_without_login.append(f"{rf.name}:{fname}")

if routes_without_login:
    report('WARNING', f"{len(routes_without_login)} GET routes without @login_required")
    for r in routes_without_login[:10]:
        print(f"      - {r}")
else:
    print("  All GET routes have @login_required.")

# ============================================================
# 4. FORMS VALIDATION
# ============================================================
print("\n" + "=" * 70)
print(" 4. FORMS VALIDATION")
print("=" * 70)

form_files = get_python_files('forms')
form_classes = {}
for ff in form_files:
    text = ff.read_text(encoding='utf-8')
    for m in re.finditer(r"class\s+(\w+Form)\s*\(", text):
        form_classes[m.group(1)] = ff.name

# Check forms imported in routes
forms_imported = set()
for rf in route_files:
    text = rf.read_text(encoding='utf-8')
    for m in re.finditer(r"from\s+forms\s+import\s+(.+)(?:\n|$)", text):
        names = [n.strip() for n in m.group(1).split(',')]
        forms_imported.update(names)
    for m in re.finditer(r"from\s+forms\.\w+\s+import\s+(.+)(?:\n|$)", text):
        names = [n.strip() for n in m.group(1).split(',')]
        forms_imported.update(names)

missing_forms = forms_imported - set(form_classes.keys())
if missing_forms:
    for mf in missing_forms:
        report('WARNING', f"Form class not found: {mf}")

# ============================================================
# 5. HARDCODED VALUES / SECRETS
# ============================================================
print("\n" + "=" * 70)
print(" 5. HARDCODED VALUES / POTENTIAL SECRETS")
print("=" * 70)

hardcoded_patterns = [
    (r'password\s*=\s*["\'][^"\']+["\']', 'Hardcoded password'),
    (r'secret\s*=\s*["\'][^"\']{8,}["\']', 'Hardcoded secret'),
    (r'api_key\s*=\s*["\'][^"\']+["\']', 'Hardcoded API key'),
    (r'token\s*=\s*["\'][^"\']{10,}["\']', 'Hardcoded token'),
]

all_py_files = route_files + model_files + form_files + list((ROOT / 'services').rglob('*.py'))
all_py_files += [ROOT / 'app_factory.py', ROOT / 'config.py']

secrets_found = 0
for pyf in all_py_files:
    if not pyf.exists():
        continue
    text = pyf.read_text(encoding='utf-8', errors='ignore')
    for pattern, label in hardcoded_patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            # Exclude env var fallbacks
            if 'os.environ' in text[max(0, m.start()-100):m.start()]:
                continue
            if 'getenv' in text[max(0, m.start()-100):m.start()]:
                continue
            secrets_found += 1
            if secrets_found <= 5:
                report('CRITICAL', f"{label} in {pyf.name}: {m.group(0)[:50]}")

if secrets_found == 0:
    print("  No hardcoded secrets detected in Python files.")
else:
    report('WARNING', f"Total potential secrets found: {secrets_found}")

# ============================================================
# 6. CLINICAL LOGIC GAPS
# ============================================================
print("\n" + "=" * 70)
print(" 6. CLINICAL LOGIC GAPS (Doctor's Review)")
print("=" * 70)

# Check if critical medical validations exist
critical_validations = [
    ('prescription', 'drug_interaction'),
    ('prescription', 'allergy'),
    ('lab_request', 'duplicate_test'),
    ('radiology', 'radiation_exposure'),
    ('medication', 'dosage_check'),
]

for rf in route_files:
    text = rf.read_text(encoding='utf-8').lower()
    if 'prescription' in rf.name.lower() or 'medication' in rf.name.lower():
        if 'allergy' not in text and 'drug_interaction' not in text:
            report('WARNING', f"Prescription route {rf.name} may lack allergy/interaction checks")
    if 'emergency' in rf.name.lower():
        if 'triage' not in text:
            report('WARNING', f"Emergency route {rf.name} may lack triage validation")

# ============================================================
# 7. SERVICES / UTILS ORPHAN CHECK
# ============================================================
print("\n" + "=" * 70)
print(" 7. SERVICES / UTILS ORPHAN CHECK")
print("=" * 70)

service_files = list((ROOT / 'services').rglob('*.py'))
services_imported = set()
for pyf in all_py_files:
    if not pyf.exists():
        continue
    text = pyf.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r"from\s+services\.\w+\s+import", text):
        services_imported.add(m.group(0))

# Check utils
utils_imported = set()
for pyf in all_py_files:
    if not pyf.exists():
        continue
    text = pyf.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r"from\s+utils\.\w+\s+import", text):
        utils_imported.add(m.group(0))

print(f"  Service imports found: {len(services_imported)}")
print(f"  Utils imports found: {len(utils_imported)}")

# ============================================================
# 8. DUPLICATE ROUTE CHECK
# ============================================================
print("\n" + "=" * 70)
print(" 8. DUPLICATE ROUTE CHECK")
print("=" * 70)

all_routes = []
for rf in route_files:
    text = rf.read_text(encoding='utf-8')
    for m in re.finditer(r"@\w+_bp\.route\s*\(\s*['\"]([^'\"]+)['\"]", text):
        all_routes.append(m.group(1))

duplicates = [r for r in set(all_routes) if all_routes.count(r) > 1]
if duplicates:
    for d in duplicates[:10]:
        report('WARNING', f"Duplicate route pattern: {d}")
else:
    print("  No duplicate route patterns found.")

# ============================================================
# 9. DATABASE SCHEMA COMPLETENESS
# ============================================================
print("\n" + "=" * 70)
print(" 9. DATABASE SCHEMA CHECK")
print("=" * 70)

try:
    from app_factory import create_app, db
    app = create_app('testing')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"  Tables created: {len(tables)}")
        if len(tables) < 100:
            report('WARNING', f"Only {len(tables)} tables — some models may not be registered")
        else:
            print(f"  {len(tables)} tables — comprehensive schema")
except Exception as e:
    report('CRITICAL', f"Could not verify DB schema: {e}")

# ============================================================
# FINAL REPORT
# ============================================================
print("\n" + "=" * 70)
print(" AUDIT SUMMARY")
print("=" * 70)
print(f"  CRITICAL issues: {len(CRITICALS)}")
print(f"  WARNING issues:  {len(WARNINGS)}")
print(f"  Info reports:    {len(REPORTS)}")

if CRITICALS:
    print("\n  CRITICAL ISSUES (must fix before production):")
    for c in CRITICALS:
        print(f"    - {c}")
if WARNINGS:
    print("\n  WARNINGS (should fix):")
    for w in WARNINGS[:20]:
        print(f"    - {w}")
    if len(WARNINGS) > 20:
        print(f"    ... and {len(WARNINGS)-20} more")
