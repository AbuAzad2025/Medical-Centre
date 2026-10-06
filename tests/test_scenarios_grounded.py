"""Guard test: the scenario corpus must stay factually grounded in the codebase.

Every route referenced in docs/scenarios/*.json must exist in the real route
table, every backticked identifier must exist in the source tree, and no value
may contain CJK/Cyrillic/Hangul or intra-word script mixing.

Run: pytest tests/test_scenarios_grounded.py -q
"""

import glob
import json
import os
import re
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCEN_DIR = os.path.join(ROOT, 'docs', 'scenarios')
BATCHES = sorted(glob.glob(os.path.join(SCEN_DIR, 'batch-*.json')))
INVENTORY = os.path.join(ROOT, 'route_inventory.json')

REQUIRED_KEYS = (
    'scenario_id',
    'facility_scope',
    'patient_profile',
    'encounter_type',
    'package_details',
    'journey_steps',
    'financial_summary',
    'generated_outputs',
)

FOREIGN = re.compile(r'[\u0e00-\u0fff\u3000-\u9fff\uff00-\uffef\u0400-\u04ff\uac00-\ud7af]')
TEMPLATE = re.compile(r'<(?:[^:<>]+:)?([^<>]+)>|\{[^}]*\}|\.\.\.')
# "GET /x" or "POST /x (side effect)" -- a trailing parenthetical is a note,
# not part of the path.
API_LINE = re.compile(r'^(GET|POST|PUT|DELETE|PATCH)\s+(\S+)(?:\s+\(.*\))?$')
CODE_DIRS = ('routes', 'services', 'models', 'app', 'utils', 'tests', 'migrations', 'forms')
CODE_EXT = ('.py', '.html', '.ini', '.json', '.js')

# Arabic prefixes that legitimately bind to a latin token, e.g. بـreception,
# كـadd-service, and the standalone conjunction و.
AR_PREFIXES = ('بـ', 'كـ', 'و')
# Arabic LETTERS only. The naive \u0600-\u06FF block also contains Arabic
# punctuation, notably the comma U+060C, so "already_open،" would otherwise look
# like a glued word when it is simply a list separator.
ARABIC_LETTER = re.compile(r'[\u0621-\u064A\u066E-\u06D3\u06FA-\u06FF]')
GLUED = re.compile('[A-Za-z][\u0621-\u064a\u066e-\u06d3\u06fa-\u06ff]')


def _norm(path):
    return re.sub(r'<(?:[^:<>]+:)?([^<>]+)>', r'{\1}', path.strip())


def _shape(path):
    return re.sub(r'\{[^}]+\}', '{}', _norm(path))


@pytest.fixture(scope='session')
def real_paths():
    with open(INVENTORY, encoding='utf-8') as fh:
        inv = json.load(fh)
    return {_norm(r['path']) for r in inv['routes']}


@pytest.fixture(scope='session')
def source_blob():
    chunks = []
    for sub in CODE_DIRS:
        base = Path(ROOT, sub)
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in ('__pycache__', '.pytest_cache')]
            for fn in filenames:
                if fn.endswith(CODE_EXT):
                    with open(os.path.join(dirpath, fn), encoding='utf-8', errors='ignore') as fh:
                        chunks.append(fh.read())
    return '\n'.join(chunks)


@pytest.fixture(scope='session')
def corpus():
    out = {}
    for path in BATCHES:
        with open(path, encoding='utf-8') as fh:
            out[path] = json.load(fh)
    return out


def test_batches_exist():
    assert len(BATCHES) == 4, f'expected 4 scenario batches, found {len(BATCHES)}'


def test_schema_complete(corpus):
    for path, data in corpus.items():
        assert data, f'{path} is empty'
        for sc in data:
            missing = [k for k in REQUIRED_KEYS if k not in sc]
            assert not missing, f'{sc.get("scenario_id")} in {path} missing {missing}'


def test_scenario_ids_unique(corpus):
    seen = set()
    for data in corpus.values():
        for sc in data:
            sid = sc['scenario_id']
            assert sid not in seen, f'duplicate scenario_id {sid}'
            seen.add(sid)
    assert len(seen) == 40, f'expected 40 scenarios, found {len(seen)}'


def test_journeys_are_non_trivial(corpus):
    """Every scenario must assert something, not just narrate."""
    for data in corpus.values():
        for sc in data:
            assert len(sc['journey_steps']) >= 5, (
                f'{sc["scenario_id"]} has only {len(sc["journey_steps"])} steps'
            )
            fs = sc['financial_summary']
            for key in (
                'gross_total',
                'package_deduction',
                'insurance_coverage',
                'patient_out_of_pocket',
                'paid',
                'outstanding',
            ):
                assert key in fs, f'{sc["scenario_id"]} financial_summary missing {key}'
                assert isinstance(fs[key], (int, float)), (
                    f'{sc["scenario_id"]}.{key} must be numeric, got {fs[key]!r}'
                )


