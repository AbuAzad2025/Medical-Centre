"""Guard the generated reports: they must be real, current, and not quietly empty.

Three separate failures are being prevented, and each of them happened before this
file existed.

1. A report that claims a measurement it never took. The CI summary for the
   frontend read ``summary.covered`` and ``total`` from vitest's
   ``coverage-final.json``, which has neither key, so it computed 0/0 and printed
   it as if it had been measured. A report that cannot distinguish "zero" from
   "I did not read the right field" is worse than no report, because it is
   believed.

2. A report that goes stale. These are committed files with numbers in them, so
   the scenario matrix can move underneath them and the number becomes a lie that
   nobody notices. The scenario figures are recomputed here from the same
   generator's output, so a drift fails the build instead of being published.

3. A report that stops being regenerated. If the generator is deleted, or its
   entry point is renamed, the committed reports would keep looking authoritative
   forever.
"""

from __future__ import annotations

import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(ROOT, 'docs', 'reports')
SUMMARY = os.path.join(REPORTS, 'README.md')
BACKEND = os.path.join(REPORTS, 'backend-coverage.md')
FRONTEND = os.path.join(REPORTS, 'frontend-coverage.md')
GENERATOR = os.path.join(ROOT, 'tools', 'reports', 'coverage_report.py')

REQUIRED = (SUMMARY, GENERATOR)

# Reported per file so a failure names the artefact rather than a parameter index.
REQUIRED_IDS = [os.path.basename(p) for p in REQUIRED]


def read(path: str) -> str:
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@pytest.mark.parametrize('path', REQUIRED, ids=REQUIRED_IDS)
def test_report_files_exist(path):
    assert os.path.isfile(path), f'{path} is missing; run tools/reports/coverage_report.py'


def test_frontend_report_does_not_claim_a_measurement_it_cannot_take():
    """The frontend report must state the caveat, or the number is not usable.

    The 0/0 defect is fixed, but the measurement is still narrow: the page scripts
    are loaded through ``eval`` and are not instrumented. A report that prints a
    percentage without saying so would be repeating the original problem in a new
    file, so the caveat is required rather than preferred.
    """
    if not os.path.isfile(FRONTEND):
        pytest.skip('no frontend coverage artefact was generated in this checkout')
    text = read(FRONTEND)
    assert 'eval' in text, (
        'the frontend report does not mention the eval loader, so a reader cannot '
        'tell why the figure is narrow'
    )
    assert re.search(r'\bnot\s+instrument', text) or 'not measured' in text, (
        'the frontend report does not say the page scripts are not instrumented'
    )


def test_summary_reports_scenario_figures_that_match_the_generator():
    """Recompute the scenario figures and require the summary to agree.

    Route coverage is the number most likely to drift, because it moves whenever a
    template is added or an axis is deleted, and a stale committed figure is
    indistinguishable from a current one.
    """
    sys_path = os.path.join(ROOT, 'tools', 'reports')
    import sys

    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    import coverage_report  # noqa: PLC0415

    stats = coverage_report.scenario_stats()
    assert stats['total'] > 0, 'the scenario matrix is empty'

    if not os.path.isfile(SUMMARY):
        pytest.skip('no summary was generated in this checkout')
    text = read(SUMMARY)
    assert f'{stats["total"]:,}' in text, (
        f'the summary does not carry the current scenario total ({stats["total"]:,}); '
        'regenerate it with tools/reports/coverage_report.py'
    )
    assert f'{stats["routes_covered"]}/{stats["routes_total"]}' in text, (
        f'the summary does not carry the current route coverage '
        f'({stats["routes_covered"]}/{stats["routes_total"]})'
    )


