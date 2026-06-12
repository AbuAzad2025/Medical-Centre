"""
الفحص الشامل — الاستيرادات، المفاتيح الأجنبية، العلاقات، الشمولية
Comprehensive Audit: Imports, FKs, Relationships, Completeness
"""
import os
import sys
import ast
import importlib
import traceback
import subprocess
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RED = '\033[91m'
YELLOW = '\033[93m'
GREEN = '\033[92m'
RESET = '\033[0m'

ERRORS = []
WARNINGS = []
INFOS = []


def log_error(msg):
    ERRORS.append(msg)
    print(f"{RED}[ERROR]{RESET} {msg}")


def log_warn(msg):
    WARNINGS.append(msg)
    print(f"{YELLOW}[WARN]{RESET} {msg}")


def log_info(msg):
    INFOS.append(msg)
    print(f"{GREEN}[INFO]{RESET} {msg}")


# ============================================================
# 1. استيرادات بايثون — Static Import Analysis
# ============================================================

def analyze_imports():
    """Scan all .py files for broken local imports."""
    print("\n" + "=" * 70)
    print("[1/5] فحص الاستيرادات Python")
    print("=" * 70)

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    py_files = []
    for root, dirs, files in os.walk(base):
        # Skip venv, node_modules, __pycache__
        dirs[:] = [d for d in dirs if d not in ('venv', '.venv', 'node_modules', '__pycache__', '.git', '.pytest_cache', 'migrations')]
        for f in files:
            if f.endswith('.py'):
                py_files.append(os.path.join(root, f))

    broken = []
    import_cycles = defaultdict(list)

    for filepath in py_files:
        rel = os.path.relpath(filepath, base)
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as fh:
                source = fh.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module
                    if not module:
                        continue
                    # Only check local project imports
                    if module.startswith(('models.', 'routes.', 'app.', 'utils.', 'scripts.')):
                        full_module = module.replace('.', os.sep)
                        possible = [
                            os.path.join(base, full_module + '.py'),
                            os.path.join(base, full_module, '__init__.py'),
                        ]
                        if not any(os.path.exists(p) for p in possible):
                            broken.append(f"{rel}: from {module} import ...")
        except SyntaxError:
            broken.append(f"{rel}: Syntax error in file")
        except Exception as e:
            broken.append(f"{rel}: Parse error ({e})")

    if broken:
        for b in broken[:20]:
            log_warn(f"Import issue: {b}")
        if len(broken) > 20:
            log_warn(f"... and {len(broken) - 20} more import issues")
    else:
        log_info("All local imports appear valid (static check)")

    return broken


# ============================================================
# 2. Foreign Keys & Relationships Runtime Check
# ============================================================

def check_fks_and_relationships():
    """Verify all FKs point to real tables/columns and relationships are valid."""
    print("\n" + "=" * 70)
    print("[2/5] فحص Foreign Keys و Relationships")
    print("=" * 70)

    from app_factory import create_app, db
    app = create_app(os.getenv('FLASK_ENV', 'testing'))

    with app.app_context():
        from sqlalchemy import inspect as sa_inspect, MetaData
        inspector = sa_inspect(db.engine)
        db_tables = {t for t in inspector.get_table_names()}

        # Get all mapped tables from SQLAlchemy
        all_tables = set(db.metadata.tables.keys())
        log_info(f"SQLAlchemy mapped tables: {len(all_tables)}")

        fk_issues = []
        rel_issues = []

        # Check each table in metadata
        for table_name, table in db.metadata.tables.items():
            # Check FKs
            for fk in table.foreign_keys:
                target_table = fk.column.table.name if hasattr(fk.column, 'table') else str(fk.column)
                target_col = fk.column.name if hasattr(fk.column, 'name') else str(fk.column)
                if target_table not in db_tables:
                    fk_issues.append(f"FK from {table_name}.{fk.parent.name} -> {target_table}.{target_col} (table missing)")
                else:
                    # Check column exists in target
                    try:
                        cols = {c['name'] for c in inspector.get_columns(target_table)}
                        if target_col not in cols:
                            fk_issues.append(f"FK from {table_name}.{fk.parent.name} -> {target_table}.{target_col} (column missing)")
                    except Exception as e:
                        fk_issues.append(f"FK check failed for {target_table}: {e}")

        # Check relationships by trying to resolve backrefs
        for mapper in db.Model.registry.mappers:
            cls = mapper.class_
            for prop in mapper.relationships:
                try:
                    target = prop.mapper.class_
                    if not hasattr(target, '__tablename__'):
                        rel_issues.append(f"{cls.__name__}.{prop.key} -> target {target} has no __tablename__")
                except Exception as e:
                    rel_issues.append(f"{cls.__name__}.{prop.key}: {e}")

        for issue in fk_issues:
            log_error(issue)
        for issue in rel_issues:
            log_warn(issue)

        if not fk_issues:
            log_info("All Foreign Keys point to valid tables/columns")
        if not rel_issues:
            log_info("All ORM relationships resolved successfully")

        return fk_issues, rel_issues


