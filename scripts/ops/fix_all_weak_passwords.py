"""Comprehensive weak password scanner and fixer for all test files."""

import os

WEAK_PASSWORDS = [
    "set_password('p')",
    "set_password('test')",
    "set_password('test123')",
    "set_password('x')",
    "set_password('password')",
    "set_password('admin')",
    "set_password('123456')",
    "set_password('owner123')",
    "set_password('sa123456')",
    "set_password('short')",
    "set_password('docpass1')",
    "set_password('sapass1')",
    'set_password("test123")',
    'set_password("p")',
]

matches = []
for root, _dirs, files in os.walk('tests'):
    for f in files:
        if f.endswith('.py'):
            fp = os.path.join(root, f)
            with open(fp, encoding='utf-8') as fh:
                content = fh.read()
            found = False
            for pw in WEAK_PASSWORDS:
                if pw in content:
                    matches.append((fp, pw))
                    found = True
            if found:
                # Replace all weak passwords with compliant one
                for pw in WEAK_PASSWORDS:
                    content = content.replace(pw, "set_password('ValidPass123!')")
                with open(fp, 'w', encoding='utf-8') as fh:
                    fh.write(content)
                print(f'Fixed {fp}')

print(f'Total weak password matches found and fixed: {len(matches)}')
