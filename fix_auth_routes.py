#!/usr/bin/env python3
"""Fix broken syntax in auth_routes.py."""
import re

with open("D:/Data/MED-2-7-2025/medical_system/routes/auth_routes.py", encoding="utf-8") as fh:
    content = fh.read()

# Fix the broken f-string in logging.exception
content = re.sub(
    r'logging\.exception\("Login error: %s\\n\{traceback\.format_exc\(\)\}"',
    r'logging.exception("Login error"',
    content
)

# Also fix the other two that weren't fully fixed
content = re.sub(
    r'logging\.exception\("Profile update error: %s", e\)',
    r'logging.exception("Profile update error")',
    content
)
content = re.sub(
    r'logging\.exception\("Change password error: %s", e\)',
    r'logging.exception("Change password error")',
    content
)

with open("D:/Data/MED-2-7-2025/medical_system/routes/auth_routes.py", "w", encoding="utf-8", newline="") as fh:
    fh.write(content)
