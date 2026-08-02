"""Fix __future__ import ordering in files where it was displaced by migration."""

import os

FILES = [
    'app/integrations/devices/biometric.py',
    'services/dicom_service.py',
    'services/fhir_service.py',
    'services/radiology_service.py',
    'services/refund_service.py',
    'services/sso_service.py',
    'services/tenant_job_runner.py',
]

for fp in FILES:
    if not os.path.exists(fp):
        print(f'MISSING: {fp}')
        continue
    with open(fp, encoding='utf-8') as f:
        lines = f.readlines()
    future_idx = None
    for i, line in enumerate(lines):
        if '__future__' in line:
            future_idx = i
            break
    if future_idx is None:
        print(f'No __future__ in {fp}')
        continue
    # Find the first content line (after docstring/empty lines)
    insert_idx = 0
    in_docstring = False
    for i in range(future_idx):
        stripped = lines[i].strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            in_docstring = not in_docstring
            insert_idx = i + 1
            continue
        if in_docstring:
            insert_idx = i + 1
            continue
        if stripped and not stripped.startswith('#'):
            insert_idx = i
            break
    # Move __future__ line to insert_idx
    future_line = lines.pop(future_idx)
    lines.insert(insert_idx, future_line)
    with open(fp, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f'Fixed {fp}')
