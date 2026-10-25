import os, re

print("=== البحث عن النصوص العربية في الكود ===")

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('node_modules', '.venv', '.git', '__pycache__', '.venv', 'coverage', 'e2e', 'scripts')]
    for f in files:
        if f.endswith(('.py', '.html', '.js', '.vue', '.ts', '.tsx', '.js', '.jsx', '.tsx')):
            path = os.path.join(root, f)
            try:
                with open(path, encoding='utf-8') as fp:
                    content = fp.read()
            except:
                continue
            # البحث عن نصوص عربية
            arabic_matches = re.findall(r'[\u0600-\u06FF]+', content)
            for m in arabic_matches:
                m = m.strip()
                if len(m) > 1:
                    print(f'{os.path.relpath(path)}: "{m.strip()}"')