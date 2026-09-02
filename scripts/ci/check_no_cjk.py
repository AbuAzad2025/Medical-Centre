#!/usr/bin/env python3
"""
CJK Guard — fail if Chinese/Japanese/Korean characters are found in code/templates.

Why: AI assistants sometimes emit CJK glyphs due to encoding or translation
errors. Arabic/English are the only allowed natural languages in this codebase.
This check is STRICT and blocks CI.

Usage:
  python scripts/ci/check_no_cjk.py
  python scripts/ci/check_no_cjk.py --staged   # only staged files (pre-commit)

Exit code 1 if any CJK character is found outside the allowlist.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess

# CJK ranges: Unified Ideographs, Extension A, Compatibility, Hiragana, Katakana, Hangul
CJK_PATTERN = re.compile(
    r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]'
)

# Directories/files that are never scanned (vendored, history, generated)
EXCLUDED_DIRS = {
    '.git',
    '.venv',
    'venv',
    'ENV',
    '.tox',
    '__pycache__',
    '.mypy_cache',
    '.ruff_cache',
    'node_modules',
    '.pytest_cache',
    'htmlcov',
    'coverage',
    'backups',
    'logs',
    'flask_session',
}

# Files that are exempt even if they contain CJK (e.g., intentional examples)
# Keep this list minimal and documented. Use relative POSIX paths.
ALLOWLIST_FILES = {
    # Example: "docs/CHINESE_EXAMPLE.md",
}

# Extensions that are scanned. Everything else is ignored to keep the check fast
# and to avoid flagging binary files (images, fonts, etc.).
SCANNED_EXTENSIONS = {
    '.py',
    '.html',
    '.js',
    '.ts',
    '.jsx',
    '.tsx',
    '.css',
    '.json',
    '.toml',
    '.yaml',
    '.yml',
    '.sql',
    '.ini',
    '.cfg',
    '.sh',
    '.bat',
    '.ps1',
    '.md',
}

# Also scan files without extension that are text-like (e.g., Dockerfile)
SCANNED_BASENAMES = {'Dockerfile', 'Makefile'}


def is_excluded(path: pathlib.Path) -> bool:
    parts = path.parts
    for part in parts:
        if part in EXCLUDED_DIRS:
            return True
    # Allowlist exact relative path
    rel = path.as_posix()
    return rel in ALLOWLIST_FILES


def should_scan(path: pathlib.Path) -> bool:
    if path.is_dir():
        return False
    if is_excluded(path):
        return False
    if path.suffix.lower() in SCANNED_EXTENSIONS:
        return True
    return path.name in SCANNED_BASENAMES


def collect_files(staged_only: bool) -> list[pathlib.Path]:
    if staged_only:
        # Only files staged for commit (pre-commit hook)
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return []
        files = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            p = pathlib.Path(line)
            if should_scan(p) and p.exists():
                files.append(p)
        return files

    # Full scan: walk the worktree
    root = pathlib.Path()
    files: list[pathlib.Path] = []
    for p in root.rglob('*'):
        if should_scan(p):
            files.append(p)
    return sorted(files)


def scan_file(path: pathlib.Path) -> list[tuple[int, str, str]]:
    """Return list of (lineno, char, line_snippet) for each CJK hit."""
    hits: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding='utf-8', errors='strict')
    except Exception:
        # Binary or undecodable — skip
        return hits
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in CJK_PATTERN.finditer(line):
            ch = m.group(0)
            # Snippet: 30 chars before/after, escaped
            start = max(0, m.start() - 30)
            end = min(len(line), m.end() + 30)
            snippet = line[start:end].strip()
            hits.append((lineno, ch, snippet))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description='CJK guard')
    parser.add_argument(
        '--staged',
        action='store_true',
        help='Only scan staged files (for pre-commit)',
    )
    args = parser.parse_args()

    files = collect_files(staged_only=args.staged)
    if not files:
        print('CJK guard: no files to scan.')
        return 0

    total_hits = 0
    for path in files:
        hits = scan_file(path)
        if hits:
            total_hits += len(hits)
            safe_path = path.as_posix().encode('ascii', 'backslashreplace').decode()
            print(f'\nCJK violation in {safe_path}:')
            for lineno, ch, snippet in hits[:5]:  # cap per file to avoid spam
                # Show Unicode codepoint for clarity (avoid printing raw CJK on cp1252)
                cp = f'U+{ord(ch):04X}'
                safe_snippet = snippet.encode('ascii', 'backslashreplace').decode()
                print(f'  L{lineno}: {cp} -> ...{safe_snippet}...')
            if len(hits) > 5:
                print(f'  ... and {len(hits) - 5} more hits in this file')

    if total_hits:
        print(f'\nFAILED: Found {total_hits} CJK character(s) in {len(files)} scanned files.')
        print('Only Arabic and English are allowed. Remove the CJK characters and retry.')
        print(
            'If a file must intentionally contain CJK, add its POSIX path to ALLOWLIST_FILES in scripts/ci/check_no_cjk.py'
        )
        return 1

    print(f'OK: No CJK characters found in {len(files)} scanned files.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
