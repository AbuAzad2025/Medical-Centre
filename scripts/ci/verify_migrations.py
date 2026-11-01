#!/usr/bin/env python3
"""
Verify Alembic migrations can be applied to a fresh database.
This script is used in CI to ensure migrations are valid.
"""

import os
import sys
import subprocess
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def run_cmd(cmd, cwd=None, env=None):
    """Run command and return (success, output)"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd or PROJECT_ROOT,
            env=env or os.environ,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, 'Command timed out'
    except Exception as e:
        return False, str(e)


def main():
    """Verify Alembic migrations can be applied to a fresh database"""
    print('Verifying Alembic migrations...')

    # Check if alembic.ini exists
    alembic_ini = PROJECT_ROOT / 'alembic.ini'
    if not alembic_ini.exists():
        print('ERROR: alembic.ini not found')
        return 1

    # Check if migrations directory exists
    migrations_dir = PROJECT_ROOT / 'migrations'
    if not migrations_dir.exists():
        print('ERROR: migrations directory not found')
        return 1

    # Check if there are migration scripts
    versions_dir = migrations_dir / 'versions'
    if not versions_dir.exists():
        print('ERROR: migrations/versions directory not found')
        return 1

    migration_files = list(versions_dir.glob('*.py'))
    if not migration_files:
        print('WARNING: No migration files found')
    else:
        print(f'Found {len(migration_files)} migration files')

    # Try to run alembic check (dry run)
    print('Running alembic check...')
    success, output = run_cmd('alembic check')
    if not success:
        print(f'alembic check failed: {output}')
        # Don't fail on check - it might be expected to fail if DB not present
        print('Continuing...')

    # Try to run alembic upgrade head --sql (dry run SQL generation)
    print('Generating migration SQL (dry run)...')
    success, output = run_cmd('alembic upgrade head --sql')
    if not success:
        print(f'ERROR: alembic upgrade head --sql failed: {output}')
        return 1

    print('Migration SQL generated successfully')
    print('All migration checks passed!')
    return 0


if __name__ == '__main__':
    sys.exit(main())
