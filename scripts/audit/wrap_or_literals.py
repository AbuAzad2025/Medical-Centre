import re
import sys

path = sys.argv[1]
text = open(path, encoding='utf-8').read()
pattern = re.compile(r"(?<!_\()'([^'\n]*[\u0600-\u06ff][^'\n]*)'")
text = pattern.sub(lambda m: "_('" + m.group(1) + "')", text)
open(path, 'w', encoding='utf-8', newline='').write(text)
print('done', path)
