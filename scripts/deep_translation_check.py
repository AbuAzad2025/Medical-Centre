import os, re

print('=== البحث العميق عن سلاسل الترجمة ===')
all_strings = []

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
            # البحث عن _("...") و _('...') مع إمكانية وجود مسافات
            matches = re.findall(r'_\(\s*[\'"]([^\'"]+)[\'"]\s*\)', content)
            for m in matches:
                if m.strip():
                    print(f'{os.path.relpath(path)}: {m.strip()}')