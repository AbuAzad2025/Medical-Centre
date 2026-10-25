import os, re

print('=== Extracting translation strings from templates ===')

# Check print_base.html
path = 'templates/print/print_base.html'
with open(path, encoding='utf-8') as f:
    content = f.read()

# Find {{ _('...') }} patterns
matches = re.findall(r'\{\{\s*_\s*\([\'\"]([^\'"]+)[\'"]\s*\)\s*\}\}', content)
for m in matches:
    print(f'Template _(): {m}')

# Check for {% trans %} blocks
trans_blocks = re.findall(r'\{% trans %\}(.*?)\{% endtrans %\}', content, re.DOTALL)
for block in trans_blocks:
    print(f'TRANS BLOCK: {block.strip()}')

# Check for gettext
matches = re.findall(r'gettext\([\'"]([^\'"]+)[\'"]\)', open('templates/print/print_base.html', encoding='utf-8').read())
for m in matches:
    print(f'gettext: {m}')

# Check _() calls in Python files
print('\n=== Python _() calls ===')
EXCLUDE = {
    'datetime', 'uuid', 'uuid4', 'uuid1', 'uuid3', 'uuid5', 'models', 'os', 'sys', 
    'json', 'pathlib', 'contextlib', 're', 'text', 'datetime', 'uuid4', 'uuid1', 
    'uuid3', 'uuid5', 'models', 'os', 'sys', 'json', 'pathlib', 'contextlib',
    'botocore', 'sqlalchemy', 'pynetdicom', 'flask', 'flask_login', 'flask_wtf',
    'wtforms', 'sqlalchemy.orm', 'werkzeug', 'jinja2', 'text', 'contextlib',
    'pynetdicom', 'botocore', 'sqlalchemy.orm', 'flask_login', 'flask_wtf',
    'wtforms', 'werkzeug', 'jinja2', 'pathlib', 'contextlib', 'os', 'sys',
    'uuid4', 'uuid1', 'uuid3', 'uuid5', 'models', 'os', 'sys', 'json', 
    'pathlib', 'contextlib', 'botocore', 'sqlalchemy', 'pynetdicom', 'flask', 
    'flask_login', 'flask_wtf', 'wtforms', 'sqlalchemy.orm', 'werkzeug', 'jinja2', 
    'pathlib', 'contextlib', 'os', 'sys', 'models', 'os', 'sys',
    'json', 'pathlib', 'contextlib', 'botocore', 'sqlalchemy', 'pynetdicom',
    'flask', 'flask_login', 'flask_wtf', 'wtforms', 'sqlalchemy.orm', 'werkzeug', 
    'jinja2', 'pathlib', 'contextlib', 'os', 'sys'
}

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('node_modules', '.venv', '.git', '__pycache__', '.venv', 'coverage', 'e2e', 'scripts')]
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                with open(path, encoding='utf-8') as fp:
                    content = fp.read()
            except:
                continue
            matches = re.findall(r'_\(\s*[\'"]([^\'"]+)[\'"]\s*\)', content)
            for m in matches:
                m = m.strip()
                if len(m) > 3 and m.lower() not in EXCLUDE:
                    if re.search(r'[a-zA-Z\u0600-\u06FF].*[a-zA-Z\u0600-\u06FF]', m) or ' ' in m or any(c in m for c in '.,!?،؟'):
                        print(f'{os.path.relpath(path)}: "{m}"')