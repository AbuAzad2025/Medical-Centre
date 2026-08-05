#!/usr/bin/env python3
"""Fix TRY401: redundant exception in logging.exception calls.

Pattern: logging.exception(f"msg {e!s}") or logging.exception(f"msg {e}")
-> logging.exception("msg", exc_info=e) or just logging.exception("msg")
since logging.exception() already includes traceback.
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
        # Pattern: logging.exception(f"...{e!s}...") or logging.exception(f"...{e}...")
        # Replace with: logging.exception("...%s...", e) or logging.exception("...")

        # Find the f-string in the logging.exception call
        # This is a simple approach - look for f"..." or f'...' patterns containing {e}
        m = re.search(r'(logging\.exception\()(f?"([^"]*)"|f\'([^\']*)\')', line)
        if m:
            full_call = m.group(0)
            quote_char = '"' if m.group(2).startswith('f"') or m.group(2).startswith('"') else "'"
            fstring_content = m.group(3) or m.group(4) or ""

            # Check if it contains {e!s} or {e} or {exc!s} etc.
            if '{e!s}' in fstring_content or '{e}' in fstring_content or '{exc!s}' in fstring_content or '{exc}' in fstring_content:
                # Extract the exception variable name
                exc_var = 'e'
                if '{exc!s}' in fstring_content or '{exc}' in fstring_content:
                    exc_var = 'exc'

                # Remove the exception var from the message
                new_msg = fstring_content.replace(f'{{{exc_var}!s}}', '%s').replace(f'{{{exc_var}}}', '%s')
                new_msg = new_msg.replace('{exc!s}', '%s').replace('{exc}', '%s')

                # Replace: logging.exception(f"msg {e!s}") -> logging.exception("msg %s", e)
                new_line = line.replace(full_call, f'logging.exception("{new_msg}", {exc_var})')
                lines[line_idx] = new_line
                fixed += 1
                total_fixed += 1

    if fixed > 0:
        with open(fn, "w", encoding="utf-8", newline="") as fh:
            fh.write("".join(lines))

