import os, re

print("=== البحث عن نصوص المستخدم في ملفات forms ===")
for f in os.listdir('forms'):
    if f.endswith('.py'):
        path = os.path.join('forms', f)
        try:
            with open(path, encoding='utf-8') as fp:
                content = fp.read()
        except:
            continue
        matches = re.findall(r'[\'"]([^\'"]{3,})[\'"]', content)
        for m in matches:
            m = m.strip()
            if len(m) > 3 and ' ' in m:
                print(f'forms/{f}: "{m}"')