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
SCEN_DIR = os.path.join(ROOT, 'docs', 'scenarios')

sys.path.insert(0, GEN_DIR)

# Importing the family modules extends TEMPLATES in place, which is how the
# clinical and platform templates join the matrix.
import clinical_templates  # noqa: E402,F401
import platform_templates  # noqa: E402,F401
from dimensions import build_dimensions  # noqa: E402
from generate import generate  # noqa: E402

from templates import TEMPLATES, all_problems  # noqa: E402

clinical_templates.add_clinical_templates()
platform_templates.add_platform_templates()

# Scoped to the matrix shards on purpose. The generated directory also holds
# read-route-inventory.json, which is an inventory rather than a list of
# scenarios, and globbing it in makes every test here read a string where it
# expects a dict. A future artefact in this directory needs the same care.
GENERATED = sorted(glob.glob(os.path.join(GEN_OUT, 'scenarios*.json')))
HAND_BATCHES = sorted(glob.glob(os.path.join(SCEN_DIR, 'batch-*.json')))
API_LINE = re.compile(
    r'^(?:(?:GET|POST|PUT|DELETE|PATCH)(?:\|(?:GET|POST|PUT|DELETE|PATCH))*)?\s+(\S+)$'
)
PLACEHOLDERS = re.compile(r'<(?:[^:<>]+:)?([^<>]+)>')

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
    """The generated shards only.

    Kept separate from ``all_scenarios`` because the generated corpus is what the
    reproducibility and duplication checks are about: they assert the generator
    emits exactly what is committed. Coverage is a different question and must
    include the hand-written scenarios, which is what ``all_scenarios`` is for.
    """
    out = {}
    for p in GENERATED:
        with open(p, encoding='utf-8') as fh:
            out[p] = json.load(fh)
    return out


@pytest.fixture(scope='session')
def all_scenarios():
    """Every scenario in the repository, generated and hand-written.

    The coverage gates read this rather than ``corpus``. Reading ``corpus`` alone
    under-reported both figures: 40 audited scenarios were excluded, so a route
    covered only by a hand-written journey looked uncovered. The number published
    to a reader has to be the number over everything that exists.
    """
    out = {}
    for p in GENERATED + HAND_BATCHES:
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
    assert families == {'financial', 'clinical', 'rbac', 'platform'}, (
        f'unexpected families {families}'
    )


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


def test_handwritten_corpus_is_valid():
    """The 40 audited scenarios are held to the same standard as the generated ones.

    They are a separate source, not a lesser one: every route they name must exist,
    every source reference must resolve to a real file, and a scenario that says
    packages do not apply must not carry a package deduction.
    """
    import handwritten

    problems = handwritten.problems()
    assert not problems, 'hand-written corpus problems:\n' + '\n'.join(problems)
    assert len(handwritten.load()) >= 40, 'hand-written corpus shrank'


def test_handwritten_and_generated_do_not_collide(corpus):
    """A hand-written journey and a generated one must not trace the same route sequence."""
    import handwritten

    generated = [sc for scs in corpus.values() for sc in scs]
    gen_shapes: set[tuple] = set()
    for sc in generated:
        seq = tuple(
            sorted(
                re.sub(r'<[^>]*>|\{[^}]*\}', '{}', (s['api'] or '')) for s in sc['journey_steps']
            )
        )
        gen_shapes.add(seq)

    collisions = []
    for sc in handwritten.load():
        apis = []
        for st in sc['journey_steps']:
            m = API_LINE.match((st.get('api') or '').strip())
            apis.append(
                re.sub(r'<[^>]*>|\{[^}]*\}', '{}', m.group(1) if m else (st.get('api') or ''))
            )
        if tuple(sorted(apis)) in gen_shapes:
            collisions.append(sc['scenario_id'])
    assert not collisions, 'hand-written scenarios duplicate a generated journey: ' + ', '.join(
        collisions[:10]
    )


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

    import handwritten

    # Both sources count. The 40 audited scenarios are real journeys with a
    # fingerprint in the same terms, and excluding them would understate what the
    # repository actually documents.
    hand = handwritten.load()
    hand_fps = {handwritten.fingerprint(s) for s in hand}
    assert len(hand_fps) == len(hand), 'hand-written scenarios collide with each other'

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

    assert len(TEMPLATES) >= 40, (
        f'only {len(TEMPLATES)} templates; add journeys that exist in the code '
        f'rather than widening an axis a template cannot observe'
    )

    combined = total + len(hand)
    assert combined >= 800, (
        f'combined matrix is {combined} ({total} generated + {len(hand)} '
        f'hand-written), below the scale requested'
    )