def test_generator_reads_the_formats_the_producers_actually_write():
    """Guard the two parsers against being "simplified" back into nonsense.

    Both formats have been misread once already, silently. A small fixture per
    producer is cheaper than rediscovering it: the Python one here is shaped like
    coverage.py's json output, the frontend one like istanbul's, and the test
    fails if either parser is changed to read a field that is not there.
    """
    sys_path = os.path.join(ROOT, 'tools', 'reports')
    import sys

    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    import coverage_report  # noqa: PLC0415

    python_fixture = {
        'totals': {'covered_lines': 30, 'num_statements': 40},
        'files': {
            'routes/reception/queue.py': {'summary': {'covered_lines': 20, 'num_statements': 25}},
            'services/payment_service.py': {'summary': {'covered_lines': 10, 'num_statements': 15}},
        },
    }
    backend = coverage_report.render_backend(python_fixture)
    assert '75.0%' in backend, 'the backend renderer lost the covered-line percentage'

    frontend_fixture = {
        'x/static/js/pages/reception/visits.js': {
            'path': 'x/static/js/pages/reception/visits.js',
            's': {'0': 1, '1': 0, '2': 3},
            'f': {'0': 1, '1': 0},
            'b': {'0': [1, 0]},
        }
    }
    metrics = coverage_report.frontend_metrics(frontend_fixture)
    st = metrics['statements']
    assert (st.covered, st.total) == (2, 3), (
        'the frontend statement counter no longer reads the v8 s map, which is the '
        'defect that made CI report 0/0'
    )
    assert metrics['functions'].total == 2
    assert metrics['branches'].covered == 1 and metrics['branches'].total == 2
    assert 'static/js/pages/reception' in metrics['areas'], (
        'the frontend area grouping stopped recognising the static/js layout'
    )


def test_summary_says_where_each_number_came_from():
    if not os.path.isfile(SUMMARY):
        pytest.skip('no summary was generated in this checkout')
    text = read(SUMMARY)
    for link in ('docs/reports/backend-coverage.md', 'docs/reports/frontend-coverage.md'):
        assert link in text, f'the summary does not point at {link}'
    assert 'tools/reports' in text, 'the summary does not name the generator directory'


def test_no_report_claims_full_coverage_without_a_measured_denominator():
    """A bare "100%" with no counts next to it is the shape the old bug had."""
    for path in (SUMMARY, BACKEND, FRONTEND):
        if not os.path.isfile(path):
            continue
        text = read(path)
        for match in re.finditer(r'(?<![\d.])100(?:\.0)?%', text):
            window = text[max(0, match.start() - 200) : match.end() + 200]
            assert re.search(r'\d[\d,]*\s*/\s*\d[\d,]*|\d[\d,]{2,}', window), (
                f'{os.path.basename(path)} claims 100% with no denominator beside it'
            )


def test_scenario_execution_registry_is_accurate():
    """Every template the registry claims is executed must exist in the matrix.

    The registry is the number a reader is given, so a key that names a template
    which does not exist inflates it silently. It cost one key to find: the file
    recorded the renewal scenario under a name that was never generated.
    """
    sys_path = os.path.join(ROOT, 'tests')
    import sys

    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    from scenario_execution_registry import executed_coverage  # noqa: PLC0415

    report = executed_coverage()
    assert not report['unknown_templates'], (
        f'the registry names templates the matrix does not contain: {report["unknown_templates"]}'
    )
    assert report['templates_executed'] > 0, 'the registry claims nothing is executed'
    assert report['scenarios_executed'] <= report['scenarios_total'], (
        'the registry claims more scenarios executed than the matrix contains'
    )


def test_known_defects_are_declared_strict_xfail():
    """Every xfail in the scenario suite must be strict and must carry a reason.

    A bare xfail is how a documented defect quietly becomes a test nobody reads: it
    keeps reporting without anybody deciding anything, and it happily survives the
    bug being fixed. strict=True turns that fix into an XPASS, which fails and asks
    for the marker to be removed deliberately.

    Parsed rather than run, so the check is about how the suite declares its known
    defects rather than about what the database happens to do today.
    """
    import ast
    import pathlib
    import sys as _sys

    sys_path = os.path.join(ROOT, 'tests')
    if sys_path not in _sys.path:
        _sys.path.insert(0, sys_path)
    from scenario_execution_registry import EXECUTED_TEMPLATES  # noqa: PLC0415

    modules = sorted({mod for mod, _ in EXECUTED_TEMPLATES.values()})
    checked = 0
    problems: list[str] = []

    for module in modules:
        path = pathlib.Path(__file__).parent / f'{module}.py'
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for deco in node.decorator_list:
                if not isinstance(deco, ast.Call):
                    continue
                name = getattr(deco.func, 'attr', None) or getattr(deco.func, 'id', None)
                if name != 'xfail':
                    continue
                checked += 1
                kwargs = {kw.arg: kw.value for kw in deco.keywords}
                strict = kwargs.get('strict')
                if not (isinstance(strict, ast.Constant) and strict.value is True):
                    problems.append(f'{module}.{node.name}: xfail without strict=True')
                if 'reason' not in kwargs:
                    problems.append(f'{module}.{node.name}: xfail without a reason')

    assert checked > 0, 'no xfail markers found; the scenario modules changed shape?'
    assert not problems, 'xfail markers that will not survive a fix:\n' + '\n'.join(problems)


