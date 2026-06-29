#!/usr/bin/env python3
"""DEV ONLY — legacy Alembic wrapper. Prefer: flask db upgrade (production/CI)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import bootstrap_dev_script


def main() -> int:
    bootstrap_dev_script()
    print('DEPRECATED: use `flask db upgrade` or scripts/ci/verify_migrations.py in CI.')
    print('Running: python -m flask db upgrade')
    result = subprocess.run([sys.executable, '-m', 'flask', 'db', 'upgrade'], check=False)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
