"""Mechanical template cleanup for the doctor shell (no new routes/templates)."""

import re
from pathlib import Path

paths = [
    *Path('templates/doctor').glob('*.html'),
    Path('templates/partials/_patient_details_tabs.html'),
]

for path in paths:
    text = path.read_text(encoding='utf-8')
    original = text

    # Double gettext: translate the Arabic literal once, not its translation.
    text = re.sub(r"_\(_\('([^']*)'\)\)", lambda m: f"_('{m.group(1)}')", text)

    # Bootstrap-4 spacing in the summary form.
    if path.name == 'visit_summary.html':
        text = text.replace('class="form-group"', 'class="mb-3"')
        text = re.sub(
            r'<label([^>]*)class="([^"]*)"',
            lambda m: f'<label{m.group(1)}class="{m.group(2)} form-label"',
            text,
        )

    if text != original:
        path.write_text(text, encoding='utf-8', newline='')
        print('patched', path)
