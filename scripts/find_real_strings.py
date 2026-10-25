import os, re

print('=== استخراج سلاسل الترجمة الحقيقية ===')
strings_found = []

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
                if len(m) > 2 and not m.startswith('api auth/rate-limit'):
                    # تجاهل الكلمات التقنية الشائعة
                    tech_words = ['datetime', 'pathlib', 'contextlib', 'os', 'sys', 'json', 're', 'datetime', 'uuid', 'uuid4', 'models', 'os', 'sys', 'json', 're', 'text', 'pathlib', 'contextlib', 'botocore', 'sqlalchemy', 'pynetdicom', 'flask', 'flask_login', 'flask_wtf', 'wtforms', 'sqlalchemy.orm', 'werkzeug', 'jinja2']
                    if m.lower() not in tech_words and len(m) > 3:
                        # تحقق من أن النص يبدو كنص حقيقي
                        if re.search(r'[a-zA-Z\u0600-\u06FF].*[a-zA-Z\u0600-\u06FF]', m) or ' ' in m or any(c in m for c in '.,!?،؟'):
                            print(f'{os.path.relpath(os.path.join(root, f))}: "{m}"')