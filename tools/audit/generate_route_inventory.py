"""Refresh route_inventory.json against the live application.

The inventory is a static artefact that the scenario and matrix tests read to
know which routes exist and how they are classified. Nothing in the tree
regenerated it, so a change to a route's methods left the file describing a
route that no longer existed - and a test that asserted a route was a GET
passed against the file rather than against the application.

This updates the inventory in place rather than rebuilding it. The
classification of a route is a policy decision (public, internal, admin,
super-admin, authenticated) that the file records; re-deriving it here would
quietly rewrite that judgement, and the matrix tests read it. So only three
things change:

  * the methods of a route that is registered differently now,
  * a route that exists in the application and not in the file,
  * a route that is in the file and no longer exists.

Everything else is left exactly as it was.
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

os.environ.setdefault(
    'DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test'
)
os.environ.setdefault('SECRET_KEY', 'route-inventory-generator-key-at-least-32c')
os.environ.setdefault('SKIP_PLATFORM_BOOTSTRAP', '1')

from app_factory import create_app  # noqa: E402

OUTPUT = 'route_inventory.json'

# The test harness registers these on the app it builds, so the inventory has
# to carry them too - otherwise every route the suite sees is missing and the
# coverage maths is wrong. They are registered here as stubs so the live map
# matches the one the test session builds.
TEST_ROUTES = (
    ('/test/module-error', 'trigger_module_error'),
    ('/test/module-error-html', 'trigger_module_error_html'),
    ('/test/tenant-iso-error', 'trigger_tenant_iso_error'),
    ('/test/tenant-ctx-error', 'trigger_tenant_ctx_error'),
    ('/test/perm-error', 'trigger_perm_error'),
    ('/test/idempotency-error', 'trigger_idem_error'),
    ('/test/idempotency-error-html', 'trigger_idem_error_html'),
    ('/test/g-trace', 'check_g_trace'),
    ('/test/log-trace', 'log_something'),
)


def main() -> int:
    with open(OUTPUT, encoding='utf-8') as fh:
        data = json.load(fh)
    existing = {(r['path'], r['endpoint']): r for r in data['routes']}

    app = create_app()
    live: dict[tuple[str, str], dict] = {}
    with app.app_context():
        for path, endpoint in TEST_ROUTES:
            # GET only, the way the test harness registers them.
            app.add_url_rule(path, endpoint, lambda: '', methods=['GET'])
        for rule in app.url_map.iter_rules():
            path = str(rule)
            methods = sorted(rule.methods or set())
            if path.startswith('/test/'):
                # The harness registers these for GET alone; the automatic
                # HEAD/OPTIONS are not what the file records.
                methods = ['GET']
            live[(path, rule.endpoint)] = {
                'endpoint': rule.endpoint,
                'path': path,
                'methods': methods,
            }

    changed_methods = []
    added = []
    for key, route in live.items():
        old = existing.get(key)
        if old is None:
            added.append(key)
            continue
        if sorted(old.get('methods', [])) != route['methods']:
            changed_methods.append(key)
            old['methods'] = route['methods']

    removed = [key for key in existing if key not in live]

    for key in added:
        # A new route inherits the classification of its neighbours: anything
        # under /super-admin or /owner is a platform surface, anything under
        # /auth is public, and the rest needs a session.
        path = key[0]
        if path.startswith(('/super-admin', '/owner')):
            classification = 'super-admin' if path.startswith('/super-admin') else 'admin'
        elif path.startswith('/auth'):
            classification = 'public'
        elif path.startswith('/api/'):
            classification = 'internal'
        else:
            classification = 'authenticated'
        existing[key] = {
            'endpoint': key[1],
            'path': key[0],
            'methods': live[key]['methods'],
            'classification': classification,
        }

    for key in removed:
        existing.pop(key, None)

    routes = list(existing.values())
    routes.sort(key=lambda r: (r['path'], r['endpoint']))
    data['routes'] = routes
    data['total_routes'] = len(routes)

    with open(OUTPUT, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write('\n')

    print(
        f'{OUTPUT}: {len(routes)} routes '
        f'({len(changed_methods)} method change(s), {len(added)} added, {len(removed)} removed)'
    )
    for key in changed_methods:
        print(f'  methods {key[1]}: {existing[key]["methods"]}')
    for key in added:
        print(f'  added   {key[1]}')
    for key in removed:
        print(f'  removed {key[1]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
