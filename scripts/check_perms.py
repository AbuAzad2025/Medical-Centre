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
                route_match = re.search(r'@\w+_bp\.route\([\'"](.*?)[\'"]', line)
                if route_match:
                    route_path = route_match.group(1)
                    roles = []
                    for j in range(i - 1, max(-1, i - 15), -1):
                        prev = lines[j].strip()
                        if prev.startswith('@role_required_json'):
                            m = re.search(r'role_required_json\((.*?)\)', prev)
                            if m:
                                args = m.group(1)
                                roles = [
                                    r.strip().strip('\'"') for r in args.split(',') if r.strip()
                                ]
                            break
                        elif prev.startswith('@role_required'):
                            m = re.search(r'role_required\((.*?)\)', prev)
                            if m:
                                args = m.group(1)
                                roles = [
                                    r.strip().strip('\'"') for r in args.split(',') if r.strip()
                                ]
                            break
                        elif prev.startswith('@') or prev == '':
                            continue
                        else:
                            break
                    if roles:
                        routes_with_perms[route_path] = roles
            for i, line in enumerate(lines):
                m = re.search(r'@\w+\.route\([\'"](.*?)[\'"]', line)
                if m and 'bp' in line:
                    route_path = m.group(1)
                    roles = []
                    for j in range(i - 1, max(-1, i - 15), -1):
                        prev = lines[j].strip()
                        if prev.startswith('@role_required_json'):
                            m2 = re.search(r'role_required_json\((.*?)\)', prev)
                            if m2:
                                args = m2.group(1)
                                roles = [
                                    r.strip().strip('\'"') for r in args.split(',') if r.strip()
                                ]
                            break
                        elif prev.startswith('@role_required'):
                            m2 = re.search(r'role_required\((.*?)\)', prev)
                            if m2:
                                args = m2.group(1)
                                roles = [
                                    r.strip().strip('\'"') for r in args.split(',') if r.strip()
                                ]
                            break
                        elif prev.startswith('@') or prev == '':
                            continue
                        else:
                            break
                    if roles:
                        routes_with_perms[m.group(1)] = roles

print(f'Found {len(routes_with_perms)} routes with explicit permissions')
for r, roles in sorted(routes_with_perms.items()):
    print(f'{r:60} {roles}')
print()
print('Total routes in app: 755')
print(f'Routes with explicit permissions: {len(routes_with_perms)}')
print(f'Routes without explicit permissions: {755 - len(routes_with_perms)}')
