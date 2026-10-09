"""Print the path for each uncovered read-only endpoint in a named blueprint.

The read-route inventory lists endpoints; a template needs paths. Kept as a tool
so the two stay in step and a route added later shows up here immediately rather
than in a template that fails validation.
"""

from __future__ import annotations

import json
import sys

with open('route_inventory.json', encoding='utf-8') as fh:
    inv = json.load(fh)
with open('docs/scenarios/generated/read-route-inventory.json', encoding='utf-8') as fh:
    inventory = json.load(fh)

blueprints = sys.argv[1:] or list(inventory['by_blueprint'])
for blueprint in blueprints:
    wanted = set(inventory['by_blueprint'].get(blueprint, ()))
    if not wanted:
        print(f'--- {blueprint}: none')
        continue
    print(f'--- {blueprint} ({len(wanted)})')
    rows = [(r['endpoint'], r['path']) for r in inv['routes'] if r['endpoint'] in wanted]
    for endpoint, path in sorted(rows):
        print(f'  {endpoint:46} {path}')
    print()
