"""Audit templates for Bootstrap 4 legacy patterns (G-06 / G-34 debt gate)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO_ROOT / 'templates'

# Patterns that must not appear in rendered HTML templates (BS5 migration).
FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        'data-dismiss',
        re.compile(r'data-dismiss\s*='),
        'Use data-bs-dismiss (Bootstrap 5)',
    ),
    (
        'bs4-modal-close',
        re.compile(r'class="close"[^>]*data-dismiss'),
        'Use btn-close with data-bs-dismiss',
    ),
    (
        'font-weight-bold',
        re.compile(r'\bfont-weight-bold\b'),
        'Use fw-bold (Bootstrap 5)',
    ),
]

# Templates allowed to keep legacy markup temporarily (custom modals, archived).
ALLOWLIST_PATHS: set[str] = set()


def scan_templates(templates_dir: Path | None = None) -> list[dict]:
    """Return list of violations: {file, line, pattern, message, snippet}."""
    root = templates_dir or TEMPLATES_DIR
    violations: list[dict] = []

    for path in sorted(root.rglob('*.html')):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in ALLOWLIST_PATHS:
            continue
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except OSError:
            continue
        for line_no, line in enumerate(lines, start=1):
            for name, pattern, message in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    violations.append({
                        'file': rel,
                        'line': line_no,
                        'pattern': name,
                        'message': message,
                        'snippet': line.strip()[:120],
                    })
    return violations


def main() -> int:
    violations = scan_templates()
    if not violations:
        print('BS4 audit: OK (no forbidden patterns in templates)')
        return 0
    print(f'BS4 audit: {len(violations)} violation(s)')
    for v in violations:
        print(f"  {v['file']}:{v['line']} [{v['pattern']}] {v['message']}")
        print(f"    {v['snippet']}")
    return 1


if __name__ == '__main__':
    sys.exit(main())
