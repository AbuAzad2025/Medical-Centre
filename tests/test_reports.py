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


def test_route_inventory_still_present_for_the_reports():
    """The reports depend on route_inventory.json; fail loudly if it moves."""
    assert os.path.isfile(os.path.join(ROOT, 'route_inventory.json'))
    with open(os.path.join(ROOT, 'route_inventory.json'), encoding='utf-8') as fh:
        inv = json.load(fh)
    assert inv.get('routes'), 'route_inventory.json has no routes'
