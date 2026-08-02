"""
Automated SA 2.0 migration for legacy Model.query patterns.
Handles common simple patterns; outputs remaining for manual review.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def migrate_file(filepath):
    try:
        with open(filepath, encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        return 0, []

    original = content
    change_types = set()
    needs_select = False
    needs_func = False

    # 1. Model.query.get(arg) → db.session.get(Model, arg)
    new = re.sub(
        r'(\w+)\.query\.get\(([^)]+)\)',
        lambda m: f'db.session.get({m.group(1)}, {m.group(2)})',
        content,
    )
    if new != content:
        change_types.add('get')
        content = new

    # 2. Model.query.filter_by(x).all() → db.session.execute(select(Model).filter_by(x)).scalars().all()
    new = re.sub(
        r'(\w+)\.query\.filter_by\((.+?)\)\.all\(\)',
        lambda m: (
            f'db.session.execute(select({m.group(1)}).filter_by({m.group(2)})).scalars().all()'
        ),
        content,
    )
    if new != content:
        change_types.add('filter_by.all')
        content = new

    # 3. Model.query.filter_by(x).first()
    new = re.sub(
        r'(\w+)\.query\.filter_by\((.+?)\)\.first\(\)',
        lambda m: (
            f'db.session.execute(select({m.group(1)}).filter_by({m.group(2)})).scalars().first()'
        ),
        content,
    )
    if new != content:
        change_types.add('filter_by.first')
        content = new

    # 4. Model.query.filter_by(x).count() — needs func
    def replace_fb_count(m):
        nonlocal needs_func
        needs_func = True
        return f'db.session.execute(select(func.count()).select_from({m.group(1)}).filter_by({m.group(2)})).scalar()'

    new = re.sub(r'(\w+)\.query\.filter_by\((.+?)\)\.count\(\)', replace_fb_count, content)
    if new != content:
        change_types.add('filter_by.count')
        content = new

    # 5. Model.query.filter_by(x).one()
    new = re.sub(
        r'(\w+)\.query\.filter_by\((.+?)\)\.one\(\)',
        lambda m: (
            f'db.session.execute(select({m.group(1)}).filter_by({m.group(2)})).scalars().one()'
        ),
        content,
    )
    if new != content:
        change_types.add('filter_by.one')
        content = new

    # 6. Model.query.filter_by(x).one_or_none()
    new = re.sub(
        r'(\w+)\.query\.filter_by\((.+?)\)\.one_or_none\(\)',
        lambda m: (
            f'db.session.execute(select({m.group(1)}).filter_by({m.group(2)})).scalars().one_or_none()'
        ),
        content,
    )
    if new != content:
        change_types.add('filter_by.one_or_none')
        content = new

    # 7. Model.query.all()
    new = re.sub(
        r'(\w+)\.query\.all\(\)',
        lambda m: f'db.session.execute(select({m.group(1)})).scalars().all()',
        content,
    )
    if new != content:
        change_types.add('query.all')
        content = new

    # 8. Model.query.first()
    new = re.sub(
        r'(\w+)\.query\.first\(\)',
        lambda m: f'db.session.execute(select({m.group(1)})).scalars().first()',
        content,
    )
    if new != content:
        change_types.add('query.first')
        content = new

    # 9. Model.query.count() — needs func
    def replace_query_count(m):
        nonlocal needs_func
        needs_func = True
        return f'db.session.execute(select(func.count()).select_from({m.group(1)})).scalar()'

    new = re.sub(r'(\w+)\.query\.count\(\)', replace_query_count, content)
    if new != content:
        change_types.add('query.count')
        content = new

    # 10. db.session.query(Model) → select(Model)
    new = re.sub(r'db\.session\.query\((\w+)\)', lambda m: f'select({m.group(1)})', content)
    if new != content:
        change_types.add('session.query')
        content = new

    if content != original:
        needs_select = (
            bool(re.search(r'\bselect\(', content))
            and 'from sqlalchemy import' not in content.split('select(')[0].split('\n')[-1]
        )

        # Add imports
        lines = content.split('\n')
        import_inserted = False

        # Find existing sqlalchemy import
        sa_import_idx = None
        for i, line in enumerate(lines):
            if re.match(r'^from sqlalchemy import ', line):
                sa_import_idx = i
                break

        if sa_import_idx is not None:
            existing = lines[sa_import_idx]
            if 'select' not in existing and needs_select:
                lines[sa_import_idx] = existing.rstrip() + ', select'
            if needs_func and 'func' not in lines[sa_import_idx]:
                lines[sa_import_idx] = lines[sa_import_idx].rstrip() + ', func'
        else:
            # Need to add new import
            imports_to_add = []
            if needs_select:
                imports_to_add.append('select')
            if needs_func:
                imports_to_add.append('func')
            if imports_to_add:
                import_line = f'from sqlalchemy import {", ".join(imports_to_add)}'
                # Find last import line
                last_import = 0
                for i, line in enumerate(lines):
                    if line.startswith('import ') or line.startswith('from '):
                        last_import = i
                lines.insert(last_import + 1, import_line)

        content = '\n'.join(lines)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    return len(change_types), list(change_types)


def main():
    total_files = 0
    total_changes = 0

    dirs_to_scan = [
        os.path.join(ROOT, 'tests'),
        os.path.join(ROOT, 'seeds'),
    ]

    for scan_dir in dirs_to_scan:
        if not os.path.exists(scan_dir):
            continue
        for dirpath, dirnames, filenames in os.walk(scan_dir):
            dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '__pycache__']
            for fname in filenames:
                if not fname.endswith('.py'):
                    continue
                filepath = os.path.join(dirpath, fname)
                count, changes = migrate_file(filepath)
                if count > 0:
                    total_files += 1
                    total_changes += count
                    rel = os.path.relpath(filepath, ROOT)
                    print(f'  {rel}: {", ".join(changes)}')

    print(f'\nTotal: {total_changes} pattern types migrated across {total_files} files')


if __name__ == '__main__':
    main()
