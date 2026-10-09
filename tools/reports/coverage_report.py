"""Turn raw coverage artefacts into the reports the repository actually shows.

The numbers already existed, in two places, and neither was readable:

  * CI printed Python coverage into the job log and threw it away.
  * CI printed frontend coverage from ``coverage-final.json`` reading a ``summary``
    and a ``total`` key. Vitest's v8 format has neither, so it computed ``0/0`` and
    reported a green-looking zero. That is why there was no frontend coverage
    report: the code that would have produced one was reading a format that does
    not exist.

This module reads both artefacts the way their producers actually write them and
writes markdown that is committed, so the coverage of a checkout is visible
without running anything.

The output is deliberately three files rather than one. Backend and frontend are
different languages measured by different tools with different notions of a line,
and merging them into a single percentage would be the kind of number that cannot
be acted on. The third file is the short summary meant for a reader who wants the
state of the repository in one screen.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORTS_DIR = os.path.join(ROOT, 'docs', 'reports')

# Where each producer writes, relative to the repository root.
PYTHON_COVERAGE_CANDIDATES = (
    'coverage.json',
    'reports/backend-coverage.json',
    os.path.join('reports', 'backend-coverage.json'),
)
FRONTEND_COVERAGE_CANDIDATES = (
    os.path.join('coverage', 'coverage-final.json'),
    'coverage-final.json',
)


@dataclass
class FileStat:
    path: str
    covered: int
    total: int

    @property
    def pct(self) -> float:
        return 100.0 * self.covered / self.total if self.total else 0.0


@dataclass
class Metric:
    """One measure over a set of files: statements, branches or functions."""

    label: str
    files: list[FileStat] = field(default_factory=list)

    @property
    def covered(self) -> int:
        return sum(f.covered for f in self.files)

    @property
    def total(self) -> int:
        return sum(f.total for f in self.files)

    @property
    def pct(self) -> float:
        return 100.0 * self.covered / self.total if self.total else 0.0

    def worst(self, n: int) -> list[FileStat]:
        """Files with the most room left, largest first, skipping empty ones."""
        ranked = [f for f in self.files if f.total]
        return sorted(ranked, key=lambda f: (f.pct, -f.total))[:n]


def _find(candidates: tuple[str, ...]) -> str | None:
    for rel in candidates:
        path = os.path.join(ROOT, rel)
        if os.path.isfile(path):
            return path
    return None


# ── Python ────────────────────────────────────────────────────────────────
def read_python_coverage() -> dict | None:
    """Load coverage.py's json report, which is what ``coverage json`` writes."""
    path = _find(PYTHON_COVERAGE_CANDIDATES)
    if not path:
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f'  could not read {path}: {exc}', file=sys.stderr)
        return None


def python_metrics(data: dict) -> dict[str, Metric]:
    files = data.get('files', {})
    by_package: dict[str, Metric] = defaultdict(lambda: Metric(''))
    lines = Metric('lines')
    for rel, entry in files.items():
        summary = entry.get('summary', {})
        covered = int(summary.get('covered_lines', 0))
        total = int(summary.get('num_statements', 0))
        if not total:
            continue
        stat = FileStat(rel.replace('\\', '/'), covered, total)
        lines.files.append(stat)
        package = rel.replace('\\', '/').split('/')[0] or '(root)'
        by_package[package].files.append(stat)
    by_package['(all)'] = lines
    return dict(by_package)


# ── Frontend ──────────────────────────────────────────────────────────────
def read_frontend_coverage() -> dict | None:
    """Load vitest's coverage-final.json.

    The v8 provider writes istanbul-shaped data with per-file ``s``/``f``/``b``
    maps and no ``summary`` or ``total``. Counting has to come from those maps: a
    statement value of 0 is uncovered, anything above it is covered, and a branch
    value is an array whose entries are hit counts.
    """
    path = _find(FRONTEND_COVERAGE_CANDIDATES)
    if not path:
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f'  could not read {path}: {exc}', file=sys.stderr)
        return None


def _count(mapping: dict, branch: bool = False) -> FileStat:
    covered = 0
    total = 0
    for value in mapping.values():
        if branch:
            for hits in value if isinstance(value, list) else [value]:
                total += 1
                if hits:
                    covered += 1
        else:
            total += 1
            if value:
                covered += 1
    return FileStat('', covered, total)


