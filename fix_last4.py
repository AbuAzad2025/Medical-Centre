#!/usr/bin/env python3
"""Fix last 4 TRY401 - direct replacement."""

# Fix access_control_service.py
fn = "D:/Data/MED-2-7-2025/medical_system/services/access_control_service.py"
with open(fn, encoding="utf-8") as fh:
    content = fh.read()

content = content.replace(
    'logging.exception("Error checking permission \\\'{permission_name}\': %s", e)',
    'logging.exception("Error checking permission \'{permission_name}\'")'
)
content = content.replace(
    'logging.exception("Error checking role \\\'{role_name}\': %s", e)',
    'logging.exception("Error checking role \'{role_name}\'")'
)

with open(fn, "w", encoding="utf-8", newline="") as fh:
    fh.write(content)

# Fix background_worker_safety.py
fn = "D:/Data/MED-2-7-2025/medical_system/utils/background_worker_safety.py"
with open(fn, encoding="utf-8") as fh:
    content = fh.read()

# Fix multiline logger.exception calls
import re

content = re.sub(
    r"logger\.exception\(\s*'[^']*'\s*,\s*[^)]+\)",
    r"logger.exception('')",
    content
)

with open(fn, "w", encoding="utf-8", newline="") as fh:
    fh.write(content)

# Fix safe_requests.py
fn = "D:/Data/MED-2-7-2025/medical_system/utils/safe_requests.py"
with open(fn, encoding="utf-8") as fh:
    content = fh.read()

content = re.sub(
    r"logger\.exception\(\s*'[^']*'\s*,\s*[^)]+\)",
    r"logger.exception('')",
    content
)

with open(fn, "w", encoding="utf-8", newline="") as fh:
    fh.write(content)
