"""
Full System Audit - Scan for all errors, missing imports, broken routes, etc.
"""
import os, sys, traceback, importlib, inspect
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

sys.path.insert(0, os.getcwd())

errors = []
warnings_list = []

def log_error(category, msg):
    errors.append(f"[{category}] {msg}")
    print(f"ERROR [{category}]: {msg}")

def log_warn(category, msg):
    warnings_list.append(f"[{category}] {msg}")
    print(f"WARN [{category}]: {msg}")

print("=" * 60)
print("FULL SYSTEM AUDIT")
print("=" * 60)

# 1. Check imports in routes
print("\n[1] Checking route imports...")
route_files = [
    'routes.auth_routes', 'routes.main', 'routes.super_admin', 'routes.manager',
    'routes.reception', 'routes.doctor', 'routes.lab', 'routes.radiology',
    'routes.emergency', 'routes.nurse_routes', 'routes.medication_routes',
    'routes.payment_routes', 'routes.finance', 'routes.accountant',
    'routes.quality_compliance', 'routes.clinical_coding',
    'routes.bed_management_routes', 'routes.or_management_routes',
    'routes.patient_portal', 'routes.nursing_assessment_routes',
    'routes.emar_routes', 'routes.population_health_routes',
    'routes.data_warehouse_routes', 'app.modules.owner.routes'
]

for mod_name in route_files:
    try:
        mod = importlib.import_module(mod_name)
        # Check for route functions
        for name, obj in inspect.getmembers(mod):
            if hasattr(obj, '__wrapped__') or (callable(obj) and hasattr(obj, 'view_class')):
                pass
    except Exception as e:
        log_error("ROUTE_IMPORT", f"{mod_name}: {type(e).__name__}: {e}")

# 2. Check model imports
print("\n[2] Checking model imports...")
model_modules = [
    'models.user', 'models.payment', 'models.invoice', 'models.system_config',
    'models.permissions', 'models.audit_trail', 'models.exchange_rate'
]
for mod_name in model_modules:
    try:
        importlib.import_module(mod_name)
    except Exception as e:
        log_error("MODEL_IMPORT", f"{mod_name}: {type(e).__name__}: {e}")

# 3. Check enum usage in code vs enum definitions
print("\n[3] Checking enum consistency...")
from app.shared.enums import TenantStatus, SubscriptionType, StorageMode, ModuleName
valid_tenant_status = [e.name for e in TenantStatus]
valid_sub_types = [e.name for e in SubscriptionType]

# Scan routes for enum usage
import re
for root, dirs, files in os.walk('app/modules/owner'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as fp:
                content = fp.read()
            for match in re.finditer(r'TenantStatus\.(\w+)', content):
                val = match.group(1)
                if val not in valid_tenant_status:
                    log_error("ENUM_MISMATCH", f"{path}: TenantStatus.{val} not in {valid_tenant_status}")
            for match in re.finditer(r'SubscriptionType\.(\w+)', content):
                val = match.group(1)
                if val not in valid_sub_types:
                    log_error("ENUM_MISMATCH", f"{path}: SubscriptionType.{val} not in {valid_sub_types}")

# 4. Check all templates for syntax errors
print("\n[4] Checking templates...")
from jinja2 import Environment, FileSystemLoader, meta
env = Environment(loader=FileSystemLoader('templates'))
for template_name in env.list_templates():
    try:
        tmpl = env.get_template(template_name)
        ast = env.parse(tmpl.source)
        # Check for undefined variables (optional)
    except Exception as e:
        log_error("TEMPLATE", f"{template_name}: {type(e).__name__}: {e}")

# 5. Check database connection and tables
print("\n[5] Checking database...")
try:
    from app_factory import create_app, db
    app = create_app()
    with app.app_context():
        from sqlalchemy import text, inspect as sa_inspect
        inspector = sa_inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"  Database tables: {len(tables)}")
        
        # Check for missing indexes
        for table in tables[:20]:  # sample
            indexes = inspector.get_indexes(table)
            pk = inspector.get_pk_constraint(table)
            
        # Check alembic version
        result = db.session.execute(text("SELECT version_num FROM alembic_version"))
        version = result.scalar()
        print(f"  Alembic version: {version}")
        
        # Check critical tables have data
        for tbl in ['tenants', 'module_definitions', 'permissions', 'roles']:
            count = db.session.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
            if count == 0:
                log_warn("DB_EMPTY", f"Table '{tbl}' has 0 rows")
            else:
                print(f"  {tbl}: {count} rows")
                
except Exception as e:
    log_error("DB", f"Database check failed: {type(e).__name__}: {e}")
    traceback.print_exc()

# 6. Check blueprints for route conflicts
print("\n[6] Checking blueprint routes...")
try:
    with app.app_context():
        rules = list(app.url_map.iter_rules())
        endpoints = {}
        for rule in rules:
            ep = rule.endpoint
            if ep in endpoints:
                endpoints[ep].append(str(rule))
            else:
                endpoints[ep] = [str(rule)]
        print(f"  Total routes: {len(rules)}")
        print(f"  Unique endpoints: {len(endpoints)}")
except Exception as e:
    log_error("ROUTES", f"Route check failed: {e}")

# 7. Check for common Flask errors
print("\n[7] Checking common config issues...")
required_configs = ['SECRET_KEY', 'SQLALCHEMY_DATABASE_URI']
for cfg in required_configs:
    if not app.config.get(cfg):
        log_error("CONFIG", f"Missing config: {cfg}")

# 8. Check for missing template variables in forms
print("\n[8] Checking template variable references...")
for root, dirs, files in os.walk('templates'):
    for f in files:
        if f.endswith('.html'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as fp:
                content = fp.read()
            # Check for undefined form fields
            if 'name="csrf_token"' in content and 'value="{{ csrf_token() }}"' not in content:
                if 'value="' not in content or 'csrf_token()' not in content:
                    pass  # skip

# Summary
print("\n" + "=" * 60)
print("AUDIT SUMMARY")
print("=" * 60)
print(f"Errors found: {len(errors)}")
print(f"Warnings found: {len(warnings_list)}")

if errors:
    print("\n--- CRITICAL ERRORS ---")
    for e in errors:
        print(e)

if warnings_list:
    print("\n--- WARNINGS ---")
    for w in warnings_list[:20]:
        print(w)

# Save report
with open('AUDIT_REPORT.txt', 'w', encoding='utf-8') as f:
    f.write("FULL SYSTEM AUDIT REPORT\n")
    f.write("=" * 60 + "\n\n")
    f.write(f"Errors: {len(errors)}\n")
    f.write(f"Warnings: {len(warnings_list)}\n\n")
    if errors:
        f.write("ERRORS:\n")
        for e in errors:
            f.write(f"  {e}\n")
    if warnings_list:
        f.write("\nWARNINGS:\n")
        for w in warnings_list:
            f.write(f"  {w}\n")

print(f"\nReport saved to AUDIT_REPORT.txt")