def frontend_metrics(data: dict) -> dict[str, Metric]:
    statements = Metric('statements')
    branches = Metric('branches')
    functions = Metric('functions')
    by_area: dict[str, Metric] = defaultdict(lambda: Metric(''))
    for raw_path, entry in data.items():
        if not isinstance(entry, dict) or 's' not in entry:
            continue
        rel = entry.get('path') or raw_path
        rel = rel.replace('\\', '/')
        s = _count(entry['s'])
        statements.files.append(FileStat(rel, s.covered, s.total))
        f_stat = _count(entry.get('f', {}))
        functions.files.append(FileStat(rel, f_stat.covered, f_stat.total))
        b_stat = _count(entry.get('b', {}), branch=True)
        branches.files.append(FileStat(rel, b_stat.covered, b_stat.total))

        area = _frontend_area(rel)
        by_area[area].files.append(s)
    by_area['(all statements)'] = statements
    return {
        'areas': dict(by_area),
        'statements': statements,
        'branches': branches,
        'functions': functions,
    }


def _frontend_area(rel: str) -> str:
    """Group a script by where it sits, tolerating absolute paths.

    The keys in ``coverage-final.json`` are absolute, and the ``path`` field can be
    absolute too, so the prefix is matched as a suffix rather than by splitting on
    a literal that may not be there.
    """
    norm = rel.replace('\\', '/')
    marker = 'static/js/'
    idx = norm.find(marker)
    if idx < 0:
        return norm
    rest = norm[idx + len(marker) :]
    if not rest:
        return 'static/js (root)'
    parts = rest.split('/')
    if parts[0] == 'pages' and len(parts) > 1:
        return f'static/js/pages/{parts[1]}'
    if parts[0] == 'pages':
        return 'static/js/pages'
    return f'static/js/{parts[0]}'


# ── Scenarios ─────────────────────────────────────────────────────────────
def scenario_stats() -> dict:
    import glob

    def load(pattern: str) -> list[dict]:
        out = []
        for f in sorted(glob.glob(os.path.join(ROOT, pattern))):
            try:
                with open(f, encoding='utf-8') as fh:
                    out += json.load(fh)
            except (OSError, json.JSONDecodeError):
                continue
        return out

    generated = load('docs/scenarios/generated/*.json')
    hand = load('docs/scenarios/batch-*.json')
    families: dict[str, int] = defaultdict(int)
    for sc in generated:
        families[sc['family']] += 1

    covered, total = _route_coverage(generated + hand)
    return {
        'generated': len(generated),
        'handwritten': len(hand),
        'total': len(generated) + len(hand),
        'templates': len({sc['template'] for sc in generated}),
        'axes': len({a for sc in generated for a in sc['axes']}),
        'families': dict(sorted(families.items())),
        'routes_covered': covered,
        'routes_total': total,
        'routes_pct': 100.0 * covered / total if total else 0.0,
    }


def _route_coverage(scenarios: list[dict]) -> tuple[int, int]:
    import re

    api = re.compile(r'^\s*(?:GET|POST|PUT|PATCH|DELETE)\s+(\S+)')
    inventory_path = os.path.join(ROOT, 'route_inventory.json')
    if not os.path.isfile(inventory_path):
        return 0, 0
    with open(inventory_path, encoding='utf-8') as fh:
        inv = json.load(fh)

    def shape(p: str) -> str:
        named = re.sub(r'<(?:[^:<>]+:)?([^<>]+)>', r'{\1}', p)
        return re.sub(r'<[^>]*>|\{[^}]*\}', '{}', named)

    state = {
        shape(r['path'])
        for r in inv['routes']
        if {'POST', 'PUT', 'DELETE', 'PATCH'} & set(r['methods'])
    }
    covered = set()
    for sc in scenarios:
        for step in sc['journey_steps']:
            m = api.match(step['api'])
            if m:
                covered.add(shape(m.group(1)))
    return len(covered & state), len(state)


# ── Rendering ─────────────────────────────────────────────────────────────
def _pct(value: float) -> str:
    return f'{value:.1f}%'


def _table(rows: list[tuple[str, ...]], header: tuple[str, ...]) -> str:
    out = ['| ' + ' | '.join(header) + ' |', '|' + '|'.join('---' for _ in header) + '|']
    for row in rows:
        out.append('| ' + ' | '.join(row) + ' |')
    return '\n'.join(out)


