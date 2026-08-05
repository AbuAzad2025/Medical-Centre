#!/usr/bin/env python3
"""Fix remaining TRY401: multiple args in logging.exception calls."""

import re

files = [
    "D:/Data/MED-2-7-2025/medical_system/routes/backup_routes.py",
    "D:/Data/MED-2-7-2025/medical_system/routes/manager/staff.py",
    "D:/Data/MED-2-7-2025/medical_system/routes/reception/dashboard.py",
    "D:/Data/MED-2-7-2025/medical_system/services/access_control_service.py",
    "D:/Data/MED-2-7-2025/medical_system/services/backup_automation_service.py",
    "D:/Data/MED-2-7-2025/medical_system/services/backup_execution_service.py",
    "D:/Data/MED-2-7-2025/medical_system/services/data_retention_service.py",
    "D:/Data/MED-2-7-2025/medical_system/services/webhook_service.py",
    "D:/Data/MED-2-7-2025/medical_system/tasks/system_tasks.py",
    "D:/Data/MED-2-7-2025/medical_system/utils/background_worker_safety.py",
    "D:/Data/MED-2-7-2025/medical_system/utils/safe_requests.py",
]

total_fixed = 0
for fn in files:
    with open(fn, encoding="utf-8") as fh:
        content = fh.read()

    # Pattern: logger.exception("format %s %s", arg1, arg2, ...) -> logger.exception("format")
    # Keep the format string, remove all format arguments
    new_content = re.sub(
        r'(\w+\.exception\()(["\'][^"\']*["\'])\s*,\s*[^)]+\)',
        r'\1\2)',
        content
    )

    # Also handle: logging.exception(str(e)) -> logging.exception("")
    new_content = re.sub(
        r'logging\.exception\(str\(e\)\)',
        r'logging.exception("")',
        new_content
    )

    if new_content != content:
        with open(fn, "w", encoding="utf-8", newline="") as fh:
            fh.write(new_content)
        total_fixed += 1

