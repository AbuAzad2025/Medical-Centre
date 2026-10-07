"""Guard the generated matrix: no duplication, no invented endpoints, no fiction.

Three things can silently go wrong in a generated matrix, and each has caught a
real bug here already:

  - a template referencing a route the application does not serve, which is how
    seven invented endpoints survived the hand-written corpus;
  - the same journey emitted twice under different names, which makes a matrix
    look larger than it is;
  - axis values that drifted from the code, because a generator and its source
    can disagree after a rename.

So the checks read the same sources the generator reads, and the generator is
re-run inside the test rather than trusting the committed JSON.
"""

from __future__ import annotations

import collections
import glob
import itertools
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN_DIR = os.path.join(ROOT, 'tools', 'scenario_gen')
GEN_OUT = os.path.join(ROOT, 'docs', 'scenarios', 'generated')

sys.path.insert(0, GEN_DIR)

from dimensions import build_dimensions  # noqa: E402
from generate import generate  # noqa: E402

from templates import TEMPLATES, all_problems  # noqa: E402

GENERATED = sorted(glob.glob(os.path.join(GEN_OUT, '*.json')))
API_LINE = re.compile(
    r'^(?:(?:GET|POST|PUT|DELETE|PATCH)(?:\|(?:GET|POST|PUT|DELETE|PATCH))*)?\s+(\S+)$'
)

FOREIGN = re.compile(r'[\u0e00-\u0fff\u3000-\u9fff\uff00-\uffef\u0400-\u04ff\uac00-\ud7af]')
GLUED = re.compile('[A-Za-z][\u0621-\u064a\u066e-\u06d3\u06fa-\u06ff]')
AR_PREFIXES = ('بـ', 'كـ', 'و')


@pytest.fixture(scope='session')
def route_shapes():
    with open(os.path.join(ROOT, 'route_inventory.json'), encoding='utf-8') as fh:
        inv = json.load(fh)
    shapes = set()
    for r in inv['routes']:
        norm = re.sub(r'<(?:[^:<>]+:)?([^<>]+)>', r'{\1}', r['path'])
        shapes.add(re.sub(r'<[^>]*>|\{[^}]*\}', '{}', norm))
    return shapes


@pytest.fixture(scope='session')
def corpus():
    out = {}
    for p in GENERATED:
        with open(p, encoding='utf-8') as fh:
            out[p] = json.load(fh)
    return out


def test_generator_produces_output():
    assert GENERATED, 'no generated matrix found; run tools/scenario_gen/generate.py'


def test_every_template_is_valid():
    problems = all_problems()
    assert not problems, (
        'templates reference routes or enum members that do not exist:\n' + '\n'.join(problems)
    )


def test_generated_routes_exist(corpus, route_shapes):
    problems = []
    for scenarios in corpus.values():
        for sc in scenarios:
            for step in sc['journey_steps']:
                m = API_LINE.match(step['api'])
                assert m, f'{sc["scenario_id"]}: unparseable api {step["api"]!r}'
                shape = re.sub(r'<[^>]*>|\{[^}]*\}', '{}', m.group(1))
                if shape not in route_shapes:
                    problems.append(f'{sc["scenario_id"]}: no route {m.group(1)}')
    assert not problems, 'invented endpoints:\n' + '\n'.join(problems)


def test_no_duplicates_across_the_whole_matrix(corpus):
    """Fingerprint uniqueness, computed over every emitted file at once."""
    seen = {}
    dupes = []
    for scenarios in corpus.values():
        for sc in scenarios:
            key = json.dumps(
                {'t': sc['template'], 'a': sorted(sc['axes'].items())},
                sort_keys=True,
                ensure_ascii=False,
            )
            if key in seen:
                dupes.append(f'{sc["scenario_id"]} duplicates {seen[key]}')
            seen[key] = sc['scenario_id']
    assert not dupes, 'duplicate scenarios:\n' + '\n'.join(dupes[:20])