def render_backend(data: dict) -> str:
    metrics = python_metrics(data)
    totals = data.get('totals', {})
    lines = [
        '# Backend coverage',
        '',
        'Produced by `pytest-cov` over `app`, `routes`, `services`, `models` and',
        '`utils`, combined across the CI shards. Regenerate with',
        '`python tools/reports/coverage_report.py`.',
        '',
    ]
    if totals:
        covered_lines = int(totals.get('covered_lines', 0))
        statements = int(totals.get('num_statements', 0))
        lines += [
            _table(
                [
                    (
                        'covered lines / statements',
                        f'{covered_lines:,}',
                        f'{statements:,}',
                        _pct(100.0 * covered_lines / statements if statements else 0.0),
                    )
                ],
                ('measure', 'covered', 'statements', 'percent'),
            ),
            '',
        ]

    rows = []
    for package in sorted(metrics):
        if package == '(all)':
            continue
        m = metrics[package]
        if not m.total:
            continue
        rows.append((f'`{package}`', f'{m.covered:,}', f'{m.total:,}', _pct(m.pct)))
    if rows:
        rows.sort(key=lambda r: float(r[3].rstrip('%')))
        lines += [
            '## By package',
            '',
            _table(rows, ('package', 'covered', 'statements', 'percent')),
            '',
        ]

    worst = metrics.get('(all)').worst(20) if '(all)' in metrics else []
    if worst:
        lines += [
            '## Least covered modules',
            '',
            'Where the missing statements are, because a low percentage on a large',
            'module is worth more attention than the same percentage on a small one.',
            '',
            _table(
                [(f'`{f.path}`', f'{f.covered}/{f.total}', _pct(f.pct)) for f in worst],
                ('module', 'covered/total', 'percent'),
            ),
            '',
        ]
    return '\n'.join(lines) + '\n'


def render_frontend(data: dict) -> str:
    m = frontend_metrics(data)
    st, br, fn = m['statements'], m['branches'], m['functions']
    lines = [
        '# Frontend coverage',
        '',
        'Produced by the vitest v8 provider over `static/js`. Regenerate with',
        '`npm run test:js:coverage` followed by',
        '`python tools/reports/coverage_report.py`.',
        '',
        '## The number that was previously reported was zero for the wrong reason',
        '',
        'CI read `summary.covered` and `total` from `coverage-final.json`. The v8',
        'provider writes neither; it writes per-file `s`, `f` and `b` maps. The',
        'arithmetic therefore ran over two missing keys and produced `0/0`, which',
        'looked like a measured result rather than a broken reader.',
        '',
        '## A second reason the figure was near zero',
        '',
        'The page scripts are loaded by `tests/frontend/test-utils.mjs`, which reads',
        'the file and calls `eval` on it. `eval` runs outside the module pipeline,',
        'so the provider never instrumented the code that executed. The tests were',
        'real, 318 of them, but they were measuring nothing.',
        '',
        'The tests still use that loader, because the scripts rely on top-level `var`',
        'leaking onto `window`, which only happens for classic scripts. Converting the',
        'loader to a dynamic `import` instruments the code and breaks that global leak,',
        'which is why the migration was reverted rather than shipped.',
        '',
        '**The page scripts are not instrumented, so this figure is not application',
        'coverage.** It counts the module bodies the provider did see, which excludes',
        'every script loaded through the eval loader. Treat it as the floor of what is',
        'measured, not as the state of the frontend.',
        '',
        'So the figure below is honest about a narrow measurement: it counts the module',
        'bodies the provider saw. Treating it as statement coverage of the application',
        'frontend would be wrong, and the header says so on purpose.',
        '',
        _table(
            [
                ('statements', f'{st.covered:,}', f'{st.total:,}', _pct(st.pct)),
                ('branches', f'{br.covered:,}', f'{br.total:,}', _pct(br.pct)),
                ('functions', f'{fn.covered:,}', f'{fn.total:,}', _pct(fn.pct)),
            ],
            ('measure', 'covered', 'total', 'percent'),
        ),
        '',
    ]
    rows = []
    for area, metric in sorted(m['areas'].items()):
        if area == '(all statements)' or not metric.total:
            continue
        rows.append((f'`{area}`', f'{metric.covered:,}', f'{metric.total:,}', _pct(metric.pct)))
    if rows:
        rows.sort(key=lambda r: float(r[3].rstrip('%')))
        lines += ['## By area', '', _table(rows, ('area', 'covered', 'statements', 'percent')), '']
    worst = st.worst(20)
    if worst:
        lines += [
            '## Least covered scripts',
            '',
            _table(
                [(f'`{f.path}`', f'{f.covered}/{f.total}', _pct(f.pct)) for f in worst],
                ('script', 'covered/total', 'percent'),
            ),
            '',
        ]
    return '\n'.join(lines) + '\n'


