#!/usr/bin/env python3
"""DEPRECATED DEV ONLY — product_bundles is created by Alembic migrations + platform bootstrap."""
from __future__ import annotations

import sys

print(
    'DEPRECATED: product_bundles is managed by migrations and '
    'scripts/ops/bootstrap_platform.py. Do not run this script.',
    file=sys.stderr,
)
raise SystemExit(1)