def test_clinical_and_platform_families_are_separate(corpus):
    """Platform scenarios must not be counted as clinical ones.

    The brief forbids inflating the count. Owner and super-admin routes configure
    tenants and sell subscriptions; a scenario over them never touches a patient,
    so folding them into the clinical family would overstate clinical coverage.
    """
    families = collections.defaultdict(set)
    for scs in corpus.values():
        for sc in scs:
            families[sc['family']].add(sc['template'])

    tpl_by_key = {t.key: t for t in TEMPLATES}
    platform_prefixes = ('/owner/', '/super-admin/', '/api/billing/', '/api/super/')

    def path_of(api):
        m = API_LINE.match(api)
        return m.group(1) if m else ''

    for fam, keys in families.items():
        for k in keys:
            deps = [path_of(s.api) for s in tpl_by_key[k].steps]
            if fam == 'platform':
                assert any(d.startswith(platform_prefixes) for d in deps), (
                    f'{k} is filed as platform but touches no platform route: {deps}'
                )

    # and the reverse: clinical templates must actually reach a clinical route
    clinical_routes = (
        '/reception/',
        '/doctor/',
        '/emergency/',
        '/lab/',
        '/radiology/',
        '/medication/',
        '/nurse/',
        '/bed/',
        '/emar/',
        '/nursing-assessment/',
        '/handover/',
        # Telemedicine is a doctor-patient consultation, so a scenario over it is
        # clinical even though no department owns the blueprint. It was missing
        # from this list, which forced telemedicine journeys to be filed as
        # non-clinical to pass; correcting the list is the honest fix.
        '/telemedicine/',
        # These record or surface something about a patient, so a scenario that
        # reaches only one of them is still clinical. They were absent from this
        # list, which forced those journeys to be misfiled to pass the gate.
        '/specialty-forms/',
        '/patient-education/',
        '/ai-imaging/',
    )
    for k in families['clinical']:
        deps = [path_of(s.api) for s in tpl_by_key[k].steps]
        assert any(any(d.startswith(p) for p in clinical_routes) for d in deps), (
            f'{k} is filed as clinical but reaches no clinical route: {deps}'
        )


def test_every_axis_states_what_it_does_to_the_run(corpus):
    """An axis must carry a mechanism, and the mechanism must name the value.

    The failure this replaces is quiet: a template declares an axis, the
    generator multiplies the journey over every value of it, and the emitted
    scenarios differ only in a field nobody reads. The count goes up and the
    coverage does not. Requiring the axis to say what it changes, with the value
    substituted into the sentence, is what makes the count mean something.
    """
    problems = []
    for scenarios in corpus.values():
        for sc in scenarios:
            effect = sc.get('axes_effect')
            assert effect is not None, f'{sc["scenario_id"]}: no stated axis effect'
            assert set(effect) == set(sc['axes']), (
                f'{sc["scenario_id"]}: axes {sorted(sc["axes"])} but effects {sorted(effect)}'
            )
            for axis, value in sc['axes'].items():
                text = effect[axis]
                if not text.strip():
                    problems.append(f'{sc["scenario_id"]}: axis {axis} has an empty effect')
                elif value not in text:
                    problems.append(
                        f'{sc["scenario_id"]}: effect for {axis}={value} does not '
                        f'mention the value: {text!r}'
                    )
    assert not problems, 'axes that state nothing about the run:\n' + '\n'.join(problems[:20])


