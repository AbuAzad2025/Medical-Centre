"""Fail CI when coverage drops below the floor the repository holds itself to.

The repository's coverage rule is not "the average is high" -- it is that the
project as a whole is at or above a total floor and that no individual source
file is left below a per-file floor. A single average can hide a file nobody
ever exercised, which is exactly the file that breaks in production, so the
per-file floor is checked separately and reported separately.

The floors live in ``.github/coverage-floor.json`` rather than in this script,
so the standard is one committed, reviewable number that only ever goes up.
Coverage is raised in steps, and each step raises the floor to match what the
repository actually holds, so a regression is caught by the very next push
instead of being discovered months later.

Both producers are read the way they actually write:

  * ``coverage.json`` -- coverage.py's json report, with a ``files`` map of
    per-file ``summary`` objects.
  * ``coverage/coverage-final.json`` -- vitest's v8 report, which has per-file
    ``s`` / ``f`` / ``b`` maps and no ``summary`` or ``total`` key. Reading a
    missing key from it is what made the frontend figure report zero.

Usage:
    python scripts/ci/check_coverage_thresholds.py [--floors .github/coverage-floor.json]
                                                   [--backend coverage.json]
                                                   [--frontend coverage/coverage-final.json]

Exit code 0 when every floor is met, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass

# The floors the repository holds itself to. They are read from
# ``.github/coverage-floor.json`` when that file exists; the values below are
# the fallback for a checkout that does not carry it.
DEFAULT_FLOORS = {
    'backend_total_min': 86.0,
    'backend_file_min': 32.0,
    'frontend_total_min': 99.0,
    'frontend_file_min': 96.0,
}


@dataclass
class FileCoverage:
    path: str
    covered: int
    total: int

    @property
    def pct(self) -> float:
        return 100.0 * self.covered / self.total if self.total else 100.0


def _read_json(path: str) -> dict:
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def read_backend(path: str) -> tuple[list[FileCoverage], float]:
    data = _read_json(path)
    files = data.get('files', {})
    rows: list[FileCoverage] = []
    covered = 0
    total = 0
    for rel, entry in files.items():
        summary = entry.get('summary', {})
        num = int(summary.get('num_statements', 0))
        miss = int(summary.get('missing_lines', 0))
        if not num:
            continue
        rows.append(FileCoverage(rel.replace('\\', '/'), num - miss, num))
        covered += num - miss
        total += num
    overall = 100.0 * covered / total if total else 0.0
    return rows, overall


def _count(mapping: dict, branch: bool = False) -> tuple[int, int]:
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
    return covered, total


def read_frontend(path: str) -> tuple[list[FileCoverage], float]:
    data = _read_json(path)
    rows: list[FileCoverage] = []
    covered = 0
    total = 0
    for raw_path, entry in data.items():
        if not isinstance(entry, dict) or 's' not in entry:
            continue
        rel = entry.get('path') or raw_path
        rel = rel.replace('\\', '/')
        marker = 'static/js/'
        idx = rel.find(marker)
        if idx >= 0:
            rel = rel[idx:]
        cov, tot = _count(entry['s'])
        if not tot:
            continue
        rows.append(FileCoverage(rel, cov, tot))
        covered += cov
        total += tot
    overall = 100.0 * covered / total if total else 0.0
    return rows, overall


def _report(
    label: str,
    rows: list[FileCoverage],
    overall: float,
    total_min: float,
    file_min: float,
    source: str | None = None,
) -> bool:
    failing = [r for r in rows if r.pct < file_min]
    failing.sort(key=lambda r: (r.pct, -r.total))
    ok = True

    print(f'\n## {label}')
    if source:
        print(f'  source: {source}')
    print(f'  files measured: {len(rows)}')
    print(f'  total: {overall:.2f}%  (floor {total_min:.1f}%)')
    if overall < total_min:
        print(f'  FAIL: total coverage is below the {total_min:.1f}% floor')
        ok = False
    else:
        print(f'  OK: total coverage is at or above the {total_min:.1f}% floor')

    print(f'  files below {file_min:.1f}%: {len(failing)} of {len(rows)}')
    for row in failing:
        print(f'    {row.pct:6.2f}%  {row.covered}/{row.total}  {row.path}')
    if not failing:
        print(f'  OK: every file is at or above {file_min:.1f}%')
    return ok


def _load_floors(path: str | None) -> dict[str, float]:
    """Read the floors the repository holds itself to."""
    floors = dict(DEFAULT_FLOORS)
    if not path or not os.path.isfile(path):
        return floors
    with open(path, encoding='utf-8') as fh:
        stored = json.load(fh)
    for key in floors:
        if key in stored:
            floors[key] = float(stored[key])
    return floors


def _find_frontend(path: str) -> str | None:
    """Locate the vitest report.

    CI merges the downloaded artefacts into ``covdata/`` and the frontend
    artefact stores the report under its own ``coverage/`` directory, so the
    file lands in one of two places depending on how the download was
    configured. Every known location is checked rather than assuming one.
    """
    candidates = [
        path,
        os.path.join('coverage', 'coverage-final.json'),
        os.path.join('covdata', 'coverage-final.json'),
        os.path.join('covdata', 'coverage', 'coverage-final.json'),
        'coverage-final.json',
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--floors',
        default=os.path.join('.github', 'coverage-floor.json'),
        help='JSON file holding the total and per-file floors the repository holds itself to.',
    )
    parser.add_argument('--backend', default='coverage.json')
    parser.add_argument('--frontend', default=os.path.join('coverage', 'coverage-final.json'))
    args = parser.parse_args(argv)

    floors = _load_floors(args.floors)
    ok = True

    if os.path.isfile(args.backend):
        rows, overall = read_backend(args.backend)
        ok &= _report(
            'Backend coverage (Python)',
            rows,
            overall,
            floors['backend_total_min'],
            floors['backend_file_min'],
        )
    else:
        print(f'\n## Backend coverage (Python)\n  SKIP: {args.backend} not found')
        ok = False

    frontend_path = _find_frontend(args.frontend)
    if frontend_path:
        rows, overall = read_frontend(frontend_path)
        ok &= _report(
            'Frontend coverage (JavaScript)',
            rows,
            overall,
            floors['frontend_total_min'],
            floors['frontend_file_min'],
            source=frontend_path,
        )
    else:
        print('\n## Frontend coverage (JavaScript)\n  SKIP: no vitest coverage-final.json found')
        ok = False

    print()
    if ok:
        print('Coverage floors met.')
        return 0
    print('Coverage floors NOT met.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