def render_summary(py: dict | None, fe: dict | None, scen: dict) -> str:
    py_total = py.get('totals', {}).get('covered_lines') if py else None
    py_stmt = py.get('totals', {}).get('num_statements') if py else None
    py_pct = 100.0 * py_total / py_stmt if py_total and py_stmt else None
    fe_pct = None
    if fe:
        m = frontend_metrics(fe)
        fe_pct = m['statements'].pct

    def cell(value: float | None) -> str:
        return _pct(value) if value is not None else 'not measured here'

    lines = [
        '# Repository summary',
        '',
        'One screen of what is actually measured in this repository. Every figure',
        'below is read from a generated artefact; none of it is typed by hand, and',
        'the generators are in `tools/reports/`.',
        '',
        '## The three things worth knowing',
        '',
        _table(
            [
                ('Backend Python statements', cell(py_pct), '`docs/reports/backend-coverage.md`'),
                (
                    'Frontend JavaScript statements',
                    cell(fe_pct),
                    '`docs/reports/frontend-coverage.md` — narrow measurement, see that file',
                ),
                (
                    'State-changing routes reached by the scenario matrix',
                    _pct(scen['routes_pct']),
                    '`docs/scenarios/generated/README.md`',
                ),
            ],
            ('measure', 'current', 'detail'),
        ),
        '',
        '## Scenario matrix',
        '',
        _table(
            [
                ('generated', f'{scen["generated"]:,}'),
                ('hand-written and audited', f'{scen["handwritten"]:,}'),
                ('total', f'{scen["total"]:,}'),
                ('templates', f'{scen["templates"]:,}'),
                ('code-derived axes', f'{scen["axes"]:,}'),
                (
                    'state-changing routes reached',
                    f'{scen["routes_covered"]}/{scen["routes_total"]}',
                ),
            ],
            ('measure', 'count'),
        ),
        '',
        'Families:',
        '',
        _table(
            [(f'`{k}`', f'{v:,}') for k, v in scen['families'].items()],
            ('family', 'scenarios'),
        ),
        '',
        '## Why scenario count and coverage are different numbers',
        '',
        f'The matrix holds {scen["total"]:,} scenarios and reaches',
        f'{scen["routes_pct"]:.1f}% of the state-changing routes. Those two numbers are',
        'not supposed to track each other, and the difference is deliberate: scenarios',
        'multiply over a dimension, so a journey with a genuine five-value state',
        'machine yields five scenarios while still touching one route. Conversely a',
        'route can be reached by a single scenario. Counting scenarios to claim',
        'coverage is the padding the matrix refuses to do, which is why every axis is',
        'required to state what it changes and where its value comes from.',
        '',
    ]
    return '\n'.join(lines) + '\n'


def main() -> int:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    py = read_python_coverage()
    fe = read_frontend_coverage()
    scen = scenario_stats()

    written = []
    if py:
        path = os.path.join(REPORTS_DIR, 'backend-coverage.md')
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(render_backend(py))
        written.append(('backend-coverage.md', f'{py.get("totals", {}).get("covered_lines", 0):,}'))
    else:
        print('  no Python coverage artefact found', file=sys.stderr)
    if fe:
        path = os.path.join(REPORTS_DIR, 'frontend-coverage.md')
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(render_frontend(fe))
        m = frontend_metrics(fe)
        written.append(('frontend-coverage.md', _pct(m['statements'].pct)))
    else:
        print('  no frontend coverage artefact found', file=sys.stderr)

    summary_path = os.path.join(REPORTS_DIR, 'README.md')
    with open(summary_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(render_summary(py, fe, scen))
    written.append(('README.md', 'summary'))

    for name, note in written:
        print(f'  wrote docs/reports/{name}  {note}')
    if not py and not fe:
        print(
            '  nothing to report: run `pytest --cov` and `npm run test:js:coverage` first',
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
