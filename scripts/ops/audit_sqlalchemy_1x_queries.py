"""
SQLAlchemy 1.x Query Audit Script
Scans the codebase for legacy Model.query / session.query() patterns
and reports them for systematic refactoring to SQLAlchemy 2.0+ explicit syntax.
"""

import os
import re
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows to avoid UnicodeEncodeError
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Directories to scan (relative to project root)
SCAN_DIRS = [
    'models',
    'routes',
    'services',
    'app',
    'utils',
]

# Patterns that indicate legacy SQLAlchemy 1.x usage
LEGACY_PATTERNS = [
    # Model.query.filter(...)
    (r'\b\w+\.query\.', 'Model.query.XYZ'),
    # db.session.query(Model)
    (r'\bsession\.query\(', 'session.query(...)'),
    # db.session.query(Model)
    (r'\.query\(\w+\)', '.query(Model)'),
]

# Safe/allowed patterns (ORM event listeners, type hints, etc.)
ALLOWED_PATTERNS = [
    r'__table__\.columns',  # metadata introspection
    r'\.query\.get\(',  # some get() calls are acceptable in 2.0 compat mode
    r'inspector\.get_',  # reflection API
    r'text\(',  # raw text()
]


def _is_allowed_line(line: str) -> bool:
    for pat in ALLOWED_PATTERNS:
        if re.search(pat, line):
            return True
    return False


def scan_file(filepath: Path) -> list[dict]:
    """Scan a single Python file for legacy query patterns."""
    findings = []
    try:
        with open(filepath, encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return findings

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if _is_allowed_line(line):
            continue
        for pattern, label in LEGACY_PATTERNS:
            if re.search(pattern, line):
                findings.append(
                    {
                        'file': str(filepath),
                        'line': lineno,
                        'code': stripped,
                        'pattern': label,
                    }
                )
                break  # Only report first match per line
    return findings


def main() -> int:
    root = Path(__file__).resolve().parent.parent.parent
    all_findings: list[dict] = []

    for subdir in SCAN_DIRS:
        target = root / subdir
        if not target.exists():
            continue
        for pyfile in target.rglob('*.py'):
            if pyfile.name.startswith('test_'):
                continue  # Skip test files
            findings = scan_file(pyfile)
            all_findings.extend(findings)

    # Group by file
    by_file: dict[str, list[dict]] = {}
    for f in all_findings:
        by_file.setdefault(f['file'], []).append(f)

    print('=' * 70)
    print('SQLAlchemy 1.x Legacy Query Audit Report')
    print('=' * 70)
    print(f'Total legacy query occurrences found: {len(all_findings)}')
    print(f'Files affected: {len(by_file)}')
    print()

    if not all_findings:
        print('[OK] No legacy SQLAlchemy 1.x query patterns detected.')
        return 0

    for filepath, findings in sorted(by_file.items()):
        rel = os.path.relpath(filepath, root)
        print(f'\n[FILE] {rel}  ({len(findings)} occurrence(s))')
        for f in findings:
            print(f'   L{f["line"]:4d}  [{f["pattern"]}]  {f["code"][:80]}')

    print('\n' + '=' * 70)
    print('REFACTORING GUIDE (SQLAlchemy 2.0+)')
    print('=' * 70)
    print("""
Legacy pattern:              Modern 2.0+ equivalent:
------------------------------------------------------------
Model.query.filter(...)      select(Model).where(...)
session.query(Model)         session.execute(select(Model))
Model.query.get(id)          session.get(Model, id)
Model.query.all()              session.execute(select(Model)).scalars().all()
Model.query.first()          session.execute(select(Model)).scalars().first()
Model.query.count()          session.execute(select(func.count()).select_from(Model)).scalar()
""")
    return 1


if __name__ == '__main__':
    sys.exit(main())
