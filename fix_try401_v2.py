#!/usr/bin/env python3
"""Fix TRY401: redundant exception object in logging.exception calls.

Pattern: logger.exception("msg %s", e) -> logger.exception("msg")
The exception traceback is automatically included by exception().
"""

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

        # Pattern: logger.exception("msg %s", var) or logger.exception("msg", var)
        # Replace with: logger.exception("msg")
        # Need to be careful - only fix calls to .exception() method

        # Find the .exception( call
        # Match: <something>.exception("message", var) or .exception('message', var)
        m = re.search(r'(\w+\.exception\()(["\'][^"\']*["\'])\s*,\s*\w+\s*\)', line)
        if m:
            prefix = m.group(1)
            msg = m.group(2)
            # Replace the whole call
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

