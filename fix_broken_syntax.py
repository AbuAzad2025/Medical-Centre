#!/usr/bin/env python3
"""Fix broken syntax from TRY401 fixes."""
import re

files_to_fix = [
    "D:/Data/MED-2-7-2025/medical_system/routes/auth_routes.py",
    "D:/Data/MED-2-7-2025/medical_system/services/payment_service.py",
]

for fn in files_to_fix:
    with open(fn, encoding="utf-8") as fh:
        content = fh.read()

    original = content
    # Fix: logging.exception("Login error: %s\n{traceback.format_exc()}"))
    content = re.sub(
        r'logging\.exception\("Login error: %s\\n\{traceback\.format_exc\(\)\}\)"\)',
        r'logging.exception("Login error")',
        content
    )
    # Fix: logging.exception("Payment IntegrityError (non-idempotency): %s"))
    content = re.sub(
        r'logging\.exception\("Payment IntegrityError \(non-idempotency\): %s"\)\)',
        r'logging.exception("Payment IntegrityError (non-idempotency)")',
        content
    )

    if content != original:
        with open(fn, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
