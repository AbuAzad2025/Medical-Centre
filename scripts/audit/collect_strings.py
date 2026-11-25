import collections
import glob
import re

counter = collections.Counter()
for path in glob.glob('templates/**/*.html', recursive=True):
    text = open(path, encoding='utf-8').read()
    counter.update(re.findall(r"_\(\s*['\"]([^'\"]{2,60})['\"]\s*\)", text))
for value, count in counter.most_common(100):
    print(f'{count:5}  {value}')
