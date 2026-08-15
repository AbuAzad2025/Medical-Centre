#!/usr/bin/env python3
"""Seed script to create default demo data for the Medical System."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def main():
    app = create_app('testing')
    with app.app_context():
        from tests.tenant_context import ensure_default_test_tenant
        ensure_default_test_tenant(app)
        print('Default tenant ensured successfully')


if __name__ == '__main__':
    main()