# ============================================================
# 3. Model Registration Completeness
# ============================================================

def check_model_registration():
    """Ensure every model file is imported in models/__init__.py"""
    print("\n" + "=" * 70)
    print("[3/5] فحص شمولية تسجيل النماذج")
    print("=" * 70)

    models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
    init_file = os.path.join(models_dir, '__init__.py')

    with open(init_file, 'r', encoding='utf-8') as f:
        init_content = f.read()

    # Files that are documentation/helpers, not real DB models
    NON_MODEL_HELPERS = {'relationships_map', 'unified_mixins'}

    model_files = [f for f in os.listdir(models_dir) if f.endswith('.py') and not f.startswith('__')]
    missing_imports = []

    for mf in model_files:
        module_name = mf[:-3]
        if module_name in NON_MODEL_HELPERS:
            continue
        # Check if imported in __init__.py
        patterns = [
            f'from .{module_name} import',
            f'import .{module_name}',
            f'from models.{module_name}',
        ]
        if not any(p in init_content for p in patterns):
            # Also check if any class from this file is in __all__
            missing_imports.append(module_name)

    if missing_imports:
        for m in missing_imports:
            log_warn(f"Model file '{m}.py' not imported in models/__init__.py")
    else:
        log_info("All model files are imported in models/__init__.py")

    # Check for app/core and app/modules models being registered in app_factory
    from app_factory import create_app, db
    app = create_app(os.getenv('FLASK_ENV', 'testing'))
    with app.app_context():
        core_models = []
        try:
            from app.core.tenant.models import Tenant, SubscriptionPlan, TenantSubscriptionHistory
            from app.core.module.models import ModuleDefinition, TenantModule
            from app.modules.workflows.stock_models import StockMovement
            core_models = ['Tenant', 'SubscriptionPlan', 'TenantSubscriptionHistory',
                           'ModuleDefinition', 'TenantModule', 'StockMovement']
        except Exception as e:
            log_error(f"Failed to import core models: {e}")

        for cm in core_models:
            log_info(f"Core model registered: {cm}")

    return missing_imports


# ============================================================
# 4. Blueprint Route Binding Check
# ============================================================

