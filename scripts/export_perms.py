import json
import os
import re

routes_with_perms = {}

for root, _dirs, files in os.walk('routes'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                with open(path, encoding='utf-8') as fp:
                    content = fp.read()
            except Exception:
                continue
            lines = content.split('\n')
            for i, line in enumerate(lines):
                m = re.search(r'@\w+_bp\.route\([\'"](.*?)[\'"]', line)
                if m:
                    route_path = m.group(1)
                    roles = []
                    for j in range(i + 1, min(i + 15, len(lines))):
                        next_line = lines[j].strip()
                        if next_line.startswith('@role_required_json'):
                            m2 = re.search(r'role_required_json\((.*?)\)', next_line)
                            if m2:
                                args = m2.group(1)
                                roles = [
                                    r.strip().strip('\'"') for r in args.split(',') if r.strip()
                                ]
                            break
                        elif next_line.startswith('@role_required'):
                            m2 = re.search(r'role_required\((.*?)\)', next_line)
                            if m2:
                                args = m2.group(1)
                                roles = [
                                    r.strip().strip('\'"') for r in args.split(',') if r.strip()
                                ]
                            break
                        elif next_line.startswith('@login_required'):
                            pass
                        elif next_line.startswith('def '):
                            break
                        elif next_line == '':
                            continue
                    if roles:
                        routes_with_perms[route_path] = roles
                    else:
                        routes_with_perms[route_path] = ['authenticated']

with open('route_permissions.json', 'w', encoding='utf-8') as f:
    json.dump(routes_with_perms, f, ensure_ascii=False, indent=2)

print(f'Total routes: {len(routes_with_perms)}')
with_role = len([r for r, roles in routes_with_perms.items() if roles != ['authenticated']])
print(f'Routes with specific roles: {with_role}')
print(f'Routes with only login: {len(routes_with_perms) - with_role}')
