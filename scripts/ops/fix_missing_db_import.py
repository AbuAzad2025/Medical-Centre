"""
Fix missing 'db' imports in files that use db.session but don't import it.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fix_file(filepath):
    try:
        with open(filepath, encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        return False

    if 'db.session' not in content:
        return False

    # Check if db is already imported
    has_db_import = bool(
        re.search(r'from app\.extensions import.*\bdb\b', content)
        or re.search(r'from app_factory import.*\bdb\b', content)
        or re.search(r'from extensions import.*\bdb\b', content)
    )

    if has_db_import:
        return False

    lines = content.split('\n')
    insert_idx = None
    for i, line in enumerate(lines):
        if line.startswith('from ') and 'import' in line:
            insert_idx = i + 1

    if insert_idx is None:
        for i, line in enumerate(lines):
            if line.startswith('import '):
                insert_idx = i + 1

    if insert_idx is None:
        return False

    # Try to import from app.extensions first, fall back to app_factory
    if 'from app_factory import' in content:
        import_line = 'from app_factory import db'
    else:
        import_line = 'from app.extensions import db'

    lines.insert(insert_idx, import_line)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return True


def main():
    fixed = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [
            d
            for d in dirnames
            if not d.startswith('.')
            and d not in ('__pycache__', 'node_modules', '.pytest_cache', 'scripts')
        ]
        for fname in filenames:
            if not fname.endswith('.py'):
                continue
            filepath = os.path.join(dirpath, fname)
            if fix_file(filepath):
                fixed += 1
                rel = os.path.relpath(filepath, ROOT)
                print(f'  Fixed: {rel}')
    print(f'\nTotal: {fixed} files fixed')


if __name__ == '__main__':
    main()
