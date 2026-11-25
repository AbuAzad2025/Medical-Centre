"""Build the comprehensive page/route inventory for the visual audit.

Reads route_inventory.json (the live-app-derived route list) and maps each
route to a product module via MODULE_ROUTE_MAP / CORE_BLUEPRINTS, then to the
role that normally operates that module. Output is consumed by the walkthrough
script and by docs/PAGE_AUDIT/inventory.md.
"""

import collections
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from app.core.module_route_map import CORE_BLUEPRINTS, MODULE_ROUTE_MAP  # noqa: E402

BLUEPRINT_MODULE = {}
for module, info in MODULE_ROUTE_MAP.items():
    for bp in info['blueprints']:
        BLUEPRINT_MODULE[bp] = module
    for prefix in info['prefixes']:
        BLUEPRINT_MODULE['prefix:' + prefix] = module

MODULE_ROLE = {
    'reception': 'reception',
    'doctor': 'doctor',
    'lab': 'lab',
    'radiology': 'radiology',
    'pharmacy': 'pharmacist',
    'emergency': 'emergency',
    'nursing': 'nurse',
    'billing': 'accountant',
    'inventory': 'technician',
    'appointments': 'reception',
    'reporting': 'manager',
    'owner': 'super_admin',
    'portal': 'patient',
    'ai_imaging': 'doctor',
    'integration': 'super_admin',
}

CORE_ROLE = {
    'main': 'any',
    'auth': 'any',
    'security': 'any',
    'mfa': 'any',
    'backup': 'super_admin',
    'backup_restore': 'super_admin',
    'biometric': 'any',
    'api': 'any',
    'test': 'any',
    'static': 'any',
    'health': 'any',
}


def module_for(route):
    bp = route['endpoint'].split('.')[0]
    if bp in BLUEPRINT_MODULE:
        return BLUEPRINT_MODULE[bp]
    path = route['path']
    for prefix, module in BLUEPRINT_MODULE.items():
        if prefix.startswith('prefix:') and path.startswith(prefix[7:]):
            return module
    if bp in CORE_BLUEPRINTS:
        return 'core:' + bp
    return 'uncategorized:' + bp


def role_for(route, module):
    if module.startswith('core:'):
        return CORE_ROLE.get(module[5:], 'any')
    if module.startswith('uncategorized:'):
        bp = module[14:]
        return CORE_ROLE.get(bp, 'any')
    return MODULE_ROLE.get(module, 'any')


def main():
    with open(os.path.join(ROOT, 'route_inventory.json'), encoding='utf-8') as fh:
        data = json.load(fh)

    items = []
    for route in data['routes']:
        module = module_for(route)
        items.append(
            {
                'path': route['path'],
                'endpoint': route['endpoint'],
                'methods': route['methods'],
                'classification': route['classification'],
                'module': module,
                'role': role_for(route, module),
                'is_get': 'GET' in route['methods'],
                'is_api': route['path'].startswith('/api/')
                or '/api/' in route['path']
                or route['endpoint'].startswith('api_'),
            }
        )

    os.makedirs(os.path.join(ROOT, 'docs', 'PAGE_AUDIT'), exist_ok=True)
    out = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'inventory.json')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump({'total': len(items), 'routes': items}, fh, ensure_ascii=False, indent=2)
        fh.write('\n')

    by_module = collections.Counter(i['module'] for i in items)
    by_role = collections.Counter(i['role'] for i in items if i['is_get'])
    print(f'routes={len(items)} get={sum(i["is_get"] for i in items)}')
    print('\nBY MODULE:')
    for m, n in by_module.most_common():
        print(f'  {m:28} {n}')
    print('\nGET ROUTES BY ROLE:')
    for r, n in by_role.most_common():
        print(f'  {r:28} {n}')
    print(f'\nwrote {out}')


if __name__ == '__main__':
    main()
