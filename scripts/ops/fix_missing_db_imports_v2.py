"""Fix missing `db` imports in files touched by the SQLAlchemy 2.0 migration.
Uses `from app.extensions import db` which is safe for all files (leaf module)."""

import os
import re
import sys


def fix_file(filepath):
    with open(filepath, encoding='utf-8') as f:
        lines = f.readlines()

    content = ''.join(lines)
    # If already imports db from app.extensions or app_factory, skip
    if re.search(r'from\s+app\.extensions\s+import\s+.*\bdb\b', content):
        return
    if re.search(r'from\s+app_factory\s+import\s+.*\bdb\b', content):
        return
    if re.search(r'^import\s+db\b', content, flags=re.MULTILINE):
        return

    # Check for SQLAlchemy 2.0 patterns introduced by migration
    if (
        'db.session.get(' in content
        or 'db.session.execute(' in content
        or 'db.session.query(' in content
    ):
        # Find insertion point: after last import line
        import_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                import_idx = i + 1

        # Insert 'from app.extensions import db'
        lines.insert(import_idx, 'from app.extensions import db\n')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f'Fixed {filepath}')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        for f in sys.argv[1:]:
            fix_file(f)
    else:
        scan_dirs = ['services', 'routes', 'app', 'models', 'utils']
        for d in scan_dirs:
            for root, dirs, files in os.walk(d):
                for f in files:
                    if f.endswith('.py'):
                        fix_file(os.path.join(root, f))
