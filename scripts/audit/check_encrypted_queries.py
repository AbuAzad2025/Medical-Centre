#!/usr/bin/env python3
"""
Encrypted Query Audit - Check for unencrypted sensitive data in queries.
Ensures sensitive fields are encrypted using the encryption utilities.
"""

import re
import sys
from pathlib import Path

# Patterns that indicate sensitive data that should be encrypted
# More specific patterns to avoid false positives
SENSITIVE_PATTERNS = [
    # Credit card numbers (more specific)
    r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
    # SSN (US format)
    r'\b\d{3}-\d{2}-\d{4}\b',
    # Phone numbers with country code (more specific)
    r'\+\d{1,3}[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
    # Saudi phone numbers (05X XXXXXXX)
    r'\b05\d{8}\b',
]

# Files to skip
SKIP_DIRS = {
    '.venv',
    'node_modules',
    '__pycache__',
    '.git',
    'migrations',
    'tests',
    'backups',
    'dist',
    'build',
}
SKIP_EXTENSIONS = {
    '.pyc',
    '.pyo',
    '.pyd',
    '.so',
    '.dll',
    '.exe',
    '.bin',
    '.png',
    '.jpg',
    '.jpeg',
    '.gif',
    '.ico',
    '.woff',
    '.woff2',
    '.ttf',
    '.eot',
    '.pdf',
    '.zip',
    '.tar',
    '.gz',
}
# Files to skip (test/demo data with known patterns)
SKIP_FILES = {
    'app/shared/validators.py',
    'scripts/first_run/dev_first_run.py',
}


def should_skip_file(filepath: Path) -> bool:
    """Check if file should be skipped"""
    # Skip directories
    if any(part in SKIP_DIRS for part in filepath.parts):
        return True
    # Skip binary files
    if filepath.suffix in SKIP_EXTENSIONS:
        return True
    # Skip known test/demo files (normalize path separator)
    rel_path = str(filepath.relative_to(Path(__file__).resolve().parents[2])).replace('\\', '/')
    return rel_path in SKIP_FILES


def check_file_for_sensitive_data(filepath: Path) -> list:
    """Check a file for potential unencrypted sensitive data patterns"""
    violations = []
    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            # Skip comments and test files
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('/*'):
                continue
            for pattern in SENSITIVE_PATTERNS:
                if re.search(pattern, line):
                    violations.append((filepath, i, line.strip()[:100]))
    except Exception as e:
        print(f'Warning: Could not read {filepath}: {e}')
    return violations


def main():
    root = Path(__file__).resolve().parents[2]

    print('Checking for unencrypted sensitive data in queries...')

    total_violations = 0
    files_with_violations = 0

    # Only scan relevant source directories
    scan_dirs = ['app', 'routes', 'services', 'utils', 'models', 'scripts']
    for scan_dir in scan_dirs:
        dir_path = root / scan_dir
        if not dir_path.exists():
            continue

        for filepath in dir_path.rglob('*'):
            if not filepath.is_file():
                continue

            if should_skip_file(filepath):
                continue

            violations = check_file_for_sensitive_data(filepath)
            if violations:
                files_with_violations += 1
                total_violations += len(violations)
                for vp, line_num, line in violations[:5]:
                    try:
                        rel_path = vp.relative_to(Path.cwd().resolve())
                    except ValueError:
                        rel_path = vp
                    safe_line = line[:100].encode('ascii', errors='replace').decode('ascii')
                    print(f'{rel_path}:{line_num}: {safe_line}')
                if len(violations) > 5:
                    print(f'  ... and {len(violations) - 5} more violations')

    if total_violations > 0:
        print(
            f'\n[FAILED] Found {total_violations} potential unencrypted sensitive data patterns in {files_with_violations} files'
        )
        print('Please ensure sensitive data is encrypted using the encryption utilities.')
        return 1

    print('[PASSED] No unencrypted sensitive data patterns found')
    return 0


if __name__ == '__main__':
    sys.exit(main())
