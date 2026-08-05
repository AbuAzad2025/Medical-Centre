"""
Fix missing db imports and remove local app_factory db imports after SQLAlchemy 2.0 migration.
Replaces all local 'from app_factory import db' with a single top-level 'from app.extensions import db'.
"""

import os
import re
import sys


def fix_file(filepath):
    with open(filepath, encoding='utf-8') as f:
        lines = f.readlines()

    content = ''.join(lines)
    # Check for SQLAlchemy 2.0 patterns introduced by migration
    if (
        'db.session.get(' not in content
        and 'db.session.execute(' not in content
        and 'db.session.query(' not in content
    ):
        return

    # If already imports db from app.extensions, skip
    if re.search(r'from\s+app\.extensions\s+import\s+.*\bdb\b', content):
        return

    # Remove all local (indented) 'from app_factory import db' lines
    new_lines = []
    removed = False
    for line in lines:
        if re.match(r'^\s+from app_factory import db\s*$', line):
            removed = True
            continue
        new_lines.append(line)
    lines = new_lines

    # Re-check after removal
    content = ''.join(lines)
    if (
        'db.session.get(' not in content
        and 'db.session.execute(' not in content
        and 'db.session.query(' not in content
    ):
        return

    # Find insertion point: after last top-level import line
    import_idx = 0
    in_docstring = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue
        if line.startswith('import ') or line.startswith('from '):
            import_idx = i + 1

    lines.insert(import_idx, 'from app.extensions import db\n')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f'Fixed {filepath} (removed local app_factory import: {removed})')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        for f in sys.argv[1:]:
            fix_file(f)
    else:
        scan_dirs = ['services', 'routes', 'app', 'models', 'utils', 'tasks', 'scripts']
        for d in scan_dirs:
            for root, _dirs, files in os.walk(d):
                for f in files:
                    if f.endswith('.py'):
                        fix_file(os.path.join(root, f))
