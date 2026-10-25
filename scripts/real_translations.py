import os, re

print('=== استخراج سلاسل الترجمة الحقيقية فقط ===')
real_strings = []

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
            # البحث عن _("text") أو _('text') - نص حقيقي فقط
            matches = re.findall(r'_\(\s*[\'"]([^\'"]{3,})[\'"]\s*\)', content)
            for m in matches:
                m = m.strip()
                # تجاهل الكلمات التقنية الشائعة
                if m.lower() not in ['datetime', 'datetime.now', 'datetime.utcnow', 'pathlib', 'contextlib', 'os', 'sys', 'json', 're', 'json', 'text', 'uuid', 'uuid4', 'uuid1', 'uuid3', 'uuid5', 'models', 'os', 'sys', 'json', 'pathlib', 'contextlib', 'botocore', 'sqlalchemy', 'pynetdicom', 'sqlalchemy.orm', 'flask', 'flask_login', 'flask_wtf', 'wtforms', 'sqlalchemy.orm', 'werkzeug', 'jinja2']:
                    if len(m) > 3:  # على الأقل 4 أحرف
                        # التحقق من أن النص يبدو كنص حقيقي (يحتوي على حروف عربية أو إنجليزية مع مسافات)
                        if re.search(r'[a-zA-Z\u0600-\u06FF].*[a-zA-Z\u0600-\u06FF]', m) or ' ' in m or any(c in m for c in '.,!?،؟'):
                            print(f'{os.path.relpath(os.path.join(root, f))}: "{m}"')