def test_scenario_execution_coverage_never_regresses():
    """Execution coverage is a floor, not a headline.

    Written as a comparison against a number rather than a percentage so that adding
    a template to the matrix does not silently make the gate harder and deleting one
    does not silently make it easier. The floor moves only when someone raises it
    deliberately, which is the only honest way to move it.
    """
    sys_path = os.path.join(ROOT, 'tests')
    import sys

    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    from scenario_execution_registry import executed_coverage  # noqa: PLC0415

    report = executed_coverage()
    floor_pct = 30.5
    floor_templates = 30
    assert report['templates_executed'] >= floor_templates, (
        f'execution coverage fell to {report["templates_executed"]} templates from a '
        f'floor of {floor_templates}'
    )
    assert report['pct_scenarios'] >= floor_pct, (
        f'execution coverage fell to {report["pct_scenarios"]:.1f}% of scenarios from '
        f'a floor of {floor_pct}%'
    )
    print(
        f'\nexecuted scenarios: {report["scenarios_executed"]}/{report["scenarios_total"]} '
        f'({report["pct_scenarios"]:.1f}%) across '
        f'{report["templates_executed"]}/{report["templates_total"]} templates'
    )


def test_blocked_journeys_are_re_verified_against_the_code():
    """Every checkable blocked note must still be true of the code.

    A blocked note is a claim that something does not exist. Those claims were
    written by reading the code, and reading the code is how a document goes
    stale: two of the ten had already become false, because the application grew
    the thing the note said was missing. A note that says a feature is absent when
    it is present is worse than no note, because it stops someone looking for it.

    The check is a script rather than an assertion duplicated here, so the same
    tool that produced the correction is the one that guards it afterwards.
    """
    import subprocess
    import sys

    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    proc = subprocess.run(
        [sys.executable, 'tools/scenario_gen/verify_blocked.py'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=env,
    )
    assert proc.returncode == 0, (
        f'a blocked-journeys note no longer matches the code:\n{proc.stdout}\n{proc.stderr}'
    )
    assert 'RESOLVED' in proc.stdout, (
        'the verification tool reported nothing as resolved; either it lost its '
        'resolution records or the blocked document was rewritten without them'
    )


def test_blocked_document_exists_and_names_every_id():
    """The blocked document and the checker must agree on which items exist."""
    import re as _re

    path = os.path.join(ROOT, 'docs', 'scenarios', 'blocked-journeys.md')
    assert os.path.isfile(path), 'docs/scenarios/blocked-journeys.md is missing'

    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    documented = set(_re.findall(r'BLOCKED-\d+', text))
    assert documented, 'the blocked document names no items'

    sys_path = os.path.join(ROOT, 'tools', 'scenario_gen')
    import sys

    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    import verify_blocked  # noqa: PLC0415

    checked = {spec['id'] for spec in verify_blocked.CHECKS}
    missing = checked - documented
    assert not missing, (
        f'the verifier checks {sorted(missing)} but the document does not name them; '
        f'a check with no note behind it is a check nobody reads'
    )


def test_route_inventory_still_present_for_the_reports():
    """The reports depend on route_inventory.json; fail loudly if it moves."""
    assert os.path.isfile(os.path.join(ROOT, 'route_inventory.json'))
    with open(os.path.join(ROOT, 'route_inventory.json'), encoding='utf-8') as fh:
        inv = json.load(fh)
    assert inv.get('routes'), 'route_inventory.json has no routes'
