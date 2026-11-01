#!/usr/bin/env python3
"""
Inline Style Ratchet - Check for inline styles and handlers in templates.
Ensures the count doesn't exceed the ceiling (397).
"""

import json
import re
import sys
from pathlib import Path

CEILING_FILE = Path(__file__).parent / 'inline_style_ceiling.json'
TEMPLATES_DIR = Path(__file__).resolve().parents[2] / 'templates'

# Regex patterns for inline styles and handlers
INLINE_STYLE_PATTERN = re.compile(r'style\s*=\s*["\'][^"\']*["\']')
INLINE_HANDLER_PATTERN = re.compile(r'on\w+\s*=\s*["\'][^"\']*["\']')


def count_inline_styles_and_handlers():
    """Count inline styles and handlers in all template files"""
    total_count = 0
    files_with_violations = []

    for template_file in TEMPLATES_DIR.rglob('*.html'):
        try:
            content = template_file.read_text(encoding='utf-8', errors='ignore')
            style_matches = INLINE_STYLE_PATTERN.findall(content)
            handler_matches = INLINE_HANDLER_PATTERN.findall(content)
            count = len(style_matches) + len(handler_matches)
            if count > 0:
                total_count += count
                files_with_violations.append((str(template_file.relative_to(TEMPLATES_DIR)), count))
        except Exception as e:
            print(f'Warning: Could not read {template_file}: {e}')

    return total_count, files_with_violations


def main():
    # Load ceiling
    with open(CEILING_FILE) as f:
        ceiling_data = json.load(f)
    ceiling = ceiling_data['max']

    print(f'Checking inline styles and handlers (ceiling: {ceiling})...')

    total_count, files_with_violations = count_inline_styles_and_handlers()

    print(f'Found {total_count} inline styles/handlers in {len(files_with_violations)} files')

    if total_count > ceiling:
        print(f'[FAILED] {total_count} exceeds ceiling of {ceiling}')
        print('Files with most violations:')
        for file_path, count in sorted(files_with_violations, key=lambda x: x[1], reverse=True)[
            :10
        ]:
            print(f'  {file_path}: {count}')
        return 1

    print('[PASSED] Inline styles/handlers within ceiling')
    return 0


if __name__ == '__main__':
    sys.exit(main())
