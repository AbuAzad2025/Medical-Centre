#!/usr/bin/env python3
"""Load-test SLO gate — parses Locust CSVs and fails on breach.

Thresholds (smoke profile):
    error rate   < 2%   across ALL requests
    p95 latency  < 1500ms across ALL requests

Usage:
    python scripts/check_load_slo.py artifacts/load_stats.csv
Exits 0 on pass, 1 on breach (so CI can gate on it).
"""

import csv
import sys

ERROR_RATE_MAX = 0.02  # 2%
P95_MS_MAX = 1500.0  # ms


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print('usage: check_load_slo.py <locust_stats.csv>')
        return 2

    path = argv[1]
    try:
        with open(path, encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
    except OSError as e:
        print(f'FAIL cannot read {path}: {e}')
        return 2

    total = next((r for r in rows if r.get('Name') == 'Aggregated'), None)
    if not total:
        print('FAIL no Aggregated row in stats CSV')
        return 2

    reqs = int(total['Request Count'] or 0)
    fails = int(total['Failure Count'] or 0)
    # Locust reports 'N/A' when too few samples exist for a percentile
    p95_raw = (total.get('95%') or '0').strip()
    try:
        p95 = float(p95_raw)
    except ValueError:
        print(f'WARN p95 unavailable ({p95_raw!r}) — treating as 0 for gating')
        p95 = 0.0

    err_rate = (fails / reqs) if reqs else 1.0

    print(f'requests={reqs} failures={fails} error_rate={err_rate:.2%} p95={p95:.0f}ms')

    breaches = []
    if err_rate >= ERROR_RATE_MAX:
        breaches.append(f'error_rate {err_rate:.2%} >= {ERROR_RATE_MAX:.0%}')
    if p95 > P95_MS_MAX:
        breaches.append(f'p95 {p95:.0f}ms > {P95_MS_MAX:.0f}ms')
    if reqs < 50:
        breaches.append(f'too few requests ({reqs}) for a meaningful sample')

    if breaches:
        print('SLO BREACH: ' + '; '.join(breaches))
        return 1
    print('SLO PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
