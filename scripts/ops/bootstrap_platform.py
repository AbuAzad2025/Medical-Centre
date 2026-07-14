#!/usr/bin/env python3
"""Platform bootstrap entrypoint for CI/production deployments.

Runs idempotent platform catalog bootstrap:
- Module definitions from MODULE_REGISTRY
- ProductBundle seed data
- SaaS package/version mirroring
- Developer config defaults

Usage: python -m scripts.ops.bootstrap_platform
"""

import os
import sys

# Ensure project root is on Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Ensure app context is available
os.environ.setdefault('APP_ENV', 'production')
os.environ.setdefault('FLASK_ENV', 'production')

def main():
    from app_factory import create_app
    from app.core.platform_bootstrap import run_platform_bootstrap

    app = create_app('production' if os.environ.get('FLASK_ENV') == 'production' else 'testing')

    with app.app_context():
        result = run_platform_bootstrap(quiet=False)
        print(f"Platform bootstrap result: {result}")
        return 0

if __name__ == '__main__':
    sys.exit(main())