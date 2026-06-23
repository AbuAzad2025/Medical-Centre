#!/usr/bin/env python3
"""Audit sidebar nav link endpoints — Gate 6b."""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from app.shared.nav_audit import audit_manager_nav_coverage, audit_nav_link_endpoints


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit nav links')
    parser.add_argument('--check-404', action='store_true', help='Verify nav endpoints resolve')
    parser.add_argument('--role', default='manager', choices=['manager', 'owner'])
    args = parser.parse_args()

    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        broken = audit_nav_link_endpoints(app)
        if broken:
            print('BROKEN:', broken)
            return 1
        if args.role == 'manager':
            missing = audit_manager_nav_coverage(app)
            if missing:
                print('UNCOVERED MANAGER ROUTES:', missing)
                return 1
        print('OK: zero broken nav endpoints')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
