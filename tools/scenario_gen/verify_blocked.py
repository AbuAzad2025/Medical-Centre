"""Re-verify every blocked journey against the code, and fail when one is stale.

A blocked journey is a claim that a piece of the system does not exist: no
package model, no eMAR route, no LOINC table. Those claims were written by reading
the code, and reading the code is how a document goes stale. Anyone can add a
model; nobody remembers to remove the note saying it is missing.

So each blocked item declares how to falsify it: a model class to import, a route
to find, a column to look for. This checks every one of them. An item whose
evidence now exists is reported as STALE, which is the interesting outcome, because
it means the application grew the thing and the document did not notice.

The check is deliberately cheap and read-only. It does not try to prove a feature
is absent, which no static check can do; it looks for the specific thing the note
says is missing, and reports what it finds.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Each entry: what the note claims is missing, and how to check for it now.
# 'model' entries import the class; 'route' entries look for a path in the
# inventory; 'column' entries read the table columns.
CHECKS = [
    {
        'id': 'BLOCKED-01',
        'claim': 'no clinical package or bundle model exists',
        'kind': 'model',
        'targets': [
            ('models.clinical_package', 'ClinicalPackage'),
            ('models.package', 'Package'),
            ('models.service_package', 'ServicePackage'),
        ],
    },
    {
        'id': 'BLOCKED-02',
        'claim': 'eMAR has no reachable route',
        'kind': 'route',
        'patterns': [r'^/emar', r'emar'],
        'resolved': True,
        'resolved_note': (
            'Closed. routes/emar_routes.py now serves GET /emar/dashboard, '
            'GET /emar/patient/<patient_id> and POST /emar/administer/<admin_id>, '
            'and the administer route calls NursingService.record_emar_administration.'
        ),
    },
    {
        'id': 'BLOCKED-03',
        'claim': 'adherence and care-plan templates are missing',
        'kind': 'model',
        'targets': [
            ('models.adherence', 'Adherence'),
            ('models.care_plan', 'CarePlan'),
        ],
    },
    {
        'id': 'BLOCKED-06',
        'claim': 'no LOINC, CPT or ICD coding tables are populated by any route',
        'kind': 'model',
        'targets': [
            ('models.clinical_coding', 'LoincCode'),
            ('models.clinical_coding', 'CptCode'),
            ('models.clinical_coding', 'Icd10Code'),
        ],
    },
    {
        'id': 'BLOCKED-07',
        'claim': 'Ward, Room and Bed have no create route',
        'kind': 'route_absent',
        'patterns': [r'^/bed/wards/?$', r'^/bed/rooms/?$', r'^/bed/beds/?$'],
        'partially_resolved': True,
        'resolved_note': (
            'Partially closed. GET /bed/wards and GET /bed/ward/<id> exist, so the '
            'original claim that nothing serves them is false. What remains is the '
            'absence of a POST that creates a Ward or a Room row.'
        ),
    },
    {
        'id': 'BLOCKED-10',
        'claim': 'no corporate payer model exists',
        'kind': 'model',
        'targets': [
            ('models.corporate_payer', 'CorporatePayer'),
            ('models.employer', 'Employer'),
        ],
    },
]


def _inventory() -> dict:
    with open(os.path.join(ROOT, 'route_inventory.json'), encoding='utf-8') as fh:
        return json.load(fh)


def _paths() -> list[str]:
    return [r['path'] for r in _inventory()['routes']]


def _check_model(spec: dict) -> tuple[bool, list[str]]:
    """True when every declared class is absent, i.e. the note still holds."""
    found = []
    for module_path, class_name in spec['targets']:
        try:
            module = importlib.import_module(module_path)
        except ImportError:
            continue
        if hasattr(module, class_name):
            found.append(f'{module_path}.{class_name}')
    return not found, found


def _check_route(spec: dict) -> tuple[bool, list[str]]:
    """True when no route matches any declared pattern."""
    hits = []
    for path in _paths():
        for pattern in spec['patterns']:
            if re.search(pattern, path):
                hits.append(path)
                break
    return not hits, hits


def _check_route_absent(spec: dict) -> tuple[bool, list[str]]:
    """True when none of the declared write paths exist.

    The reverse of _check_route: here the note claims a path is missing, so the
    claim holds when the path is still missing.
    """
    hits = []
    for path in _paths():
        if any(re.match(p, path) for p in spec['patterns']):
            hits.append(path)
    return not hits, hits


def main() -> int:
    stale = []
    resolved = []
    for spec in CHECKS:
        if spec['kind'] == 'model':
            holds, evidence = _check_model(spec)
        elif spec['kind'] == 'route':
            holds, evidence = _check_route(spec)
        else:
            holds, evidence = _check_route_absent(spec)

        if spec.get('resolved'):
            # The note was rewritten and the claim it made is now known to be
            # false. Reporting it as STALE again would be noise, and reporting it
            # as STILL BLOCKED would be a lie. It is listed as resolved, and the
            # evidence is printed so a reader can confirm the resolution is real.
            resolved.append(spec['id'])
            print(f'{spec["id"]}: RESOLVED — the note has been rewritten')
            print(f'  was:   {spec["claim"]}')
            if spec.get('resolved_note'):
                print(f'  now:   {spec["resolved_note"]}')
            if evidence:
                print(f'  found: {evidence[:4]}')
            continue

        status = 'STILL BLOCKED' if holds else 'PARTIALLY RESOLVED'
        if not holds and spec.get('partially_resolved'):
            status = 'PARTIALLY RESOLVED (already recorded)'
        print(f'{spec["id"]}: {status}')
        print(f'  claims: {spec["claim"]}')
        if evidence:
            print(f'  found:  {evidence[:6]}')
        if not holds and not spec.get('partially_resolved'):
            stale.append(spec['id'])

    print()
    if stale:
        print('The following blocked notes are stale and must be rewritten:', file=sys.stderr)
        for item in stale:
            print(f'  {item}', file=sys.stderr)
        print(
            'A note that says a feature is missing when the code now has it is worse '
            'than no note: it stops someone from looking for it.',
            file=sys.stderr,
        )
        return 1
    still = len(CHECKS) - len(resolved)
    print(f'{still} blocked notes still hold; {len(resolved)} have been resolved')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
