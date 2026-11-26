import re
from pathlib import Path

path = Path('templates/dashboards/command_center.html')
text = path.read_text(encoding='utf-8')
text = re.sub(r"_\(_\('([^']*)'\)\)", lambda m: f"_('{m.group(1)}')", text)
path.write_text(text, encoding='utf-8', newline='')
print('patched command center i18n')
