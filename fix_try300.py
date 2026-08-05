#!/usr/bin/env python3
"""Fix TRY300: refactor try-except to use else blocks where applicable."""
import ast
import re

files_to_fix = [
    "D:/Data/MED-2-7-2025/medical_system/app/core/rate_limiter.py",
    "D:/Data/MED-2-7-2025/medical_system/app/integrations/printing/escpos.py",
    "D:/Data/MED-2-7-2025/medical_system/app/integrations/sms/provider.py",
    "D:/Data/MED-2-7-2025/medical_system/app/shared/pos_charge.py",
    "D:/Data/MED-2-7-2025/medical_system/app/shared/print_context.py",
    "D:/Data/MED-2-7-2025/medical_system/app/shared/report_template_service.py",
    "D:/Data/MED-2-7-2025/medical_system/app_factory.py",
    "D:/Data/MED-2-7-2025/medical_system/models/branding.py",
    "D:/Data/MED-2-7-2025/medical_system/models/budget.py",
    "D:/Data/MED-2-7-2025/medical_system/models/cash_register.py",
    "D:/Data/MED-2-7-2025/medical_system/models/notification.py",
    "D:/Data/MED-2-7-2025/medical_system/models/patient.py",
    "D:/Data/MED-2-7-2025/medical_system/models/whatsapp_integration.py",
    "D:/Data/MED-2-7-2025/medical_system/routes/accountant/__init__.py",
    "D:/Data/MED-2-7-2025/medical_system/routes/backup_routes.py",
    "D:/Data/MED-2-7-2025/medical_system/routes/doctor/diagnosis.py",
    "D:/Data/MED-2-7-2025/medical_system/routes/doctor/visits.py",
    "D:/Data/MED-2-7-2025/medical_system/routes/emergency/analytics.py",
    "D:/Data/MED-2-7-2025/medical_system/routes/lab/__init__.py",
]

for fn in files_to_fix:
    with open(fn, encoding="utf-8") as fh:
        content = fh.read()
    
    original = content
    
    # Pattern 1: try: return X; except: return Y -> try: X; except: Y; else: return X
    # Actually, the TRY300 pattern is: try: stmt; except: ...; stmt after try
    # Refactor: try: ...; else: stmt
    
    # Simple pattern: try: ...\n        return X\n    except ...:\n        ...\n        return Y\n    \n    Z  ->  try: ...\n    except ...:\n        ...\n        return Y\n    else:\n        return X\n    Z
    
    # This is complex - let me use a simpler approach: just run ruff --fix on each file
    
    if content != original:
        with open(fn, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
        print(f"Fixed: {fn}")

print("Done")