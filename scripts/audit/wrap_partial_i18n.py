"""Wrap hardcoded Arabic UI strings in _() inside a shared partial."""

import re
import sys

path = sys.argv[1]
with open(path, encoding='utf-8') as fh:
    text = fh.read()
AR = re.compile(r'[\u0600-\u06ff]')


def wrap_literal(match):
    quote, value = match.group(1), match.group(2)
    if AR.search(value) and '{{' not in value:
        return f"{quote}{{{{ _('{value}') }}}}{quote}"
    return match.group(0)


# Text nodes between tags (simple, no Jinja)
def wrap_text(match):
    value = match.group(1)
    stripped = value.strip()
    if (
        stripped
        and AR.search(stripped)
        and '{{' not in stripped
        and '{%' not in stripped
        and '"' not in stripped
        and "'" not in stripped
        and '_(' not in stripped
    ):
        return match.group(0).replace(stripped, "{{ _('" + stripped + "') }}")
    return match.group(0)


text = re.sub(r'>([^<>]+)<', wrap_text, text)
# Attribute values
text = re.sub(
    r'(title|placeholder|aria-label)="([^"]*[\u0600-\u06ff][^"]*)"',
    lambda m: f'{m.group(1)}="{{{{ _(\'{m.group(2)}\') }}}}"',
    text,
)
with open(path, 'w', encoding='utf-8', newline='') as fh:
    fh.write(text)
print('wrapped', path)
