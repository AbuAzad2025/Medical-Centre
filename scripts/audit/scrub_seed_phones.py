"""Replace literal phone numbers in seed scripts with runtime-generated values."""

import re

for path in (
    'scripts/audit/seed_package1.py',
    'scripts/audit/seed_package1_bookings.py',
    'scripts/audit/seed_package1_complete.py',
):
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    if 'import time' not in text:
        text = text.replace('import os\n', 'import os\nimport time\n', 1)
    if 'PHONES =' not in text:
        anchor = 'SHOTS ='
        text = text.replace(
            anchor,
            "PHONES = ['05' + str(int(time.time()) + i)[-9:] for i in range(3)]\n" + anchor,
            1,
        )
    text = re.sub(r"'055111000[123]'", lambda m: f'PHONES[{int(m.group(0)[-2]) - 1}]', text)
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)
    print('patched', path)
