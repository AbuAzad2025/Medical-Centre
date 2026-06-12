"""
فحص شامل للتطابق بين SQLAlchemy Models وقاعدة البيانات
Database Schema Audit — compares Python models vs actual DB tables
"""
import os
import sys
import inspect
import re
import argparse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_all_models():
    """Extract all SQLAlchemy model classes from models/ directory."""
    models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
    model_classes = []
    seen = set()

    if not os.path.isdir(models_dir):
        print(f"[WARN] models directory not found: {models_dir}")
        return []

    # Import app to get db
    from app_factory import create_app, db
    app = create_app(os.getenv('FLASK_ENV', 'testing'))

    with app.app_context():
        # Import models/__init__.py to trigger all imports
        try:
            import models
        except Exception as e:
            print(f"[WARN] Could not import models package: {e}")

        # Helper to scan a directory for model files
        def _scan_dir(scan_dir, package_name):
            if not os.path.isdir(scan_dir):
                return
            for root, dirs, files in os.walk(scan_dir):
                for filename in files:
                    if not filename.endswith('.py') or filename.startswith('__'):
                        continue
                    rel_path = os.path.relpath(root, scan_dir).replace(os.sep, '.')
                    if rel_path == '.':
                        rel_path = ''
                    module_name = f"{package_name}.{rel_path}.{filename[:-3]}" if rel_path else f"{package_name}.{filename[:-3]}"
                    module_name = module_name.replace('..', '.').strip('.')
                    try:
                        module = __import__(module_name, fromlist=['*'])
                        for name, obj in inspect.getmembers(module):
                            if (inspect.isclass(obj) and
                                hasattr(obj, '__tablename__') and
                                hasattr(obj, '__table__') and
                                obj.__name__ not in seen):
                                seen.add(obj.__name__)
                                model_classes.append(obj)
                    except Exception:
                        pass

        # Walk traditional models/
        for filename in os.listdir(models_dir):
            if not filename.endswith('.py') or filename.startswith('__'):
                continue
            module_name = f"models.{filename[:-3]}"
            try:
                module = __import__(module_name, fromlist=['*'])
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and
                        hasattr(obj, '__tablename__') and
                        hasattr(obj, '__table__') and
                        obj.__name__ not in seen):
                        seen.add(obj.__name__)
                        model_classes.append(obj)
            except Exception as e:
                print(f"[WARN] Failed to import {module_name}: {e}")

        # Walk app/core/, app/modules/, app/integrations/
        base_dir = os.path.dirname(os.path.dirname(__file__))
        _scan_dir(os.path.join(base_dir, 'app', 'core'), 'app.core')
        _scan_dir(os.path.join(base_dir, 'app', 'modules'), 'app.modules')
        _scan_dir(os.path.join(base_dir, 'app', 'integrations'), 'app.integrations')

    return model_classes


def extract_model_schema(model_class):
    """Extract columns, types, constraints from a SQLAlchemy model."""
    table = model_class.__table__
    columns = {}
    for col in table.columns:
        col_info = {
            'name': col.name,
            'type': str(col.type),
            'nullable': col.nullable,
            'default': str(col.default.arg) if col.default else None,
            'primary_key': col.primary_key,
            'foreign_keys': [str(fk) for fk in col.foreign_keys],
        }
        columns[col.name] = col_info

    constraints = []
    for cons in table.constraints:
        if hasattr(cons, 'name'):
            constraints.append({
                'name': cons.name,
                'type': type(cons).__name__,
                'sql': str(cons)
            })

    indexes = []
    for idx in table.indexes:
        indexes.append({
            'name': idx.name,
            'columns': [c.name for c in idx.columns],
            'unique': idx.unique
        })

    return {
        'table_name': table.name,
        'columns': columns,
        'constraints': constraints,
        'indexes': indexes
    }


