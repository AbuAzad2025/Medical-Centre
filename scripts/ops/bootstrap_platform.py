#!/usr/bin/env python3
"""Production bootstrap: catalog + SaaS packages after migrations."""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('FLASK_APP', 'wsgi:app')


def main() -> int:
    from app_factory import create_app
    from app.core.platform_bootstrap import run_platform_bootstrap

    app = create_app(os.environ.get('FLASK_ENV', 'production'))
    with app.app_context():
        summary = run_platform_bootstrap(quiet=False)
        if summary.get('skipped'):
            print('Platform bootstrap skipped (SKIP_PLATFORM_BOOTSTRAP)')
            return 0
        print('OK', summary)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
