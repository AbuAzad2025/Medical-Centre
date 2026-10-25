import os, re

print('=== جميع سلاسل _() في الكود ===')
strings = []

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
                if len(m) > 2:
                    print(f'{os.path.relpath(path)}: "{m}"')