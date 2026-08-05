#!/usr/bin/env python3
"""Fix broken logging.exception in auth_routes.py - multiline fix."""
with open("D:/Data/MED-2-7-2025/medical_system/routes/auth_routes.py", encoding="utf-8") as fh:
    lines = fh.readlines()

# Lines 429-430 have the broken multiline logging.exception
# Fix by replacing lines 429-430 with a single line
new_lines = []
i = 0
while i < len(lines):
    if i == 428:  # 0-indexed = line 429
        # Skip the broken two lines, insert fixed version
        new_lines.append('            logging.exception("Login error")\n')
        i += 2  # Skip the two broken lines
    else:
        new_lines.append(lines[i])
        i += 1

with open("D:/Data/MED-2-7-2025/medical_system/routes/auth_routes.py", "w", encoding="utf-8", newline="") as fh:
    fh.write("".join(new_lines))