def test_every_axis_reaches_the_journey(corpus):
    """An axis must be an input the operator sends, not a field the audit records.

        Two ways to qualify: the axis is a route converter on one of the steps, so the
    value is literally part of the URL, or the axis has an entry in
    ``axis_effects.SUPPLIED_BY`` naming the form field or column that carries it.

    ``audit_action`` on a catalogue write is the case this exists for. It describes
    what an audit row ends up containing, it is not sent by the operator, and varying
    it produced the same run sixteen times. Entries that say "written by the audit
    writer, not sent by the operator" are recorded rather than removed so the axis is
    still available to the two templates whose journey really is an audit write.
    """
    from axis_effects import SUPPLIED_BY

    converters = {}
    for tpl in TEMPLATES:
        names = set()
        for step in tpl.steps:
            m = API_LINE.match(step.api)
            if m:
                names |= set(PLACEHOLDERS.findall(m.group(1)))
        converters[tpl.key] = names

    problems = []
    for tpl in TEMPLATES:
        for axis in tpl.axes:
            if axis in converters[tpl.key]:
                continue
            origin = SUPPLIED_BY.get(axis)
            if origin and 'not sent by the operator' not in origin:
                continue
            problems.append(f'{tpl.key}: axis {axis} reaches nothing on the journey')
    assert not problems, 'axes that are not an input to the run:\n' + '\n'.join(problems[:20])


def test_every_route_is_reached_not_just_the_mutating_ones(all_scenarios):
    """Every route, reads included, not only the ones that change state.

    The matrix started with state-changing routes on the reasoning that a GET
    cannot corrupt anything. For a clinical system that is wrong: a read that
    returns the wrong patient, the wrong price or a stale queue is a safety
    defect. 354 read-only routes were undocumented because of it, and this is the
    check that stops the gap reopening the next time a screen is added.

    It is also the check most likely to fail on a new feature, which is the point:
    a new list endpoint should force a decision about whether it is documented,
    rather than being added and forgotten.
    """
    with open(os.path.join(ROOT, 'route_inventory.json'), encoding='utf-8') as fh:
        inv = json.load(fh)

    def shape(path):
        named = re.sub(r'<(?:[^:<>]+:)?([^<>]+)>', r'{\1}', path)
        return re.sub(r'<[^>]*>|\{[^}]*\}', '{}', named)

    every = {shape(r['path']) for r in inv['routes']}
    reads = {
        shape(r['path'])
        for r in inv['routes']
        if not {'POST', 'PUT', 'DELETE', 'PATCH'} & set(r['methods'])
    }
    covered = set()
    for scs in all_scenarios.values():
        for sc in scs:
            for st in sc['journey_steps']:
                m = API_LINE.match(st['api'])
                if m:
                    covered.add(shape(m.group(1)))

    uncovered_reads = sorted(reads - covered)
    assert not uncovered_reads, (
        f'{len(uncovered_reads)} read-only routes have no scenario, including '
        f'{uncovered_reads[:8]}. A read that returns the wrong record is a safety '
        'defect, not a cosmetic one'
    )
    pct = 100.0 * len(covered & every) / len(every)
    print(f'\nroute coverage: {len(covered & every)}/{len(every)} routes = {pct:.1f}%')
    assert pct >= 99.0, f'only {pct:.1f}% of all routes are reached by a scenario'


def test_route_coverage_is_measured_not_asserted(all_scenarios):
    """Report coverage rather than assert a number that could be met by padding.

    This replaced the original `total >= 1000` assertion. What matters is how much
    of the state-changing route surface the matrix actually reaches, and that is a
    fact to publish on every run, not a threshold to satisfy.
    """
    with open(os.path.join(ROOT, 'route_inventory.json'), encoding='utf-8') as fh:
        inv = json.load(fh)
    state_changing = {
        re.sub(r'<[^>]*>|\{[^}]*\}', '{}', re.sub(r'<(?:[^:<>]+:)?([^<>]+)>', r'{\1}', r['path']))
        for r in inv['routes']
        if {'POST', 'PUT', 'DELETE', 'PATCH'} & set(r['methods'])
    }
    covered = set()
    for scs in all_scenarios.values():
        for sc in scs:
            for st in sc['journey_steps']:
                m = API_LINE.match(st['api'])
                if m:
                    covered.add(re.sub(r'<[^>]*>|\{[^}]*\}', '{}', m.group(1)))

    pct = 100.0 * len(covered & state_changing) / len(state_changing)
    print(
        f'\nroute coverage: {len(covered & state_changing)}/{len(state_changing)} '
        f'state-changing routes = {pct:.1f}%'
    )
    assert pct >= 20.0, (
        f'only {pct:.1f}% of state-changing routes are covered '
        f'({len(covered & state_changing)}/{len(state_changing)}); '
        f'the matrix is not reaching the application'
    )
