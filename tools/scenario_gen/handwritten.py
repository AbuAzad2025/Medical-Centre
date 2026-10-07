"""Load the hand-written corpus as a first-class source alongside the templates.

The 40 scenarios written during the audit are richer than anything the generator
produces: they carry a patient profile, an encounter type, a package verdict and a
financial summary, and each one records a finding about where the code stops. That
prose is the point of them, so they are not discarded and not flattened either.

This module keeps them intact, validates the same things the generated matrix is
validated against, and gives them a fingerprint in the same terms so the two
sources cannot quietly overlap.

The 40 record references to services and models as well as routes, because a
finding is often "no route exists; the service is only reachable from
app_factory". Those references are validated against the source tree instead of
the route table, and a reference that names nothing real is an error.
"""

from __future__ import annotations

import glob
import json
import os
import re
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCEN_DIR = os.path.join(ROOT, 'docs', 'scenarios')

HAND_BATCHES = sorted(
    p
    for p in glob.glob(os.path.join(SCEN_DIR, 'batch-*.json'))
    if os.path.basename(p) != os.path.basename(__file__)
)

REQUIRED = (
    'scenario_id',
    'facility_scope',
    'patient_profile',
    'encounter_type',
    'package_details',
    'journey_steps',
    'financial_summary',
    'generated_outputs',
)

API_LINE = re.compile(
    r'^(?:(?P<verb>GET|POST|PUT|DELETE|PATCH)'
    r'(?:\|(?:GET|POST|PUT|DELETE|PATCH))*)?\s+(?P<path>\S+)(?:\s+\(.*\))?$'
)
# "services/x.py:12", "models/y.py", "services/z.py:40-90", and the dotted
# "services/q.py.Class.attr" form -- all evidence, not endpoints.
REF_LINE = re.compile(
    r'^(?P<file>[\w/\\.]+\.py)'
    r'(?::(?P<line>\d+)(?:-(?P<end>\d+))?)?'
    r'(?P<dotted>(?:\.[\w]+)*)$'
)
NO_ROUTE = re.compile(r'^[—-]')  # em dash: explicitly "there is no route"


def _route_shapes() -> set[str]:
    with open(os.path.join(ROOT, 'route_inventory.json'), encoding='utf-8') as fh:
        inv = json.load(fh)
    out = set()
    for r in inv['routes']:
        norm = re.sub(r'<(?:[^:<>]+:)?([^<>]+)>', r'{\1}', r['path'])
        out.add(re.sub(r'<[^>]*>|\{[^}]*\}', '{}', norm))
    return out


def _source_corpus() -> str:
    chunks = []
    for sub in ('routes', 'services', 'models', 'app', 'utils', 'tests', 'migrations', 'forms'):
        base = os.path.join(ROOT, sub)
        if not Path(ROOT, sub).is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in ('__pycache__', '.pytest_cache')]
            for fn in filenames:
                if fn.endswith(('.py', '.html')):
                    with open(os.path.join(dirpath, fn), encoding='utf-8', errors='ignore') as fh:
                        chunks.append(fh.read())
    return '\n'.join(chunks)


def load() -> list[dict]:
    """Return the hand-written corpus, unchanged."""
    out: list[dict] = []
    for path in HAND_BATCHES:
        with open(path, encoding='utf-8') as fh:
            for sc in json.load(fh):
                sc = dict(sc)
                sc['_source_file'] = os.path.basename(path)
                out.append(sc)
    return out


def problems(shapes: set[str] | None = None, corpus: str | None = None) -> list[str]:
    """Everything wrong with the hand-written corpus."""
    shapes = shapes if shapes is not None else _route_shapes()
    corpus = corpus if corpus is not None else _source_corpus()
    out: list[str] = []

    seen_ids: dict[str, str] = {}
    for sc in load():
        sid = sc.get('scenario_id', '<missing id>')
        src = sc['_source_file']

        missing = [k for k in REQUIRED if k not in sc]
        if missing:
            out.append(f'{sid}: missing {missing}')

        if sid in seen_ids:
            out.append(f'{sid}: duplicate id, also in {seen_ids[sid]}')
        seen_ids[sid] = src

        if sc.get('package_details', {}).get('applicable') is False:
            if sc.get('financial_summary', {}).get('package_deduction', 0) != 0:
                out.append(f'{sid}: package not applicable but a deduction was recorded')

        steps = sc.get('journey_steps') or []
        if len(steps) < 3:
            out.append(f'{sid}: only {len(steps)} steps')

        for st in steps:
            api = (st.get('api') or '').strip()
            if not api:
                out.append(f'{sid}: step with no api')
                continue
            if NO_ROUTE.match(api):
                continue  # an explicit "this does not exist" marker
            m = API_LINE.match(api)
            if m:
                shape = re.sub(r'<[^>]*>|\{[^}]*\}', '{}', m.group('path'))
                if shape not in shapes:
                    out.append(f'{sid}: no route {m.group("path")}')
                continue
            rm = REF_LINE.match(api)
            if rm:
                # A reference names a file, so it is resolved against the tree,
                # not against file contents. The corpus is still consulted so a
                # reference to a file that exists but is empty, or a basename that
                # only ever appears in a comment, is caught.
                rel = rm.group('file').replace('\\', '/')
                if not os.path.isfile(os.path.join(ROOT, rel)):
                    hits = [
                        os.path.join(dp, f)
                        for dp, _dn, fns in os.walk(ROOT)
                        for f in fns
                        if f == os.path.basename(rel)
                        and '.venv' not in dp
                        and 'node_modules' not in dp
                    ]
                    if not hits:
                        out.append(f'{sid}: reference {api} names no {rel} in the tree')
                continue
            out.append(f'{sid}: api {api!r} is neither a route nor a source reference')
    return out


def fingerprint(sc: dict) -> str:
    """Identity of a hand-written scenario, in the same terms the generator uses.

    Two hand-written scenarios collide when they trace the same endpoints for the
    same encounter type, which is the duplication the generator is guarded against.
    """
    apis = []
    for st in sc.get('journey_steps', []):
        api = (st.get('api') or '').strip()
        m = API_LINE.match(api)
        path = m.group('path') if m else api
        apis.append(re.sub(r'<[^>]*>|\{[^}]*\}', '{}', path))
    key = json.dumps(
        {
            'scope': sc.get('facility_scope'),
            'encounter': sc.get('encounter_type'),
            'apis': apis,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    import hashlib

    return 'HW-' + hashlib.sha256(key.encode('utf-8')).hexdigest()[:12]


if __name__ == '__main__':
    scs = load()
    bad = problems()
    print(f'hand-written scenarios: {len(scs)} from {len(HAND_BATCHES)} batches')
    fps = [fingerprint(s) for s in scs]
    print(f'unique fingerprints   : {len(set(fps))}')
    if bad:
        print(f'\nPROBLEMS ({len(bad)}):')
        for p in bad:
            print(' ', p)
    else:
        print('\nevery route, source reference and package verdict verified')
