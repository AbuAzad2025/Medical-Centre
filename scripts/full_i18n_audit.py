import os, re, json

print("=================================================================")
print("تقرير تدقيق الترجمة واللغة الشامل (I18n Audit)")
print("=================================================================")

# 1. جمع جميع سلاسل الترجمة
strings = []
template_strings = []

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
            matches = re.findall(r'_\(\s*[\'"]([^\'"]+)[\'\"]\s*\)', content)
            for m in matches:
                m = m.strip()
                if len(m) > 2:
                    print(f'{os.path.relpath(path)}: "{m}"')

# القوالب
print('\n=== القوالب ===')
for root, dirs, files in os.walk('templates'):
    for f in files:
        if f.endswith('.html'):
            path = os.path.join(root, f)
            try:
                with open(path, encoding='utf-8') as fp:
                    content = fp.read()
            except:
                continue
            matches = re.findall(r'\{\{\s*_\s*\([\'\"]([^\'\"]+)[\'\"]\s*\)\s*\}\}', content)
            for m in matches:
                m = m.strip()
                if m:
                    print(f'{os.path.relpath(path)}: "{m}"')

# 2. فحص gettext/lazy_gettext
print('\n=== lazy_gettext / gettext / lazy_pgettext ===')
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
            matches = re.findall(r'(lazy_gettext|gettext|lazy_pgettext)\(\s*[\'\"]([^\'\"]+)[\'\"]', content)
            for m in matches:
                print(f'{os.path.relpath(path)}: {m[0]}(\"{m[1]}\")')