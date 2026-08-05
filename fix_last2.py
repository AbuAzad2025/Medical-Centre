#!/usr/bin/env python3
"""Fix last 2 TRY401 in access_control_service.py."""
fn = "D:/Data/MED-2-7-2025/medical_system/services/access_control_service.py"
with open(fn, encoding="utf-8") as fh:
    content = fh.read()

# The actual content has: "Error checking permission '{permission_name}': %s"
# with a single backslash before the single quote
old1 = 'logging.exception("Error checking permission \'{permission_name}\': %s", e)'
new1 = 'logging.exception("Error checking permission \'{permission_name}\'")'
old2 = 'logging.exception("Error checking role \'{role_name}\': %s", e)'
new2 = 'logging.exception("Error checking role \'{role_name}\'")'


content = content.replace(old1, new1)
content = content.replace(old2, new2)

with open(fn, "w", encoding="utf-8", newline="") as fh:
    fh.write(content)
