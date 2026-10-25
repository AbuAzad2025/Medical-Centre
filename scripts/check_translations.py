import os, re, json, sys

# فحص شامل للترجمة واللغة
print("=== تدقيق شامل للترجمة واللغة ===")

# 1. استخراج جميع سلاسل الترجمة من ملفات Python
all_strings = []
string_locations = {}

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
            # البحث عن _('text') patterns
            matches = re.findall(r"_\([\'\"]([^\'\"]+)[\'\"]", content)
            for m in matches:
                if m not in string_locations:
                    string_locations[m] = []
                string_locations[m].append(os.path.relpath(os.path.join(root, f)))

# 2. فحص القوالب
print('=== سلاسل الترجمة في القوالب ===')
for root, dirs, files in os.walk('templates'):
    for f in files:
        if f.endswith('.html'):
            path = os.path.join(root, f)
            try:
                with open(path, encoding='utf-8') as fp:
                    content = fp.read()
            except:
                continue
            matches = re.findall(r'\{\{\s*_\s*\([\'\"]([^\'\"]+)[\'\"]', content)
            for m in matches:
                print(f'  TEMPLATE: {m}')

# 1. استخراج جميع سلاسل الترجمة
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
            matches = re.findall(r"_\([\'\"]([^\'\"]+)[\'\"]", content)
            for m in matches:
                if m.strip():
                    all_strings.add(m.strip())

# 2. فحص القوالب
for root, dirs, files in os.walk('templates'):
    for f in files:
        if f.endswith('.html'):
            path = os.path.join(root, f)
            try:
                with open(path, encoding='utf-8') as fp:
                    content = fp.read()
            except:
                continue
            matches = re.findall(r'\{\{\s*_\s*\([\'\"]([^\'\"]+)[\'\"]', content)
            for m in matches:
                if m.strip():
                    all_strings.add(m.strip())

print(f'إجمالي سلاسل الترجمة الفريدة: {len(all_strings)}')
print()
print('=== جميع سلاسل الترجمة ===')
for s in sorted(all_strings):
    print(f'  {s}')