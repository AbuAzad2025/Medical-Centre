"""
Smart fix: add 'from app.extensions import db' to test files that use
bare db.session but don't have a standalone db import.
Handles edge cases:
  - Files with 'from app_factory import db as _db' (need separate import)
  - Files with multi-line from-imports (insert after last top-level import)
  - Skip files already correct
"""

import os
import re

ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'tests'
)


def has_standalone_db_import(content):
    """Check if file has 'from app.extensions import db' (not aliased as _db)."""
    # Match 'from app.extensions import db' but not 'from app.extensions import db as _db'
    if re.search(r'^from app\.extensions import db\s*$', content, re.MULTILINE):
        return True
    # Also match 'from app.extensions import db, something' where db is not aliased
    return bool(re.search(r'^from app\.extensions import db\b(?!\s*as\b)', content, re.MULTILINE))


def uses_bare_db_session(content):
    """Check if file uses db.session (not _db.session)."""
    return bool(re.search(r'(?<!_)db\.session', content))


def find_insert_point(lines):
    """Find the line index after the last top-level import block."""
    last_import_end = None
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        # Detect start of an import statement
        if (line.startswith('from ') or line.startswith('import ')) and 'import' in line:
            # Check for multi-line import
            if '(' in line and ')' not in line:
                # Multi-line: find closing paren
                while i < len(lines) and ')' not in lines[i]:
                    i += 1
            last_import_end = i + 1
        i += 1
    return last_import_end


def fix_file(filepath):
    try:
        with open(filepath, encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        return False

    if not uses_bare_db_session(content):
        return False

    if has_standalone_db_import(content):
        return False

    lines = content.split('\n')
    insert_idx = find_insert_point(lines)
    if insert_idx is None:
        return False

    import_line = 'from app.extensions import db'
    lines.insert(insert_idx, import_line)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return True


def main():
    fixed = 0
    for dp, _, fns in os.walk(ROOT):
        for f in fns:
            if not f.endswith('.py'):
                continue
            filepath = os.path.join(dp, f)
            if fix_file(filepath):
                fixed += 1
                rel = os.path.relpath(filepath, ROOT)
                print(f'  Fixed: {rel}')
    print(f'\nTotal: {fixed} files fixed')


if __name__ == '__main__':
    main()
