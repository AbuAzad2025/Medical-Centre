import re
import sys

path = sys.argv[1]
with open(path, encoding='utf-8') as fh:
    text = fh.read()
pattern = re.compile(r"(?<!_\()'([^'\n]*[\u0600-\u06ff][^'\n]*)'")
text = pattern.sub(lambda m: "_('" + m.group(1) + "')", text)
with open(path, 'w', encoding='utf-8', newline='') as fh:
    fh.write(text)
print('done', path)
