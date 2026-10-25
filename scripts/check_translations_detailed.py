import os, re, json

# استخراج سلاسل الترجمة الفعلية فقط
all_strings = set()

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('node_modules', '.venv', '.git', '__pycache__', '.venv', 'coverage', 'e2e')]
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                with open(path, encoding='utf-8') as fp:
                    content = fp.read()
            except:
                continue
            # البحث عن _("text") أو _('text')
            matches = re.findall(r'_\([\'"]([^\'"]+)[\'"]\)', content)
            for m in matches:
                if m.strip() and not re.match(r'^[a-z_]+$', m) and m not in ['models', 'os', 'sys', 'json', 'datetime', 'contextlib', 'text', 'uuid', 'pynetdicom', 'botocore', 'sqlalchemy']:
                    all_strings.add(m.strip())

# القوالب
for root, dirs, files in os.walk('templates'):
    for f in files:
        if f.endswith('.html'):
            path = os.path.join(root, f)
            try:
                with open(path, encoding='utf-8') as fp:
                    content = fp.read()
            except:
                continue
            matches = re.findall(r'\{\{\s*_\s*\([\'"]([^\'"]+)[\'"]', content)
            for m in matches:
                if m.strip():
                    print(f'  TEMPLATE: {m.strip()}')

# الفحص الدقيق - البحث عن _(...) فقط
all_strings = set()
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('node_modules', '.venv', '.git', '__pycache__', '.venv', 'coverage', 'e2e')]
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                with open(path, encoding='utf-8') as fp:
                    content = fp.read()
            except:
                continue
            matches = re.findall(r'_\([\'"]([^\'"]+)[\'"]\)', content)
            for m in matches:
                if m.strip() and len(m.strip()) > 1:
                    all_strings.add(m.strip())

print(f'إجمالي سلاسل الترجمة الفريدة: {len(all_strings)}')
print()
for s in sorted(all_strings):
    print(f'  {s}')