def get_db_schema(engine):
    """Extract schema from actual database using SQLAlchemy inspection."""
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(engine)
    schema = {}

    for table_name in inspector.get_table_names():
        columns = {}
        for col in inspector.get_columns(table_name):
            columns[col['name']] = {
                'name': col['name'],
                'type': str(col['type']),
                'nullable': col.get('nullable', True),
                'default': str(col.get('default')) if col.get('default') else None,
            }

        pks = inspector.get_pk_constraint(table_name)
        for pk_col in pks.get('constrained_columns', []):
            if pk_col in columns:
                columns[pk_col]['primary_key'] = True

        fks = inspector.get_foreign_keys(table_name)
        for fk in fks:
            for col_name in fk.get('constrained_columns', []):
                if col_name in columns:
                    columns[col_name].setdefault('foreign_keys', []).append(
                        f"{fk.get('referred_table')}.{fk.get('referred_columns', [])[0]}"
                    )

        constraints = []
        try:
            for check in inspector.get_check_constraints(table_name):
                constraints.append({
                    'name': check.get('name'),
                    'type': 'CheckConstraint',
                    'sql': check.get('sqltext', '')
                })
        except Exception:
            pass

        indexes = []
        try:
            for idx in inspector.get_indexes(table_name):
                indexes.append({
                    'name': idx['name'],
                    'columns': idx['column_names'],
                    'unique': idx['unique']
                })
        except Exception:
            pass

        schema[table_name] = {
            'table_name': table_name,
            'columns': columns,
            'constraints': constraints,
            'indexes': indexes
        }

    return schema