def test_scenario_ids_unique_and_dense(corpus):
    ids = [sc['scenario_id'] for scs in corpus.values() for sc in scs]
    assert len(ids) == len(set(ids)), 'duplicate scenario_id'
    nums = sorted(int(i.split('-')[1]) for i in ids)
    assert nums == list(range(1, len(nums) + 1)), 'scenario ids are not a dense 1..N range'


def test_axis_values_match_the_code(corpus):
    """Every emitted axis value must still exist in the code."""
    dims = {d.name: set(d.values) for d in build_dimensions()}
    bad = []
    for scenarios in corpus.values():
        for sc in scenarios:
            for axis, value in sc['axes'].items():
                allowed = dims.get(axis)
                assert allowed is not None, f'{sc["scenario_id"]}: unknown axis {axis}'
                if value not in allowed:
                    bad.append(f'{sc["scenario_id"]}: {axis}={value}')
    assert not bad, 'axis values that no longer exist in the code:\n' + '\n'.join(bad[:20])


def test_templates_only_vary_axes_they_act_on(corpus):
    """A template must use every axis it declares, and observe real members.

    The mirror image of the check this replaced. That one required an axis to be
    mentioned in prose, which flagged ten correct templates because the prose
    never said the words "actor role", and it would have passed an axis that is
    named but never actually varied, which is the padding case worth catching.
    """
    problems = []
    keys = {t.key for t in TEMPLATES}
    for tpl in TEMPLATES:
        for axis in tpl.axes:
            if axis not in tpl.observed:
                problems.append(f'{tpl.key}: declares {axis} but observes nothing on it')
        for axis, members in tpl.observed.items():
            if axis not in tpl.axes:
                problems.append(f'{tpl.key}: observes {axis} but does not declare it')
                continue
            allowed = set(tpl.axis_values.get(axis, ()))
            for m in members:
                if m not in allowed:
                    problems.append(f'{tpl.key}: {axis}={m} is not a value the code defines')
    for scenarios in corpus.values():
        for sc in scenarios:
            assert sc['template'] in keys, f'{sc["scenario_id"]}: unknown template'
            for axis in sc['axes']:
                assert axis in dims_or_fail(axis), f'{sc["scenario_id"]}: unknown axis {axis}'
    assert not problems, 'templates vary axes they do not observe:\n' + '\n'.join(problems)


def dims_or_fail(axis):
    return {d.name for d in build_dimensions()}


def test_observed_values_exist_in_the_code():
    dims = {d.name: set(d.values) for d in build_dimensions()}
    problems = []
    for tpl in TEMPLATES:
        for axis, members in tpl.observed.items():
            allowed = dims.get(axis)
            assert allowed is not None, f'{tpl.key}: observes unknown axis {axis}'
            for m in members:
                if m not in allowed:
                    problems.append(f'{tpl.key}: {axis}={m} is not a value the code defines')
    assert not problems, 'templates observe values that do not exist:\n' + '\n'.join(problems)


def test_generator_is_reproducible(corpus):
    """Re-running the generator must reproduce the committed files exactly."""
    for path, scenarios in corpus.items():
        m = re.search(r'part(\d+)-of-(\d+)', os.path.basename(path))
        group, groups = (int(m.group(1)), int(m.group(2))) if m else (1, 1)
        regenerated, _ = generate(group=group, groups=groups)
        assert len(regenerated) == len(scenarios), (
            f'{os.path.basename(path)}: {len(regenerated)} regenerated vs {len(scenarios)} stored'
        )
        for a, b in zip(regenerated, scenarios, strict=True):
            assert a['scenario_id'] == b['scenario_id'], f'group {group}: id drift'
            assert a['axes'] == b['axes'], f'group {group}: axis drift at {a["scenario_id"]}'
            assert [s['api'] for s in a['journey_steps']] == [
                s['api'] for s in b['journey_steps']
            ], f'group {group}: step drift at {a["scenario_id"]}'


