#!/usr/bin/env python3
"""
Verify RLS startup guard rejects superuser.

This script verifies that the RLS startup guard in app_factory.py
correctly rejects superuser connections when RLS_BYPASS_ALLOWED is not set.
"""

import os
import sys
import subprocess
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    """Verify RLS startup guard rejects superuser when bypass is not allowed."""
    print('Verifying RLS startup guard rejects superuser...')

    # Get database URL from environment (set by CI)
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print('ERROR: DATABASE_URL not set')
        return 1

    # Test 1: Without RLS_BYPASS_ALLOWED, superuser should be rejected
    print('Test 1: Testing without RLS_BYPASS_ALLOWED...')
    env = os.environ.copy()
    env.pop('RLS_BYPASS_ALLOWED', None)
    env['FLASK_ENV'] = 'testing'
    env['SECRET_KEY'] = 'test-secret-key-for-ci-testing-32bytes-minimum-length'
    env['APP_ENV'] = 'testing'

    # Try to create app - should fail with RuntimeError about RLS guard
    result = subprocess.run(
        [sys.executable, '-c', '''
import os
os.environ["RLS_BYPASS_ALLOWED"] = "0"
from app_factory import create_app
app = create_app("testing")
print("ERROR: Should have failed but didn't")
'''],
        capture_output=True, text=True, timeout=60, env=env
    )

    if result.returncode == 0:
        print('FAIL: App creation succeeded but should have been rejected by RLS guard')
        print('STDOUT:', result.stdout)
        return 1

    stderr_lower = result.stderr.lower()
    if 'rls startup guard rejected' in stderr_lower or 'rls startup guard rejected superuser' in stderr_lower:
        print('PASS: RLS startup guard correctly rejected superuser')
    else:
        print('FAIL: Expected RLS guard rejection message not found')
        print('STDOUT:', result.stdout)
        print('STDERR:', result.stderr)
        return 1

    # Test 2: With RLS_BYPASS_ALLOWED=1, superuser should be allowed
    print('\nTest 2: Testing with RLS_BYPASS_ALLOWED=1...')
    env['RLS_BYPASS_ALLOWED'] = '1'
    result = subprocess.run(
        [sys.executable, '-c', '''
import os
os.environ["RLS_BYPASS_ALLOWED"] = "1"
from app_factory import create_app
app = create_app("testing")
print("SUCCESS: App created with bypass allowed")
'''],
        capture_output=True, text=True, timeout=60, env=env
    )

    if result.returncode != 0:
        print('FAIL: App creation failed with bypass allowed')
        print('STDOUT:', result.stdout)
        print('STDERR:', result.stderr)
        return 1

    if 'SUCCESS' in result.stdout:
        print('PASS: App created successfully with bypass allowed')
    else:
        print('FAIL: Unexpected output')
        print('STDOUT:', result.stdout)
        return 1

    print('\nAll RLS guard tests passed!')
    return 0


if __name__ == '__main__':
    sys.exit(main())