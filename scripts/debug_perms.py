import re

# Test on a specific file to debug
path = 'routes/reception/api.py'
with open(path, encoding='utf-8') as fp:
    content = fp.read()

lines = content.split('\n')
for i, line in enumerate(lines):
    line_stripped = line.strip()
    # Match @xxx_bp.route('/path')
    m = re.search(r'@\w+_bp\.route\([\'"](.*?)[\'"]', line)
    if m:
        route_path = m.group(1)
        print(f'Route: {route_path} at line {i + 1}')
        # Look backwards for ALL decorators
        for j in range(i - 1, max(-1, i - 25), -1):
            prev = lines[j].strip()
            if prev.startswith('@role_required_json'):
                print(f'  @role_required_json found at line {j + 1}: {prev}')
                m2 = re.search(r'role_required_json\((.*?)\)', prev)
                if m2:
                    args = m2.group(1)
                    roles = [r.strip().strip('\'"') for r in args.split(',') if r.strip()]
                    print(f'  Roles: {roles}')
            print()
