import os, re

print("=== البحث عن نصوص المستخدم في ملفات forms ===")
forms_dir = 'forms'
if os.path.exists('forms'):
    for f in os.listdir('forms'):
        if f.endswith('.py'):
            path = os.path.join('forms', f)
            try:
                with open(path, encoding='utf-8') as fp:
                    content = fp.read()
            except:
                continue
            matches = re.findall(r'_\([\'"]([^\'"]+)[\'"]', content)
            for m in matches:
                m = m.strip()
                if len(m) > 3 and 'datetime' not in m and 'uuid' not in m:
                    print(f'forms/{f}: "{m}"')