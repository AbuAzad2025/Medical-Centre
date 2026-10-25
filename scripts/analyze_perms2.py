import json

with open('route_permissions.json', encoding='utf-8') as f:
    perms = json.load(f)

# Categorize by getting the endpoint from app.url_map
# We need to run this inside Flask app context
import sys

sys.path.insert(0, r'D:\recovers\data\medical')

from app_factory import create_app

app = create_app('testing')
with app.app_context():
    route_to_bp = {}
    for rule in app.url_map.iter_rules():
        bp = rule.endpoint.split('.')[0] if '.' in rule.endpoint else 'main'
        route_to_bp[rule.rule] = bp

    bp_counts = {}
    bp_roles = {}

    for route, roles in perms.items():
        bp = route_to_bp.get(route, 'other')
        bp_counts[bp] = bp_counts.get(bp, 0) + 1

        if bp not in bp_roles:
            bp_roles[bp] = {}
        for role in roles:
            bp_roles[bp][role] = bp_roles[bp].get(role, 0) + 1

print('Blueprint route counts:')
for bp, count in sorted(bp_counts.items(), key=lambda x: -x[1]):
    print(f'{bp:30} {count}')

print('\nRoles per blueprint:')
for bp, roles in sorted(bp_roles.items()):
    print(f'\n{bp}:')
    for role, count in sorted(roles.items(), key=lambda x: -x[1]):
        print(f'  {role}: {count}')

# Also check for routes without explicit roles
with_role = sum(1 for r in perms.values() if r != ['authenticated'])
print(f'\nTotal routes: {len(perms)}')
print(f'Routes with specific roles: {with_role}')
print(f'Routes with only login: {len(perms) - with_role}')
