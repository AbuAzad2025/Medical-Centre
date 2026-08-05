#!/usr/bin/env python3
"""Fix ARG005: prefix unused lambda arguments with _."""

import re

# Get all ARG005 findings
import subprocess

result = subprocess.run(
    ["ruff", "check", ".", "--select", "ARG005", "--output-format=json"],
    capture_output=True, text=True, encoding="utf-8"
)
import json

findings = json.loads(result.stdout)

by_file = {}
for f in findings:
    fn = f["filename"]
    row = f["location"]["row"]
    col = f["location"]["column"]
    m = re.search(r"`(\w+)`", f["message"])
    name = m.group(1) if m else None
    by_file.setdefault(fn, []).append((row, col, name))

total_fixed = 0
for fn, hits in by_file.items():
    with open(fn, encoding="utf-8") as fh:
        src = fh.read()
    lines = src.splitlines(keepends=True)

    # Sort hits by line, then column descending (rightmost first)
    hits.sort(key=lambda x: (x[0], -x[1]))

    fixed = 0
    for row, col, name in hits:
        if name is None:
            continue
        line_idx = row - 1
        if line_idx >= len(lines):
            continue
        line = lines[line_idx]
        # Find the exact name at approximately the column position
        # Look for `lambda name:` or `lambda name,` or `lambda name)`
        # Replace the name at/after the column
        pos = col - 1
        if pos < len(line):
            # Check if the name matches at this position
            if line[pos:pos+len(name)] == name:
                # Ensure it's a word boundary
                before_ok = pos == 0 or (not line[pos-1].isalnum() and line[pos-1] != '_')
                after_ok = pos+len(name) >= len(line) or (not line[pos+len(name)].isalnum() and line[pos+len(name)] != '_')
                if before_ok and after_ok:
                    lines[line_idx] = line[:pos] + "_" + name + line[pos+len(name):]
                    fixed += 1
                    total_fixed += 1

    if fixed > 0:
        with open(fn, "w", encoding="utf-8", newline="") as fh:
            fh.write("".join(lines))

