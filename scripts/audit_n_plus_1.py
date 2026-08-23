"""
N+1 query detector — instruments SQLAlchemy via event listeners.
Counts queries per request and flags hot paths exceeding threshold.

Usage:
    python scripts/audit_n_plus_1.py
"""

import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent))

THRESHOLD = 15  # queries per request — above this is suspicious
HOT_PATHS = [
    '/',
    '/reception/patients',
    '/reception/visits',
    '/reception/queue',
    '/doctor/dashboard',
    '/doctor/patient-queue',
    '/medication/dashboard',
    '/manager/dashboard',
]


def main() -> int:
    os.environ.setdefault('SECRET_KEY', 'n1-audit-only-not-secret')
    os.environ['APP_ENV'] = 'testing'
    os.environ.setdefault(
        'DATABASE_URL', 'postgresql://postgres:123@localhost:5432/medical_system_test'
    )

    from sqlalchemy import event

    from app_factory import create_app

    app = create_app('testing')

    query_count = {'n': 0}
    statements = []

    findings = []
    with app.app_context():

        @event.listens_for(db.engine, 'before_cursor_execute')
        def _count(conn, cursor, statement, parameters, context, executemany):
            query_count['n'] += 1
            statements.append(statement[:120])

        client = app.test_client()
        client.post('/auth/login', data={'username': 'reception', 'password': 'ValidPass123!'})

        for path in HOT_PATHS:
            query_count['n'] = 0
            statements.clear()

            t0 = time.monotonic()
            resp = client.get(path)
            elapsed = time.monotonic() - t0

            count = query_count['n']
            status_flag = 'OK' if count <= THRESHOLD else f'SUSPICIOUS ({count})'
            print(
                f'{path:40s} {resp.status_code}  queries={count:3d}  {elapsed:.0f}ms  {status_flag}'
            )

            if count > THRESHOLD:
                from collections import Counter

                repeated = Counter(statements).most_common(5)
                for stmt, n in repeated:
                    if n > 2:
                        findings.append((path, n, stmt))
                        print(f'    {n}x: {stmt[:120]}')

    print()
    if findings:
        print(f'⚠️  {len(findings)} potential N+1 patterns found')
        return 1
    print('✅ No N+1 patterns detected')
    return 0


# Import db after create_app to avoid circular issues
from app.extensions import db  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main())
