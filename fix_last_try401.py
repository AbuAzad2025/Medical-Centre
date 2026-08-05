#!/usr/bin/env python3
"""Fix last 4 TRY401."""
import re

# Fix access_control_service.py lines 480, 489
fn = "D:/Data/MED-2-7-2025/medical_system/services/access_control_service.py"
with open(fn, encoding="utf-8") as fh:
    content = fh.read()

# Fix single-quote in format string
content = re.sub(
    r'logging\.exception\("Error checking permission \\\'\{permission_name\}\'\': %s", e\)',
    r'logging.exception("Error checking permission \'{permission_name}\'")',
    content
)
content = re.sub(
    r'logging\.exception\("Error checking role \\\'\{role_name\}\'\': %s", e\)',
    r'logging.exception("Error checking role \'{role_name}\'")',
    content
)
with open(fn, "w", encoding="utf-8", newline="") as fh:
    fh.write(content)

# Fix background_worker_safety.py - multiline
fn = "D:/Data/MED-2-7-2025/medical_system/utils/background_worker_safety.py"
with open(fn, encoding="utf-8") as fh:
    lines = fh.readlines()

# Line 48-50 (0-indexed 47-49) - multiline logger.exception
# Need to join and fix
new_lines = []
i = 0
while i < len(lines):
    if i == 47:  # Line 48 - start of the multiline
        # Check if next lines are continuation
        if 'logger.exception(' in lines[i]:
            # Find the closing )
            j = i
            full = ""
            while j < len(lines):
                full += lines[j]
                if ')' in lines[j] and full.count('(') == full.count(')'):
                    break
                j += 1
            # Fix: logger.exception('fmt', args...) -> logger.exception('fmt')
            fixed = re.sub(
                r'(logger\.exception\()(["\'][^"\']*["\'])\s*,\s*[^)]+\)',
                r'\1\2)',
                full
            )
            new_lines.append(fixed)
            i = j + 1
        else:
            new_lines.append(lines[i])
            i += 1
    else:
        new_lines.append(lines[i])
        i += 1

with open(fn, "w", encoding="utf-8", newline="") as fh:
    fh.write("".join(new_lines))

# Fix safe_requests.py - multiline
fn = "D:/Data/MED-2-7-2025/medical_system/utils/safe_requests.py"
with open(fn, encoding="utf-8") as fh:
    lines = fh.readlines()

# Similar approach for line 67-69
new_lines = []
i = 0
while i < len(lines):
    if i == 67 and 'logger.exception(' in lines[i]:
        j = i
        full = ""
        while j < len(lines):
            full += lines[j]
            if ')' in lines[j] and full.count('(') == full.count(')'):
                break
            j += 1
        fixed = re.sub(
            r'(logger\.exception\()(["\'][^"\']*["\'])\s*,\s*[^)]+\)',
            r'\1\2)',
            full
        )
        new_lines.append(fixed)
        i = j + 1
    else:
        new_lines.append(lines[i])
        i += 1

with open(fn, "w", encoding="utf-8", newline="") as fh:
    fh.write("".join(new_lines))
