import collections
import glob
import re

counter = collections.Counter()
for path in glob.glob('templates/**/*.html', recursive=True):
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    counter.update(re.findall(r"_\(\s*['\"]([^'\"]{2,60})['\"]\s*\)", text))
for value, count in counter.most_common(100):
    print(f'{count:5}  {value}')