def test_no_flattened_axis_correlations(corpus):
    """Each template's scenarios must genuinely differ in the axes they declare.

    If a template collapsed to one value per axis the count would still look right
    while the coverage would be fiction.
    """
    by_template = collections.defaultdict(list)
    for scenarios in corpus.values():
        for sc in scenarios:
            by_template[sc['template']].append(sc)
    for tpl in TEMPLATES:
        scenarios = by_template.get(tpl.key, [])
        assert scenarios, f'{tpl.key}: no scenarios emitted'
        for axis in tpl.axes:
            values = {s['axes'][axis] for s in scenarios}
            assert len(values) > 1, (
                f'{tpl.key}: axis {axis} has a single value across {len(scenarios)} scenarios'
            )


def test_journeys_are_non_trivial(corpus):
    for scenarios in corpus.values():
        for sc in scenarios:
            assert len(sc['journey_steps']) >= 3, (
                f'{sc["scenario_id"]}: only {len(sc["journey_steps"])} steps'
            )
            for step in sc['journey_steps']:
                assert step['assertion'], f'{sc["scenario_id"]}: step without assertion'
                assert step['department'], f'{sc["scenario_id"]}: step without department'


def test_matrix_covers_every_template_and_family(corpus):
    seen_templates = {sc['template'] for scs in corpus.values() for sc in scs}
    assert seen_templates == {t.key for t in TEMPLATES}, (
        f'templates with no scenarios: {sorted({t.key for t in TEMPLATES} - seen_templates)}'
    )
    families = {sc['family'] for scs in corpus.values() for sc in scs}
    assert families == {'financial', 'clinical', 'rbac'}, f'unexpected families {families}'


def test_no_foreign_scripts(corpus):
    problems = []
    for path in GENERATED:
        with open(path, encoding='utf-8') as fh:
            for i, line in enumerate(fh.read().split('\n'), 1):
                m = FOREIGN.search(line)
                if m:
                    problems.append(f'{os.path.basename(path)}:{i} {m.group()!r}')
    assert not problems, 'foreign scripts:\n' + '\n'.join(problems)


def test_no_broken_words_across_scripts(corpus):
    problems = []
    for path in GENERATED:
        with open(path, encoding='utf-8') as fh:
            for i, line in enumerate(fh.read().split('\n'), 1):
                for m in GLUED.finditer(line):
                    if line[max(0, m.start() - 1) : m.start()] in AR_PREFIXES:
                        continue
                    problems.append(
                        f'{os.path.basename(path)}:{i} {line[max(0, m.start() - 20) : m.end() + 20]!r}'
                    )
    assert not problems, 'glued cross-script tokens:\n' + '\n'.join(problems[:20])


def test_matrix_scale_is_honest(corpus):
    """Every scenario must be a distinct journey, and the count must be truthful.

    This replaces a flat `total >= 1000` assertion. That number was wrong twice:
    it was satisfiable only by widening axes a template cannot observe, which
    produces the duplication the brief forbids, and it counted permutations
    rather than journeys.

    What is asserted instead is the property that actually matters: the count
    equals the number of distinct (template, axis-value) pairs, every pair is
    reachable from the templates, and nothing is emitted twice. If the matrix
    needs to grow, the failure message says to add a template.
    """
    scenarios = [sc for scs in corpus.values() for sc in scs]
    total = len(scenarios)

    pairs = {(sc['template'], tuple(sorted(sc['axes'].items()))) for sc in scenarios}
    assert len(pairs) == total, (
        f'{total} scenarios but only {len(pairs)} distinct journeys; the matrix is padded'
    )

    reachable = set()
    for tpl in TEMPLATES:
        for combo in itertools.product(*(tpl.axis_values.get(a, ()) for a in tpl.axes)):
            reachable.add((tpl.key, tuple(sorted(dict(zip(tpl.axes, combo, strict=True)).items()))))
    assert pairs <= reachable, (
        f'{len(pairs - reachable)} emitted pairs are not reachable from any template'
    )

    assert len(TEMPLATES) >= 20, (
        f'only {len(TEMPLATES)} templates; add journeys that exist in the code '
        f'rather than widening an axis a template cannot observe'
    )
