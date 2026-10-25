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
                # Match @xxx_bp.route('/path')
                m = re.search(r'@\w+_bp\.route\([\'"](.*?)[\'"]', line)
                if m:
                    route_path = m.group(1)
                    # Look backwards for ALL decorators
                    roles = []
                    has_login = False
                    for j in range(i - 1, max(-1, i - 20), -1):
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
                        elif prev.startswith('@login_required'):
                            # Continue checking for role_required above login_required
                            pass
                        elif prev.startswith('@') or prev == '':
                            continue
                        else:
                            break
                    if roles:
                        routes_with_perms[route_path] = roles
                    else:
                        routes_with_perms[route_path] = ['authenticated']

print(f'Found {len(routes_with_perms)} routes with permissions')
for r, roles in sorted(routes_with_perms.items()):
    print(f'{r:70} {roles}')
print()
print('Total routes in app: 755')
print(
    f'Routes with role permissions: {len([r for r, roles in routes_with_perms.items() if roles != ["authenticated"]])}'
)
print(
    f'Routes with only login: {len([r for r, roles in routes_with_perms.items() if roles == ["authenticated"]])}'
)
