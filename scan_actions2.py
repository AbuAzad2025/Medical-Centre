import glob
import re

TEMPLATE_FILES = glob.glob('templates/**/*.html', recursive=True)
ACTIONS = ['add-service-row', 'create-db-backup', 'export-system-data', 'forgot-password',
           'new-appointment', 'open-system-monitor', 'quickCommand', 'refresh-dashboard',
           'save-visit', 'send-ai-message']

def camel(s):
    parts = s.split('-')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])

for action in ACTIONS:
    fn = camel(action) if '-' in action else action
    hits = []
    for path in TEMPLATE_FILES:
        text = open(path, encoding='utf-8', errors='replace').read()
        if re.search(r'(function\s+' + re.escape(fn) + r'\b|window\.' + re.escape(fn) + r'\s*=|const\s+' + re.escape(fn) + r'\b|id="' + re.escape(action) + r'")', text):
            hits.append(path)
    print(action, '->', hits or 'NOT FOUND')
