"""Inventory the read-only routes the matrix does not reach yet.

Read-only routes were out of scope when the matrix started: a GET cannot corrupt
anything, so the risk it carries is showing the wrong thing rather than breaking
the system. That is a real risk in a clinical system, and 354 of them are
undocumented.

This groups them by blueprint so the templates can be written area by area rather
than as one undifferentiated list, and prints the shape each cluster needs: a
read journey still has to be a journey, not a single GET, so each group has to
supply at least three steps that a clinician or operator actually performs.
"""

from __future__ import annotations

import collections
import glob
import json
import re

API = re.compile(r'^\s*(?:GET|POST|PUT|PATCH|DELETE)\s+(\S+)')


def shape(path: str) -> str:
    named = re.sub(r'<(?:[^:<>]+:)?([^<>]+)>', r'{\1}', path)
    return re.sub(r'<[^>]*>|\{[^}]*\}', '{}', named)


def main() -> None:
    with open('route_inventory.json', encoding='utf-8') as fh:
        inv = json.load(fh)

    covered: set[str] = set()
    # Excluded deliberately: the inventory this script writes lives in the same
    # directory as the matrix and is not itself a list of scenarios. Globbing it
    # in makes every iteration below read a string where a dict was expected.
    for path in glob.glob('docs/scenarios/generated/scenarios*.json') + glob.glob(
        'docs/scenarios/batch-*.json'
    ):
        with open(path, encoding='utf-8') as fh:
            for sc in json.load(fh):
                for step in sc['journey_steps']:
                    m = API.match(step['api'])
                    if m:
                        covered.add(shape(m.group(1)))

    read_only: dict[str, str] = {}
    for r in inv['routes']:
        methods = set(r['methods']) & {'GET', 'HEAD', 'OPTIONS'}
        if not methods or {'POST', 'PUT', 'DELETE', 'PATCH'} & set(r['methods']):
            continue
        sh = shape(r['path'])
        if sh in covered:
            continue
        read_only[sh] = r['endpoint']

    by_blueprint: dict[str, list[str]] = collections.defaultdict(list)
    for endpoint in read_only.values():
        by_blueprint[endpoint.split('.')[0]].append(endpoint)

    print(f'uncovered read-only routes: {len(read_only)}\n')
    for blueprint in sorted(by_blueprint, key=lambda b: -len(by_blueprint[b])):
        routes = sorted(by_blueprint[blueprint])
        print(f'{blueprint} ({len(routes)})')
        for r in routes:
            print(f'    {r}')
        print()

    with open('docs/scenarios/generated/read-route-inventory.json', 'w', encoding='utf-8') as fh:
        json.dump(
            {
                'uncovered_read_routes': len(read_only),
                'by_blueprint': {k: sorted(v) for k, v in sorted(by_blueprint.items())},
            },
            fh,
            indent=1,
        )
        fh.write('\n')
    print('wrote docs/scenarios/generated/read-route-inventory.json')


if __name__ == '__main__':
    main()
