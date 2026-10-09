"""List the state-changing routes no scenario reaches, with their blueprint.

Used when the read templates are regenerated: adding read journeys can quietly
stop mentioning a write route that an earlier template covered, and the
state-changing coverage number drops without anything looking wrong. Printing the
endpoint as well as the path is what makes that findable.
"""

from __future__ import annotations

import glob
import json
import re
import sys

API = re.compile(r'^\s*(?:GET|POST|PUT|PATCH|DELETE)\s+(\S+)')


def shape(path: str) -> str:
    named = re.sub(r'<(?:[^:<>]+:)?([^<>]+)>', r'{\1}', path)
    return re.sub(r'<[^>]*>|\{[^}]*\}', '{}', named)


def main() -> None:
    with open('route_inventory.json', encoding='utf-8') as fh:
        inv = json.load(fh)

    covered: set[str] = set()
    for path in glob.glob('docs/scenarios/generated/scenarios*.json') + glob.glob(
        'docs/scenarios/batch-*.json'
    ):
        with open(path, encoding='utf-8') as fh:
            for sc in json.load(fh):
                for step in sc['journey_steps']:
                    m = API.match(step['api'])
                    if m:
                        covered.add(shape(m.group(1)))

    only_mutating = '--reads' not in sys.argv
    missing = []
    for r in inv['routes']:
        methods = set(r['methods']) & {'POST', 'PUT', 'DELETE', 'PATCH'}
        if not methods or (only_mutating is False and not methods):
            continue
        if not only_mutating and {'GET', 'HEAD', 'OPTIONS'} & set(r['methods']):
            continue
        if shape(r['path']) not in covered:
            missing.append(('/'.join(sorted(methods)), r['endpoint'], r['path']))

    print(f'uncovered {"state-changing" if only_mutating else "read-only"} routes: {len(missing)}')
    for methods, endpoint, path in sorted(missing, key=lambda t: t[1]):
        print(f'  {methods:20} {endpoint:46} {path}')


if __name__ == '__main__':
    main()
