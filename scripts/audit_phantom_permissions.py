"""
Phantom permission auditor — finds has_permission('X') calls in templates
that reference permissions not registered in create_default_permissions().
Also checks permissions referenced in Python code (decorators, service calls).
"""

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))


def get_registered_permissions():
    """Extract permission names from create_default_permissions()."""
    from app_factory import create_app
    from app.extensions import db

    app = create_app('testing')
    with app.app_context():
        from sqlalchemy import text

        rows = db.session.execute(
            text('SELECT name FROM permissions WHERE is_active = true')
        ).fetchall()
        return {r[0] for r in rows}


def get_template_permissions(templates_dir):
    """Extract has_permission('X') from all template files."""
    perms = {}
    tpl_path = Path(templates_dir)
    for f in tpl_path.rglob('*.html'):
        content = f.read_text(encoding='utf-8', errors='replace')
        rel = str(f.relative_to(tpl_path))
        for m in re.finditer(r"has_permission\(['\"]([^'\"]+)['\"]\)", content):
            perm = m.group(1)
            if perm not in perms:
                perms[perm] = []
            if rel not in perms[perm]:
                perms[perm].append(rel)
    return perms


def get_python_permissions(routes_dir, services_dir):
    """Extract permission names from decorators/service calls."""
    perms = {}
    for d in [routes_dir, services_dir]:
        for f in Path(d).rglob('*.py'):
            content = f.read_text(encoding='utf-8', errors='replace')
            rel = str(f.relative_to(Path(d).parent))
            for m in re.finditer(r"has_permission\(['\"]([^'\"]+)['\"]\)", content):
                perm = m.group(1)
                if perm not in perms:
                    perms[perm] = []
                if rel not in perms[perm]:
                    perms[perm].append(rel)
            for m in re.finditer(r'@role_required\(([^)]+)\)', content):
                # These are role-based, not permission-based — skip
                pass
    return perms


def main():
    root = Path(__file__).parent.parent
    registered = get_registered_permissions()
    tpl_perms = get_template_permissions(root / 'templates')
    py_perms = get_python_permissions(root / 'routes', root / 'services')

    all_used = set(tpl_perms.keys()) | set(py_perms.keys())
    phantoms = sorted(all_used - registered)

    print(f'Registered permissions: {len(registered)}')
    print(f'Permissions used in templates: {len(tpl_perms)}')
    print(f'Permissions used in Python: {len(py_perms)}')
    print(f'Unique used: {len(all_used)}')
    print()

    if phantoms:
        print(f'PHANTOM PERMISSIONS ({len(phantoms)} found):')
        print('=' * 60)
        for p in phantoms:
            files = tpl_perms.get(p, []) + py_perms.get(p, [])
            print(f'  "{p}"')
            for f in files[:5]:
                print(f'    -> {f}')
            if len(files) > 5:
                print(f'    ... and {len(files) - 5} more')
        print()
        print('FIX: Register these in create_default_permissions()')
        return 1
    else:
        print('NO phantom permissions detected!')
        return 0


if __name__ == '__main__':
    import os

    os.environ.setdefault('SECRET_KEY', 'audit-only')
    os.environ['APP_ENV'] = 'testing'
    raise SystemExit(main())
