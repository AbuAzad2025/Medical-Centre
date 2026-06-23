#!/usr/bin/env python3
"""Audit route coverage in nav registries — G-143."""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from app.shared.nav_audit import audit_manager_nav_coverage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--role', default='manager', choices=['manager'])
    args = parser.parse_args()

    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        if args.role == 'manager':
            missing = audit_manager_nav_coverage(app)
            if missing:
                print('MISSING FROM NAV:', *missing, sep='\n  ')
                return 1
        print(f'OK: {args.role} nav coverage')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
