import re
from pathlib import Path

for path in Path('templates/dashboards').rglob('*.html'):
    text = path.read_text(encoding='utf-8')
    fixed = re.sub(r"_\(_\('([^']*)'\)\)", lambda m: f"_('{m.group(1)}')", text)
    if fixed != text:
        path.write_text(fixed, encoding='utf-8', newline='')
        print('patched', path)
