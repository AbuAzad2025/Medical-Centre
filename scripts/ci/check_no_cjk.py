#!/usr/bin/env python3
"""
CJK Guard - Check for Chinese/Japanese/Korean characters in code and templates.
This prevents accidental commit of non-ASCII characters that should be in translation files.
"""

import re
import sys
from pathlib import Path

# CJK Unicode ranges
CJK_PATTERN = re.compile(
    r'[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff'
    r'\uf900-\ufaff\uff65-\uff9f]'
)

# Only scan these source directories (skip .venv, node_modules, backups, etc.)
SCAN_DIRS = [
    'app',
    'routes',
    'templates',
    'static',
    'scripts',
    'tests',
    'utils',
    'models',
    'services',
    'config',
    'migrations',
]

# File extensions to check
CHECK_EXTENSIONS = {
    '.py',
    '.html',
    '.js',
    '.ts',
    '.css',
    '.scss',
    '.json',
    '.yml',
    '.yaml',
    '.md',
    '.txt',
}

# File patterns to skip
SKIP_FILE_PATTERNS = [
    r'.*\.po$',  # Translation files
    r'.*\.mo$',  # Compiled translation files
    r'.*\.png$',
    r'.*\.jpg$',
    r'.*\.jpeg$',
    r'.*\.gif$',
    r'.*\.ico$',
    r'.*\.woff$',
    r'.*\.woff2$',
    r'.*\.ttf$',
    r'.*\.eot$',
]


def should_skip_file(filepath: Path) -> bool:
    """Check if file should be skipped"""
    rel_path = str(filepath)
    return any(re.search(pattern, rel_path) for pattern in SKIP_FILE_PATTERNS)


def check_file(filepath: Path) -> list:
    """Check a file for CJK characters, return list of (line_num, line) tuples"""
    violations = []
    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        for i, line in enumerate(content.splitlines(), 1):
            if CJK_PATTERN.search(line):
                violations.append((i, line.strip()))
    except Exception as e:
        print(f'Warning: Could not read {filepath}: {e}')
    return violations


def main():
    root = Path(__file__).resolve().parents[2]

    total_violations = 0
    files_with_violations = 0

    # Only scan relevant source directories
    for scan_dir in SCAN_DIRS:
        dir_path = root / scan_dir
        if not dir_path.exists():
            continue

        for filepath in dir_path.rglob('*'):
            if not filepath.is_file():
                continue

            if filepath.suffix not in CHECK_EXTENSIONS:
                continue

            if should_skip_file(filepath):
                continue

            violations = check_file(filepath)
            if violations:
                files_with_violations += 1
                total_violations += len(violations)
                rel_path = filepath.relative_to(Path.cwd())
                print(f'\n{rel_path}:')
                for line_num, line in violations[:5]:
                    safe_line = line[:100].encode('ascii', errors='replace').decode('ascii')
                    print(f'  Line {line_num}: {safe_line}')
                if len(violations) > 5:
                    print(f'  ... and {len(violations) - 5} more violations')

    if total_violations > 0:
        print(
            f'\n[FAILED] Found {total_violations} CJK character violations in {files_with_violations} files'
        )
        print('Please move CJK text to translation files (.po) or add files to skip list.')
        return 1
    print('[PASSED] No CJK characters found in source code')
    return 0


if __name__ == '__main__':
    sys.exit(main())
