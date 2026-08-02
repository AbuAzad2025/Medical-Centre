"""Fix all weak test passwords from 'test123' to policy-compliant password."""

import os

scan_dir = 'tests'
fixed = 0
for root, dirs, files in os.walk(scan_dir):
    for f in files:
        if f.startswith('test_') and f.endswith('.py'):
            fp = os.path.join(root, f)
            with open(fp, encoding='utf-8') as fh:
                content = fh.read()
            new_content = content.replace(
                ".set_password('test123')", ".set_password('ValidPass123!')"
            )
            if new_content != content:
                with open(fp, 'w', encoding='utf-8') as fh:
                    fh.write(new_content)
                fixed += 1
                print(f'Fixed {fp}')
print(f'Total files fixed: {fixed}')