def check_blueprint_routes():
    """Ensure all blueprints register routes and no duplicate URLs."""
    print("\n" + "=" * 70)
    print("[4/5] فحص تسجيل Blueprint Routes")
    print("=" * 70)

    from app_factory import create_app
    app = create_app(os.getenv('FLASK_ENV', 'testing'))

    urls = defaultdict(list)
    for rule in app.url_map.iter_rules():
        if rule.endpoint != 'static':
            urls[rule.rule].append((rule.endpoint, rule.methods - {'OPTIONS', 'HEAD'}))

    # Only flag duplicates if methods overlap (GET+GET on same path = real conflict)
    real_conflicts = {}
    restful_pairs = {}
    for url, endpoints in urls.items():
        if len(endpoints) <= 1:
            continue
        # Check for method overlap
        all_methods = []
        for ep, methods in endpoints:
            all_methods.extend(methods)
        has_overlap = len(all_methods) > len(set(all_methods))
        if has_overlap:
            real_conflicts[url] = [ep for ep, _ in endpoints]
        else:
            restful_pairs[url] = [ep for ep, _ in endpoints]

    if restful_pairs:
        log_info(f"RESTful routes (same URL, different methods — OK): {len(restful_pairs)}")
        for url, endpoints in restful_pairs.items():
            log_info(f"  {url} -> {endpoints}")
    if real_conflicts:
        for url, endpoints in real_conflicts.items():
            log_warn(f"Real duplicate URL '{url}' registered by: {endpoints}")
    else:
        log_info("No real duplicate URL conflicts found")

    log_info(f"Total routes registered: {len(urls)}")
    return real_conflicts


# ============================================================
# 5. Circular Import Detection
# ============================================================

def check_circular_imports():
    """Detect circular import dependencies."""
    print("\n" + "=" * 70)
    print("[5/5] فحص الاستيرادات الدائرية")
    print("=" * 70)

    # Use modulegraph or a simple DFS
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    graph = defaultdict(set)

    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ('venv', '.venv', 'node_modules', '__pycache__', '.git', 'migrations')]
        for f in files:
            if not f.endswith('.py'):
                continue
            filepath = os.path.join(root, f)
            rel = os.path.relpath(filepath, base).replace(os.sep, '.')[:-3]
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as fh:
                    source = fh.read()
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        mod = node.module
                        if mod.startswith(('models.', 'routes.', 'app.', 'utils.')):
                            graph[rel].add(mod)
            except SyntaxError:
                pass

    # DFS for cycles
    cycles = []
    visited = set()
    rec_stack = set()

    def dfs(node, path):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                if dfs(neighbor, path + [neighbor]):
                    return True
            elif neighbor in rec_stack:
                cycle_start = path.index(neighbor) if neighbor in path else 0
                cycles.append(path[cycle_start:] + [neighbor])
                return True
        rec_stack.remove(node)
        return False

    for node in list(graph.keys()):
        if node not in visited:
            dfs(node, [node])

    if cycles:
        for c in cycles[:5]:
            log_warn(f"Circular import detected: {' -> '.join(c)}")
        if len(cycles) > 5:
            log_warn(f"... and {len(cycles) - 5} more cycles")
    else:
        log_info("No circular imports detected")

    return cycles


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 70)
    print("الفحص الشامل — Azad Medical Platform v3.0")
    print("Comprehensive Audit: Imports, FKs, Relationships, Completeness")
    print("=" * 70)

    analyze_imports()
    check_fks_and_relationships()
    check_model_registration()
    check_blueprint_routes()
    check_circular_imports()

    print("\n" + "=" * 70)
    print("الملخص النهائي")
    print("=" * 70)
    total_errors = len(ERRORS)
    total_warns = len(WARNINGS)
    print(f"  {RED}{total_errors} خطأ{RESET}")
    print(f"  {YELLOW}{total_warns} تحذير{RESET}")
    print(f"  {GREEN}{len(INFOS)} معلومة{RESET}")

    if total_errors == 0 and total_warns == 0:
        print(f"\n{GREEN}✅ النظام متكامل تماماً — لا يوجد أي مشاكل{RESET}")
    elif total_errors == 0:
        print(f"\n{YELLOW}⚠️ النظام يعمل لكن يوجد تحذيرات غير حرجة{RESET}")
    else:
        print(f"\n{RED}🔴 يوجد أخطاء حرجة يجب إصلاحها{RESET}")

    sys.exit(1 if total_errors > 0 else 0)


if __name__ == '__main__':
    main()
