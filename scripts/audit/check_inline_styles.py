"""Fail the build on inline styles and inline event handlers in templates.

Inline styles defeat the design-token layer: a `style="..."` in a template wins
over any stylesheet, so a colour or spacing value written there can never be
changed centrally and drifts from the rest of the system. They also defeat
CSP unless `unsafe-inline` is allowed.

This is a ratchet, not a one-shot purge. It reports the number of occurrences
and fails above a ceiling, so the count can only go down. A plain "must be
zero" gate would fail the build today and block every other change until the
whole frontend is rewritten, which is how gates get disabled.

Usage:
    python scripts/audit/check_inline_styles.py            # enforce the ceiling
    python scripts/audit/check_inline_styles.py --report   # count only
    python scripts/audit/check_inline_styles.py --set 0    # lower the ceiling
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CEILING_PATH = ROOT / 'scripts/audit/inline_style_ceiling.json'

SKIP_DIRS = {'.venv', 'site-packages', 'node_modules', '__pycache__', '.mypy_cache', '.git'}

# style="..." / style='...' on any tag
STYLE_ATTR = re.compile(r"""\sstyle\s*=\s*(?P<q>["'])(?P<val>[^"']*)(?P=q)""", re.I)
# <style> ... </style> blocks
STYLE_BLOCK = re.compile(r'<style\b[^>]*>', re.I)
# inline handlers: onclick=, onchange=, onsubmit= ...
EVENT_ATTR = re.compile(r"""\son(?P<name>[a-z]+)\s*=\s*(?P<q>["'])""", re.I)
ALLOWED_EVENTS = {'off'}

COMMENT = (
    'Inline styles and inline event handlers are banned. Move the rule into a\n'
    'stylesheet and let the design tokens in static/css own the value, or read\n'
    'the value from a data- attribute when it is genuinely dynamic.'
)


def templates() -> list[pathlib.Path]:
    return [
        p for p in (ROOT / 'templates').rglob('*.html') if not any(s in p.parts for s in SKIP_DIRS)
    ]


def audit() -> dict:
    style_attrs: list[tuple[str, int]] = []
    style_blocks: list[tuple[str, int]] = []
    event_attrs: list[tuple[str, int]] = []

    for path in templates():
        rel = str(path.relative_to(ROOT))
        try:
            lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            if STYLE_ATTR.search(line):
                style_attrs.append((rel, n))
            if STYLE_BLOCK.search(line):
                style_blocks.append((rel, n))
            for m in EVENT_ATTR.finditer(line):
                if m.group('name').lower() in ALLOWED_EVENTS:
                    continue
                event_attrs.append((rel, n))

    return {
        'style_attributes': sorted(style_attrs),
        'style_blocks': sorted(style_blocks),
        'event_attributes': sorted(event_attrs),
    }


def ceiling() -> int:
    if not CEILING_PATH.exists():
        return 0
    try:
        return int(json.loads(CEILING_PATH.read_text(encoding='utf-8'))['max'])
    except (ValueError, KeyError, OSError):
        return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report', action='store_true', help='count only, never fail')
    ap.add_argument('--set', type=int, metavar='N', help='write a new ceiling')
    args = ap.parse_args(argv if argv is not None else sys.argv[1:])

    result = audit()
    counts = {k: len(v) for k, v in result.items()}
    total = sum(counts.values())

    if args.set is not None:
        CEILING_PATH.write_text(
            json.dumps({'max': args.set, 'note': COMMENT}, indent=2) + '\n', encoding='utf-8'
        )
        print(f'inline-style ceiling set to {args.set}')
        return 0

    limit = ceiling()
    print(f'templates scanned     : {len(templates())}')
    for key, value in sorted(counts.items()):
        print(f'{key:24}: {value}')
    print(f'{"total":24}: {total}')
    print(f'ceiling               : {limit}')

    if args.report:
        return 0

    if total > limit:
        offenders: dict[str, int] = {}
        for key, rows in result.items():
            for rel, _n in rows:
                offenders[f'{rel} ({key})'] = 1
        print(f'\n{total - limit} over the ceiling. {COMMENT}\n', file=sys.stderr)
        for name in sorted(offenders)[:25]:
            print(f'  {name}', file=sys.stderr)
        if len(offenders) > 25:
            print(f'  ... and {len(offenders) - 25} more', file=sys.stderr)
        return 1

    print('\nOK: inline styles within the ratchet ceiling')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
