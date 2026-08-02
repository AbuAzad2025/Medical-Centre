#!/usr/bin/env python3
"""Verify the RLS startup guard rejects superuser/BYPASSRLS connections.

The guard in app_factory.py checks that the current database role does NOT
have SUPERUSER or BYPASSRLS when ENABLE_SAAS_MODE is true.  If `RLS_BYPASS_ALLOWED`
is not set, it raises RuntimeError.
"""

from __future__ import annotations

import os
import subprocess
import sys

_PROBE = """
import os
os.environ.pop('RLS_BYPASS_ALLOWED', None)
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:testpass@localhost:5432/postgres')
os.environ.setdefault('SECRET_KEY', 'probe')
os.environ.setdefault('ENABLE_SAAS_MODE', 'true')
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ['APP_ENV'] = 'testing'
try:
    from app_factory import create_app
    app = create_app('testing')
    print('UNEXPECTED: create_app succeeded without RLS_BYPASS_ALLOWED')
    raise SystemExit(1)
except RuntimeError as e:
    msg = str(e)
    if 'superuser' in msg.lower() or 'bypassrls' in msg.lower():
        print(f'OK  guard rejected: {msg}')
        raise SystemExit(0)
    print(f'UNEXPECTED RuntimeError: {msg}')
    raise SystemExit(1)
except Exception as e:
    print(f'UNEXPECTED {type(e).__name__}: {e}')
    raise SystemExit(1)
"""


def main() -> int:
    env = {k: v for k, v in os.environ.items() if k != 'RLS_BYPASS_ALLOWED'}
    env.pop('RLS_BYPASS_ALLOWED', None)

    result = subprocess.run(
        [sys.executable, '-c', _PROBE],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    print(result.stdout, end='')
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
