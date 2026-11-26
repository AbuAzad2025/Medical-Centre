"""Remove stray ': %s' from logging.exception calls that pass no argument."""

import glob
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PATTERN = re.compile(r"(logging\.(?:exception|error)\('[^'\n]*?): %s'\)")
count = 0
files = 0
for base in ('routes', 'services', 'app', 'utils'):
    for path in glob.glob(os.path.join(ROOT, base, '**', '*.py'), recursive=True):
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        new, n = PATTERN.subn(r"\1')", text)
        if n:
            with open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(new)
            count += n
            files += 1
print('replacements', count, 'files', files)
