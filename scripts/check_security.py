import os, sys, re, json, ast

sys.path.insert(0, r'D:\recovers\data\medical')

os.environ.setdefault('SECRET_KEY', 'ci-test-secret-key-for-jwt-hs256-min32')
os.environ.setdefault('APP_ENV', 'testing')
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('TEST_DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test')
os.environ.setdefault('DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test')

from app_factory import create_app

app = create_app('testing')

print("=== الأمان (SECURITY) ===")

with app.app_context():
    from app.extensions import db
    from sqlalchemy import inspect, text
    
    # 1. فحص CSRF Protection
    print("\n=== حماية CSRF ===")
    csrf_routes = []
    for root, dirs, files in os.walk('routes'):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                try:
                    with open(path, encoding='utf-8') as fp:
                        content = fp.read()
                except:
                    continue
                # البحث عن مسارات POST بدون CSRF
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if '@' in line and 'route' in line and ('POST' in line or 'methods=[' in line):
                        # التحقق من وجود CSRF protection
                        has_csrf = False
                        for j in range(i-1, max(-1, i-10), -1):
                            prev = lines[j].strip()
                            if 'csrf' in prev.lower() or 'csrf' in line.lower():
                                has_csrf = True
                                break
                        # لا نطبع كل شيء، فقط نعد
    
    # بدلاً من ذلك، نتحقق من وجود CSRF protection في الكود
    print("\n=== فحص CSRF Protection في الكود ===")
    csrf_imports = 0
    csrf_exempt = 0
    for root, dirs, files in os.walk('routes'):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                try:
                    with open(path, encoding='utf-8') as fp:
                        content = fp.read()
                except:
                    continue
                if 'csrf' in content.lower() or 'CSRF' in content:
                    csrf_imports += 1
                if 'csrf_exempt' in content or 'csrf_exempt' in content:
                    csrf_exempt += 1
    
    print(f"ملفات تستخدم CSRF: {csrf_imports}")
    print(f"استخدام csrf_exempt: {csrf_exempt}")
    
    # 2. فحص SQL Injection - البحث عن استعلامات raw SQL
    print("\n=== فحص SQL Injection ===")
    raw_sql_count = 0
    text_clause_count = 0
    for root, dirs, files in os.walk('routes'):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                try:
                    with open(path, encoding='utf-8') as fp:
                        content = fp.read()
                except:
                    continue
                # البحث عن استعلامات raw
                if 'text(' in content or 'execute(' in content:
                    raw_sql_count += content.count('text(') + content.count('execute(')
                if 'text(' in content:
                    text_clause_count += content.count('text(')
    
    print(f"استخدام text() clause: {text_clause_count}")
    print(f"إجمالي استعلامات raw محتملة: {raw_sql_count}")
    
    # 3. فحص XSS - في القوالب
    print("\n=== فحص XSS في القوالب ===")
    unsafe_outputs = 0
    safe_outputs = 0
    for root, dirs, files in os.walk('templates'):
        for f in files:
            if f.endswith('.html'):
                path = os.path.join(root, f)
                try:
                    with open(path, encoding='utf-8') as fp:
                        content = fp.read()
                except:
                    continue
                # البحث عن |safe أو safe filter
                safe_outputs += content.count('|safe')
                safe_outputs += content.count('safe}')
                # البحث عن متغيرات بدون escaping
                # هذا صعب الكشف آلياً، نكتفي بالعد
    
    print(f"استخدام |safe filter: {safe_outputs}")
    
    # 4. فحص الصلاحيات (Authorization)
    print("\n=== التحقق من الصلاحيات (Authorization) ===")
    auth_checks = 0
    missing_auth = 0
    for root, dirs, files in os.walk('routes'):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                try:
                    with open(path, encoding='utf-8') as fp:
                        content = fp.read()
                except:
                    continue
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if '@' in line and 'route' in line and ('POST' in line or 'PUT' in line or 'DELETE' in line):
                        # التحقق من وجود role_required أو login_required
                        has_auth = False
                        for j in range(i-1, max(-1, i-10), -1):
                            prev = lines[j].strip()
                            if 'role_required' in prev or 'login_required' in prev:
                                has_auth = True
                                break
                        if has_auth:
                            auth_checks += 1
                        else:
                            missing_auth += 1
    
    print(f"مسارات POST/PUT/DELETE مع تحقق صلاحيات: {auth_checks}")
    print(f"مسارات POST/PUT/DELETE بدون تحقق صلاحيات: {missing_auth}")
    
    # 5. فحص تشفير البيانات الحساسة
    print("\n=== تشفير البيانات الحساسة ===")
    encrypted_fields = 0
    for root, dirs, files in os.walk('models'):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                try:
                    with open(path, encoding='utf-8') as fp:
                        content = fp.read()
                except:
                    continue
                if 'EncryptedType' in content or 'encrypted' in content.lower():
                    encrypted_fields += content.count('EncryptedType')
    
    print(f"الحقول المشفرة (EncryptedType): {encrypted_fields}")
    
    # 6. فحص Rate Limiting
    print("\n=== Rate Limiting ===")
    rate_limit_count = 0
    for root, dirs, files in os.walk('.'):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                try:
                    with open(path, encoding='utf-8') as fp:
                        content = fp.read()
                except:
                    continue
                if 'rate_limit' in content.lower() or 'ratelimit' in content.lower():
                    rate_limit_count += 1
    
    print(f"ملفات تستخدم Rate Limiting: {rate_limit_count}")
    
    # 7. فحص Content Security Policy
    print("\n=== Content Security Policy ===")
    csp_count = 0
    for root, dirs, files in os.walk('templates'):
        for f in files:
            if f.endswith('.html'):
                path = os.path.join(root, f)
                try:
                    with open(path, encoding='utf-8') as fp:
                        content = fp.read()
                except:
                    continue
                if 'csp' in content.lower() or 'content-security-policy' in content.lower():
                    csp_count += 1
    
    print(f"صفحات تستخدم CSP: {csp_count}")

if __name__ == '__main__':
    import os, sys, re, json
    
    sys.path.insert(0, r'D:\recovers\data\medical')
    os.environ.setdefault('SECRET_KEY', 'ci-test-secret-key-for-jwt-hs256-min32')
    os.environ.setdefault('APP_ENV', 'testing')
    os.environ.setdefault('FLASK_ENV', 'testing')
    os.environ.setdefault('TEST_DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test')
    os.environ.setdefault('DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test')
    
    from app_factory import create_app
    
    app = create_app('testing')
    with app.app_context():
        pass