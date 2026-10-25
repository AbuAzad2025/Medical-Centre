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
                line_stripped = line.strip()
                # Match @xxx_bp.route('/path')
                m = re.search(r'@\w+_bp\.route\([\'"](.*?)[\'"]', line)
                if m:
                    route_path = m.group(1)
                    # Look FORWARD for decorators (after route, before def)
                    roles = []
                    has_login = False
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
                            pass  # continue looking
                        elif next_line.startswith('@'):
                            continue
                        elif next_line.startswith('def '):
                            break
                        elif next_line == '':
                            continue
                    if roles:
                        routes_with_perms[route_path] = roles
                    else:
                        routes_with_perms[route_path] = ['authenticated']

print(f'Found {len(routes_with_perms)} routes with permissions')
# Group by roles
role_groups = {}
for r, roles in sorted(routes_with_perms.items()):
    key = ','.join(sorted(roles))
    if key not in role_groups:
        role_groups[key] = []
    role_groups[key].append(r)

for roles, routes in sorted(role_groups.items()):
    print(f'\n=== Roles: {roles} ({len(routes)} routes) ===')
    for r in sorted(routes)[:10]:
        print(f'  {r}')
    if len(routes) > 10:
        print(f'  ... and {len(routes) - 10} more')

print()
print(f'Total routes analyzed: {len(routes_with_perms)}')
with_role = len([r for r, roles in routes_with_perms.items() if roles != ['authenticated']])
print(f'Routes with specific roles: {with_role}')
print(f'Routes with only login: {len(routes_with_perms) - with_role}')
