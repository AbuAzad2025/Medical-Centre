import os, re, json, sys

sys.path.insert(0, r'D:\recovers\data\medical')
os.environ.setdefault('SECRET_KEY', 'ci-test-secret-key-for-jwt-hs256-min32')
os.environ.setdefault('APP_ENV', 'testing')
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('TEST_DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test')
os.environ.setdefault('DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test')

# فحص المسارات غير المحمية
print('=== تحليل المسارات غير المحمية ===')
unprotected = []

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
                line_stripped = line.strip()
                # البحث عن route مع POST/PUT/DELETE
                if '@' in line_stripped and 'route' in line_stripped:
                    # التحقق من وجود POST/PUT/DELETE
                    has_mutating = False
                    if 'POST' in line_stripped or 'PUT' in line_stripped or 'DELETE' in line_stripped:
                        has_mutating = True
                    elif 'methods=' in line_stripped:
                        if 'POST' in line_stripped or 'PUT' in line_stripped or 'DELETE' in line_stripped:
                            has_mutating = True
                    
                    if has_mutating:
                        # التحقق من وجود role_required أو login_required
                        has_auth = False
                        for j in range(i-1, max(-1, i-15), -1):
                            prev = lines[j].strip()
                            if 'role_required' in prev or 'login_required' in prev:
                                has_auth = True
                                break
                        if not has_auth:
                            # البحث عن المسار
                            route_match = re.search(r'route\([\'"](.*?)[\'"]', line)
                            if route_match:
                                unprotected.append({
                                    'path': os.path.relpath(path),
                                    'route': route_match.group(1),
                                    'line': line.strip()[:100]
                                })

print(f'المسارات غير المحمية: {len(unprotected)}')
for item in unprotected[:50]:
    print(f'  {item["path"]} -> {item["route"]}')

if len(unprotected) > 50:
    print(f'  ... and {len(unprotected) - 50} more')

# تحليل حسب البلاوبرينت
print('\n=== توزيع المسارات غير المحمية حسب البلاوبرينت ===')
bp_unprotected = {}
for item in unprotected:
    bp = item['path'].split('\\')[1] if '\\' in item['path'] else item['path'].split('/')[1]
    bp_unprotected[bp] = bp_unprotected.get(bp, 0) + 1

for bp, count in sorted(bp_unprotected.items(), key=lambda x: -x[1]):
    print(f'  {bp}: {count}')