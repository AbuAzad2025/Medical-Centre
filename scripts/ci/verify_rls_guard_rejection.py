"""
CI step: verify the RLS startup guard rejects superuser/BYPASSRLS roles.

Creates the Flask app with postgres superuser but WITHOUT RLS_BYPASS_ALLOWED,
expecting RuntimeError.  This proves the guard is active and effective.

Usage:  python scripts/ci/verify_rls_guard_rejection.py
"""
import os, sys

os.environ['APP_ENV'] = 'testing'
os.environ['SUPPRESS_LOGGING'] = '1'
os.environ['SKIP_PLATFORM_BOOTSTRAP'] = '1'
os.environ['WTF_CSRF_ENABLED'] = 'False'
os.environ['SECRET_KEY'] = 'ci-test-secret-key'

# Ensure DATABASE_URL connects as postgres superuser
dsn = os.environ.get('TEST_DATABASE_URL') or 'postgresql://postgres:testpass@localhost:5432/medical_test'
os.environ['SQLALCHEMY_DATABASE_URI'] = dsn

# CRITICAL: do NOT set RLS_BYPASS_ALLOWED — guard should fire
os.environ.pop('RLS_BYPASS_ALLOWED', None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app_factory import create_app

try:
    app = create_app('testing')
    print("FAIL: RLS startup guard did NOT reject postgres superuser")
    sys.exit(1)
except RuntimeError as e:
    msg = str(e)
    if 'RLS startup guard rejected' in msg:
        print(f"PASS: RLS startup guard rejected superuser: {msg[:80]}")
        sys.exit(0)
    else:
        print(f"FAIL: Unexpected RuntimeError: {msg}")
        sys.exit(1)
except Exception as e:
    print(f"FAIL: Unexpected exception: {type(e).__name__}: {e}")
    sys.exit(1)
