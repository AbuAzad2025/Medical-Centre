"""
============================================================
 DEEP SYSTEM AUDIT v2 — Dynamic Import Verification
============================================================
"""
import os, sys, re
from pathlib import Path

os.environ['SECRET_KEY'] = 'test-secret-key-for-compilation-only'
os.environ['FLASK_ENV'] = 'testing'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CRITICALS = []
WARNINGS = []

def report(level, msg):
    if level == 'CRITICAL':
        CRITICALS.append(msg)
    else:
        WARNINGS.append(msg)
    print(f"  [{level}] {msg}")

print("=" * 70)
print(" DYNAMIC IMPORT VERIFICATION")
print("=" * 70)

# 1. Verify all models can be imported
print("\n--- 1. MODEL IMPORT VERIFICATION ---")
from models import __all__ as model_all
import models

route_files = list((ROOT / 'routes').rglob('*.py'))
for rf in route_files:
    text = rf.read_text(encoding='utf-8')
    # Find all import lines mentioning models
    for line in text.split('\n'):
        if 'from models' in line and 'import' in line:
            # Parse import
            try:
                imported = line.split('import')[1].split('#')[0].strip()
                names = [n.strip().split(' as ')[0] for n in imported.split(',')]
                for name in names:
                    if not hasattr(models, name):
                        report('CRITICAL', f"{rf.name}: imports '{name}' but not in models package")
            except Exception:
                pass

if not CRITICALS:
    print("  All route model imports verified successfully.")

# 2. Template existence verification
print("\n--- 2. TEMPLATE EXISTENCE VERIFICATION ---")
template_refs = set()
for rf in route_files:
    text = rf.read_text(encoding='utf-8')
    for m in re.finditer(r"render_template\s*\(\s*['\"]([^'\"]+)['\"]", text):
        template_refs.add(m.group(1))

template_files = {str(t.relative_to(ROOT / 'templates')).replace('\\', '/') for t in (ROOT / 'templates').rglob('*.html')}

missing = [t for t in template_refs if t not in template_files]
if missing:
    for m in missing:
        report('CRITICAL', f"Missing template: {m}")
else:
    print(f"  All {len(template_refs)} referenced templates exist.")

# 3. DB Schema
print("\n--- 3. DATABASE SCHEMA ---")
try:
    from app_factory import create_app, db
    app = create_app('testing')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        from sqlalchemy import inspect
        tables = inspect(db.engine).get_table_names()
        print(f"  Tables: {len(tables)}")
except Exception as e:
    report('CRITICAL', f"DB schema failed: {e}")

# 4. Blueprint registration
print("\n--- 4. BLUEPRINT REGISTRATION ---")
app_factory_text = (ROOT / 'app_factory.py').read_text(encoding='utf-8')
imported = set(re.findall(r"^from routes\.\w+ import (\w+_bp)", app_factory_text, re.MULTILINE))
# Exclude commented lines
imported = {bp for bp in imported if not app_factory_text.split(bp)[0].rsplit('\n', 1)[-1].strip().startswith('#')}
registered = set(re.findall(r"register_blueprint\s*\(\s*(\w+_bp)", app_factory_text))
missing_reg = imported - registered
if missing_reg:
    for m in missing_reg:
        report('CRITICAL', f"Blueprint imported but NOT registered: {m}")
else:
    print(f"  All {len(imported)} blueprints registered.")

# Summary
print("\n" + "=" * 70)
print(f" CRITICAL: {len(CRITICALS)}  |  WARNINGS: {len(WARNINGS)}")
print("=" * 70)
if CRITICALS:
    for c in CRITICALS:
        print(f"  - {c}")
else:
    print("  ALL CHECKS PASSED")