def get_migration_schema():
    """Extract table definitions from Alembic migration files."""
    migrations_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'migrations', 'versions'
    )
    tables = defaultdict(lambda: {'columns': {}, 'constraints': []})

    if not os.path.isdir(migrations_dir):
        return {}

    for filename in sorted(os.listdir(migrations_dir)):
        if not filename.endswith('.py') or filename.startswith('__'):
            continue
        filepath = os.path.join(migrations_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract op.create_table blocks (simplified regex)
        create_table_pattern = r"op\.create_table\(\s*'([^']+)'\s*,(.*?)\)"
        for match in re.finditer(create_table_pattern, content, re.DOTALL):
            table_name = match.group(1)
            block = match.group(2)

            # Extract columns
            col_pattern = r"sa\.Column\('([^']+)'\s*,\s*([^,\)]+)"
            for col_match in re.finditer(col_pattern, block):
                col_name = col_match.group(1)
                col_type = col_match.group(2).strip()
                tables[table_name]['columns'][col_name] = {
                    'name': col_name,
                    'type': col_type,
                }

            # Extract constraints
            fk_pattern = r"sa\.ForeignKeyConstraint\(\[([^\]]+)\]\s*,\s*\[([^\]]+)\]\s*\)"
            for fk_match in re.finditer(fk_pattern, block):
                tables[table_name]['constraints'].append({
                    'type': 'ForeignKeyConstraint',
                    'local': fk_match.group(1),
                    'remote': fk_match.group(2)
                })

    return dict(tables)


def compare_schemas(models_schema, db_schema):
    """Compare model schema vs actual DB schema."""
    issues = []

    model_tables = set(models_schema.keys())
    db_tables = set(db_schema.keys())

    # Tables in models but not in DB
    missing_in_db = model_tables - db_tables
    if missing_in_db:
        issues.append({
            'severity': 'ERROR',
            'type': 'TABLE_MISSING_IN_DB',
            'message': f"Tables defined in models but missing in DB: {sorted(missing_in_db)}"
        })

    # Tables in DB but not in models (legacy or manual)
    extra_in_db = db_tables - model_tables
    if extra_in_db:
        issues.append({
            'severity': 'WARN',
            'type': 'TABLE_MISSING_IN_MODELS',
            'message': f"Tables in DB but not found in models (might be legacy): {sorted(extra_in_db)}"
        })

    # Compare columns for existing tables
    for table in model_tables & db_tables:
        model_cols = set(models_schema[table]['columns'].keys())
        db_cols = set(db_schema[table]['columns'].keys())

        missing_cols = model_cols - db_cols
        if missing_cols:
            issues.append({
                'severity': 'ERROR',
                'type': 'COLUMN_MISSING_IN_DB',
                'table': table,
                'message': f"Columns missing in DB: {sorted(missing_cols)}"
            })

        extra_cols = db_cols - model_cols
        if extra_cols:
            issues.append({
                'severity': 'WARN',
                'type': 'COLUMN_MISSING_IN_MODELS',
                'table': table,
                'message': f"Extra columns in DB: {sorted(extra_cols)}"
            })

        # Compare types for matching columns
        for col in model_cols & db_cols:
            model_type = models_schema[table]['columns'][col].get('type', '')
            db_type = db_schema[table]['columns'][col].get('type', '')
            # Normalize types for comparison
            model_norm = model_type.lower().replace('varchar', 'varchar').replace('integer', 'integer')
            db_norm = db_type.lower().replace('varchar', 'varchar').replace('integer', 'integer')
            if model_norm != db_norm:
                issues.append({
                    'severity': 'WARN',
                    'type': 'TYPE_MISMATCH',
                    'table': table,
                    'column': col,
                    'message': f"Type mismatch: model={model_type}, db={db_type}"
                })

    return issues


def main():
    parser = argparse.ArgumentParser(description="Database Schema Audit")
    parser.add_argument('--db-url', help='Database URL (overrides env)')
    parser.add_argument('--strict', action='store_true', help='Exit non-zero on any ERROR')
    args = parser.parse_args()

    # Setup
    if args.db_url:
        os.environ['DATABASE_URL'] = args.db_url

    from app_factory import create_app, db
    app = create_app(os.getenv('FLASK_ENV', 'testing'))

    print("=" * 60)
    print("Azad Medical Platform — Database Schema Audit")
    print("=" * 60)

    # 1. Extract model schema
    print("\n[1/4] Scanning SQLAlchemy models...")
    model_classes = get_all_models()
    print(f"      Found {len(model_classes)} model classes")

    models_schema = {}
    for cls in model_classes:
        try:
            schema = extract_model_schema(cls)
            models_schema[schema['table_name']] = schema
        except Exception as e:
            print(f"      [WARN] Failed to inspect {cls.__name__}: {e}")

    # 2. Extract DB schema
    print("\n[2/4] Scanning actual database...")
    with app.app_context():
        db_schema = get_db_schema(db.engine)
    print(f"      Found {len(db_schema)} tables in DB")

    # 3. Extract migration schema
    print("\n[3/4] Scanning Alembic migrations...")
    migration_schema = get_migration_schema()
    print(f"      Found {len(migration_schema)} tables in migrations")

    # 4. Compare
    print("\n[4/4] Comparing models vs database...")
    issues = compare_schemas(models_schema, db_schema)

    errors = [i for i in issues if i['severity'] == 'ERROR']
    warnings = [i for i in issues if i['severity'] == 'WARN']

    print(f"\n{'=' * 60}")
    print(f"Results: {len(errors)} ERRORS, {len(warnings)} WARNINGS")
    print(f"{'=' * 60}")

    if errors:
        print("\n🔴 ERRORS:")
        for issue in errors:
            print(f"   [{issue['type']}] {issue['message']}")
            if 'table' in issue:
                print(f"   Table: {issue['table']}")
            if 'column' in issue:
                print(f"   Column: {issue['column']}")

    if warnings:
        print("\n🟡 WARNINGS:")
        for issue in warnings:
            print(f"   [{issue['type']}] {issue['message']}")

    if not errors and not warnings:
        print("\n✅ Models and database are perfectly aligned!")

    # Summary table
    print(f"\n{'=' * 60}")
    print("Summary Table:")
    print(f"  Models tables:    {len(models_schema)}")
    print(f"  DB tables:        {len(db_schema)}")
    print(f"  Migration tables: {len(migration_schema)}")
    print(f"{'=' * 60}")

    if args.strict and errors:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