def test_financial_arithmetic_is_internally_consistent(corpus):
    """paid <= gross, and package_deduction cannot exceed gross."""
    for data in corpus.values():
        for sc in data:
            sid = sc['scenario_id']
            fs = sc['financial_summary']
            gross = fs['gross_total']
            paid = fs['paid']
            assert paid <= gross + 0.005, f'{sid}: paid {paid} exceeds gross_total {gross}'
            assert fs['package_deduction'] <= gross + 0.005, (
                f'{sid}: package_deduction {fs["package_deduction"]} exceeds gross {gross}'
            )
            ins = fs['insurance_coverage']
            oop = fs['patient_out_of_pocket']
            assert ins + oop <= gross + 0.05, (
                f'{sid}: insurance {ins} + out_of_pocket {oop} exceeds gross {gross}'
            )


def test_no_abandoned_package_deduction(corpus):
    """A non-applicable package must not still carry a deduction."""
    for data in corpus.values():
        for sc in data:
            if sc['package_details'].get('applicable') is False:
                assert sc['financial_summary']['package_deduction'] == 0, (
                    f'{sc["scenario_id"]}: package not applicable but a deduction was recorded'
                )


def test_every_referenced_route_exists(corpus, real_paths):
    """The core guarantee: no invented endpoints."""
    shapes = {_shape(p) for p in real_paths}
    problems = []
    for data in corpus.values():
        for sc in data:
            for step in sc['journey_steps']:
                api = step.get('api', '').strip()
                if not api or api.startswith(('—', 'services/', 'models/')):
                    continue
                m = API_LINE.match(api)
                if not m:
                    problems.append(f'{sc["scenario_id"]}: unparseable api {api!r}')
                    continue
                for one in (x.strip().strip('`') for x in m.group(2).split(',')):
                    if not one or one in ('—', '-'):
                        continue
                    norm = _norm(one)
                    if TEMPLATE.search(one):
                        if _shape(one) not in shapes:
                            problems.append(f'{sc["scenario_id"]}: no route shaped {one}')
                    elif norm not in real_paths:
                        problems.append(f'{sc["scenario_id"]}: no route {one}')
    assert not problems, 'invented endpoints:\n' + '\n'.join(problems)


def test_no_foreign_scripts(corpus):
    problems = []
    for path in corpus:
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        for lineno, line in enumerate(text.split('\n'), 1):
            hit = FOREIGN.search(line)
            if hit:
                problems.append(f'{os.path.basename(path)}:{lineno} {hit.group()!r}')
    assert not problems, 'foreign scripts present:\n' + '\n'.join(problems)


def test_no_broken_words_across_scripts(corpus):
    """Catch 'eMachineService' and 'معOverrides': latin/arabic glued mid-token."""
    problems = []
    for path in corpus:
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        for lineno, line in enumerate(text.split('\n'), 1):
            for m in GLUED.finditer(line):
                prefix = line[max(0, m.start() - 1) : m.start()]
                if prefix in AR_PREFIXES:
                    continue
                problems.append(
                    f'{os.path.basename(path)}:{lineno} '
                    f'{line[max(0, m.start() - 18) : m.end() + 18]!r}'
                )
    assert not problems, 'glued cross-script tokens:\n' + '\n'.join(problems)


def test_identifiers_exist_in_source(corpus, source_blob):
    """Every backticked identifier must resolve in the codebase."""
    problems = []
    seen = set()
    for data in corpus.values():
        for sc in data:
            for key in ('scenario_id', 'facility_scope', 'encounter_type'):
                seen.add(sc[key])
            seen.add(sc.get('title', ''))
            for step in sc['journey_steps']:
                seen.add(step.get('action', ''))
                seen.add(step.get('department', ''))
            for v in sc['generated_outputs']:
                seen.add(v)
            seen.add(sc['financial_summary'].get('ledger', ''))
    for text in seen:
        for m in re.finditer('`([A-Za-z_][A-Za-z0-9_.]*)`', text):
            ident = m.group(1)
            head = ident.split('.')[0]
            if head in source_blob or ident in source_blob:
                continue
            problems.append(f'{ident}  (in: {text[:60]!r})')
    assert not problems, 'unresolvable identifiers:\n' + '\n'.join(problems)


def test_markdown_docs_are_clean():
    problems = []
    for md in glob.glob(os.path.join(SCEN_DIR, '*.md')):
        with open(md, encoding='utf-8') as fh:
            text = fh.read()
        for lineno, line in enumerate(text.split('\n'), 1):
            hit = FOREIGN.search(line)
            if hit:
                problems.append(f'{os.path.basename(md)}:{lineno} {hit.group()!r}')
    assert not problems, 'foreign scripts in markdown:\n' + '\n'.join(problems)
