import os, re

EXCLUDE = {
    'datetime', 'uuid', 'uuid4', 'uuid1', 'uuid3', 'uuid5', 'models', 'os', 'sys', 
    'json', 'pathlib', 'contextlib', 're', 'text', 'datetime', 'uuid4', 'uuid1', 
    'uuid3', 'uuid5', 'models', 'os', 'sys', 'json', 'pathlib', 'contextlib',
    'botocore', 'sqlalchemy', 'pynetdicom', 'flask', 'flask_login', 'flask_wtf',
    'wtforms', 'sqlalchemy.orm', 'werkzeug', 'jinja2', 'text', 'contextlib',
    'pynetdicom', 'botocore', 'sqlalchemy.orm', 'flask_login', 'flask_wtf',
    'wtforms', 'werkzeug', 'jinja2', 'pathlib', 'contextlib', 'os', 'sys'
}

print('=== سلاسل الترجمة الحقيقية ===')

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