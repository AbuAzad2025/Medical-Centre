#!/usr/bin/env python
"""
OpenAPI Specification Generator for Medical Centre Platform

Generates an OpenAPI 3.0 specification from the Flask route inventory that
``tools/scenario_gen`` already produces, so the published contract cannot drift
from the routes the application actually registers.

Design constraints:

* No third-party dependency. The inventory is JSON and the target is JSON, so
  the stdlib is sufficient and the generator keeps working in CI without a new
  requirement being installed.
* Every registered operation is emitted, including GET. A contract that only
  describes mutating endpoints is not a contract for this API.
* No invented parameters. Path parameters are derived from the real route rule.
  Query parameters are *not* guessed, because a guessed contract is worse than
  an absent one: it advertises behaviour the server does not have.

Usage::

    python tools/openapi/generate_openapi.py [--output PATH] [--check]

``--check`` regenerates in memory and exits non-zero when the committed spec
drifts from the route inventory, which is what CI should call.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / 'docs' / 'openapi.json'
INVENTORY_PATH = ROOT / 'route_inventory.json'

# Flask rule syntax -> OpenAPI path template syntax.
CONVERTER_RE = re.compile(r'<(?:[^:<>]+:)?([^<>]+)>')

# Methods that are transport-level aliases rather than distinct operations.
SKIPPED_METHODS = frozenset({'HEAD', 'OPTIONS', 'TRACE'})

# Endpoints that exist in the inventory but are not part of the production API
# surface, and so must not be advertised to consumers of the published contract.
#
# `/static/<path:filename>` is Flask's asset route, not an API endpoint.
# `/test/*` are error-injection diagnostics registered by tests/conftest.py; they
# only exist when the app runs under TestingConfig. Verified against the live
# url_map: 0 live operations are missing from the inventory, but these 10 were
# inventory entries with no production counterpart.
NON_PRODUCTION_PREFIXES = ('/static/', '/test/')

ERROR_RESPONSES: dict[str, str] = {
    '400': 'Bad request',
    '401': 'Unauthorized',
    '403': 'Forbidden',
    '404': 'Not found',
    '422': 'Unprocessable entity',
    '500': 'Internal server error',
}


def normalize_path(path: str) -> str:
    """Convert a Flask rule to an OpenAPI path template."""
    return CONVERTER_RE.sub(r'{\1}', path)


def path_parameters(path: str) -> list[dict[str, Any]]:
    """Derive path parameters from the route rule itself."""
    return [
        {
            'name': name,
            'in': 'path',
            'required': True,
            'schema': {'type': 'string'},
            'description': f'Path parameter `{name}`.',
        }
        for name in re.findall(r'\{([^}]+)\}', path)
    ]


def build_operation(method: str, path: str, route: dict[str, Any]) -> dict[str, Any]:
    """Build one OpenAPI operation object from an inventory route entry."""
    endpoint = route.get('endpoint') or 'unknown'
    blueprint = route.get('blueprint') or 'unknown'
    docstring = (route.get('doc') or '').strip()

    operation: dict[str, Any] = {
        'tags': [blueprint],
        'operationId': f'{method.lower()}_{endpoint}',
        'summary': docstring.splitlines()[0]
        if docstring
        else endpoint.replace('_', ' ').capitalize(),
        'parameters': path_parameters(path),
        'responses': {
            '200': {'description': 'Successful response'},
            **{code: {'description': text} for code, text in ERROR_RESPONSES.items()},
        },
    }

    if docstring:
        operation['description'] = docstring

    # HEAD/OPTIONS are skipped above; a mutating operation may carry a body.
    if method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        operation['requestBody'] = {
            'required': False,
            'content': {'application/json': {'schema': {'type': 'object'}}},
        }

    operation['security'] = [{'BearerAuth': []}]
    return operation


def generate_spec(inventory: dict[str, Any]) -> dict[str, Any]:
    """Assemble the full OpenAPI 3.0 document."""
    paths: dict[str, dict[str, Any]] = {}

    for route in inventory.get('routes', []):
        raw_path = route.get('path')
        if not raw_path:
            continue
        if raw_path.startswith(NON_PRODUCTION_PREFIXES):
            continue

        path = normalize_path(raw_path)
        bucket = paths.setdefault(path, {})

        for method in route.get('methods', []):
            method = method.upper()
            if method in SKIPPED_METHODS:
                continue
            bucket[method.lower()] = build_operation(method, path, route)

    # Drop paths that ended up with no real operation.
    paths = {p: ops for p, ops in paths.items() if ops}

    return {
        'openapi': '3.0.3',
        'info': {
            'title': 'Medical Centre Platform API',
            'version': '1.0.0',
            'description': 'REST surface generated from the Flask route inventory.',
            'license': {'name': 'Proprietary'},
        },
        'servers': [{'url': '/', 'description': 'Current host'}],
        'components': {
            'securitySchemes': {
                'BearerAuth': {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'},
                'ApiKeyAuth': {'type': 'apiKey', 'in': 'header', 'name': 'X-API-Key'},
            }
        },
        'security': [{'BearerAuth': []}, {'ApiKeyAuth': []}],
        'paths': dict(sorted(paths.items())),
    }


def load_inventory() -> dict[str, Any]:
    if not INVENTORY_PATH.exists():
        return {}
    return json.loads(INVENTORY_PATH.read_text(encoding='utf-8'))


def count_operations(spec: dict[str, Any]) -> int:
    return sum(len(ops) for ops in spec.get('paths', {}).values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        '--check',
        action='store_true',
        help='Verify the committed spec matches the inventory without writing it.',
    )
    args = parser.parse_args()

    inventory = load_inventory()
    if not inventory:
        print(f'Error: route inventory not found at {INVENTORY_PATH}', file=sys.stderr)
        return 1

    spec = generate_spec(inventory)
    serialized = json.dumps(spec, indent=2, ensure_ascii=False) + '\n'

    if args.check:
        if not args.output.exists():
            print(f'Error: {args.output} does not exist', file=sys.stderr)
            return 1
        if args.output.read_text(encoding='utf-8') != serialized:
            print(f'Error: {args.output} is stale; regenerate it.', file=sys.stderr)
            return 1
        print(f'{args.output} is up to date.')
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    # newline='\n' so the committed artefact matches byte-for-byte on any host;
    # otherwise git's CRLF normalisation would make --check fail in CI.
    args.output.write_text(serialized, encoding='utf-8', newline='\n')

    print(f'OpenAPI spec written to {args.output}')
    print(f'Paths: {len(spec["paths"])}')
    print(f'Operations: {count_operations(spec)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
