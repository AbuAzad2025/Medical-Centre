import glob
import re

TEMPLATE_FILES = glob.glob('templates/**/*.html', recursive=True) + glob.glob('templates/**/*.j2', recursive=True) + glob.glob('templates/**/*.jinja', recursive=True)
JS_FILES = glob.glob('static/js/**/*.js', recursive=True)

def camel(s):
    parts = s.split('-')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])

actions = set()
for path in TEMPLATE_FILES:
    text = open(path, encoding='utf-8', errors='replace').read()
    for m in re.finditer(r'data-action="([^"]+)"', text):
        actions.add(m.group(1))
    for m in re.finditer(r"'data_action':\s*'([^']+)'", text):
        actions.add(m.group(1))

js_source = ''
for path in JS_FILES:
    js_source += open(path, encoding='utf-8', errors='replace').read()

BUILTIN = {'print', 'go-back', 'reload', 'close-modal', 'submit-form', 'confirm', 'confirm-submit',
           'confirm-navigate', 'toggle-password'}

missing = []
for action in sorted(actions):
    if action in BUILTIN:
        continue
    if action.startswith('filter-') or action.startswith('filter_'):
        continue
    fn = camel(action)
    if re.search(r'(export\s+(async\s+)?function\s+' + re.escape(fn) + r'\b|function\s+' + re.escape(fn) + r'\b|window\.' + re.escape(fn) + r'\s*=)', js_source):
        continue
    missing.append(action)

print('actions found:', len(actions))
print('missing implementations:')
for a in missing:
    print(' -', a)
