#!/usr/bin/env python3
"""Fix TRY401: f-string patterns in logging.exception calls."""

import json
import re
import subprocess

result = subprocess.run(
    ["ruff", "check", ".", "--select", "TRY401", "--output-format=json"],
    capture_output=True, text=True, encoding="utf-8"
)
findings = json.loads(result.stdout)

by_file = {}
for f in findings:
    fn = f["filename"]
    row = f["location"]["row"]
    col = f["location"]["column"]
    by_file.setdefault(fn, []).append((row, col))

total_fixed = 0
for fn, hits in by_file.items():
    with open(fn, encoding="utf-8") as fh:
        src = fh.read()
    lines = src.splitlines(keepends=True)

    hits.sort(key=lambda x: x[0], reverse=True)

    fixed = 0
    for row, col in hits:
        line_idx = row - 1
        if line_idx >= len(lines):
            continue
        line = lines[line_idx]

        # Pattern 1: logger.exception(f"msg {e}") or logger.exception(f'msg {e}')
        # Pattern 2: logger.exception("msg %s", e)
        # Replace with: logger.exception("msg")

        # Handle f-string: logger.exception(f"msg {e}") -> logger.exception("msg")
        m = re.search(r'(\w+\.exception\()f(["\'])(.*?)\2\s*\)', line)
        if m:
            prefix = m.group(1)
            quote = m.group(2)
            msg = m.group(3)
            # Remove {e} or {e!s} or {exc} etc from message
            clean_msg = re.sub(r'\{[^}]+\}', '%s', msg)
            new_line = re.sub(
                r'(\w+\.exception\()f(["\'])(.*?)\2\s*\)',
                r'\1' + quote + clean_msg + quote + r')',
                line
            )
            lines[line_idx] = new_line
            fixed += 1
            total_fixed += 1
            continue

        # Handle format string: logger.exception("msg %s", e) -> logger.exception("msg")
        m = re.search(r'(\w+\.exception\()(["\'][^"\']*["\'])\s*,\s*\w+\s*\)', line)
        if m:
            prefix = m.group(1)
            msg = m.group(2)
            new_line = re.sub(
                r'(\w+\.exception\()(["\'][^"\']*["\'])\s*,\s*\w+\s*\)',
                r'\1' + msg + r')',
                line
            )
            lines[line_idx] = new_line
            fixed += 1
            total_fixed += 1

    if fixed > 0:
        with open(fn, "w", encoding="utf-8", newline="") as fh:
            fh.write("".join(lines))

