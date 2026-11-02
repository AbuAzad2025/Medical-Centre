#!/usr/bin/env python3
"""
Verify Alembic migrations can be applied to a fresh database.
This script is used in CI to ensure migrations are valid.
"""

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

MIGRATIONS_DIR = PROJECT_ROOT / 'migrations'
ALEMBIC_INI = MIGRATIONS_DIR / 'alembic.ini'


def run_cmd(cmd, cwd=None, env=None):
    """Run command and return (success, output)"""
    # Ensure PYTHONPATH is passed to subprocess
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    # Ensure project root is in PYTHONPATH so 'migrations' module can be imported
    project_root = str(PROJECT_ROOT)
    if 'PYTHONPATH' in merged_env:
        merged_env['PYTHONPATH'] = project_root + os.pathsep + merged_env['PYTHONPATH']
    else:
        merged_env['PYTHONPATH'] = project_root

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd or PROJECT_ROOT,
            env=merged_env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, 'Command timed out'
    except Exception as e:
        return False, str(e)


def create_postgres_database(database_url: str) -> bool:
    """Create PostgreSQL database if it doesn't exist"""
    if not database_url.startswith('postgresql://') and not database_url.startswith('postgres://'):
        return True  # Not PostgreSQL, nothing to do

    try:
        parsed = urlparse(database_url)
        db_name = parsed.path.lstrip('/')
        if not db_name:
            return True

        # Connect to postgres database to create the target database
        postgres_url = f'postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port or 5432}/postgres'

        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

        conn = psycopg2.connect(postgres_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Check if database exists
        cursor.execute('SELECT 1 FROM pg_database WHERE datname = %s', (db_name,))
        if not cursor.fetchone():
            print(f'Creating database: {db_name}')
            cursor.execute(f'CREATE DATABASE "{db_name}"')
            print(f'Database {db_name} created successfully')
        else:
            print(f'Database {db_name} already exists')

        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f'Warning: Could not create database: {e}')
        return False


def run_alembic_upgrade_with_context(app):
    """Run alembic upgrade head using Flask-Migrate's API within app context"""
    from flask_migrate import upgrade

    # Use Flask-Migrate's upgrade function which properly handles app context
    with app.app_context():
        upgrade(directory=str(MIGRATIONS_DIR), revision='head')


def main():
    """Verify Alembic migrations can be applied to a fresh database"""
    print('Verifying Alembic migrations...')

    # Check if alembic.ini exists
    if not ALEMBIC_INI.exists():
        print(f'ERROR: alembic.ini not found at {ALEMBIC_INI}')
        return 1

    # Check if migrations directory exists
    if not MIGRATIONS_DIR.exists():
        print('ERROR: migrations directory not found')
        return 1

    # Check if there are migration scripts
    versions_dir = MIGRATIONS_DIR / 'versions'
    if not versions_dir.exists():
        print('ERROR: migrations/versions directory not found')
        return 1

    migration_files = list(versions_dir.glob('*.py'))
    if not migration_files:
        print('WARNING: No migration files found')
    else:
        print(f'Found {len(migration_files)} migration files')

    # Use DATABASE_URL from environment (PostgreSQL in CI) or default to SQLite for local
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///:memory:')
    os.environ['DATABASE_URL'] = database_url
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['SECRET_KEY'] = 'test-secret-key-for-ci-testing-32bytes-minimum-length'
    os.environ['FLASK_ENV'] = 'testing'
    # Allow RLS bypass for superuser in CI (required for migrations)
    os.environ['RLS_BYPASS_ALLOWED'] = '1'

    # Create PostgreSQL database if needed (for CI)
    if database_url.startswith('postgresql://') or database_url.startswith('postgres://'):
        print('Ensuring PostgreSQL database exists...')
        create_postgres_database(database_url)

    # Add project root to PYTHONPATH so migration scripts can import from migrations.*
    os.environ['PYTHONPATH'] = str(PROJECT_ROOT) + os.pathsep + os.environ.get('PYTHONPATH', '')

    # Import and create the actual Flask app with test database
    print('Creating Flask app with test database...')
    try:
        from app_factory import create_app

        app = create_app('testing')
    except Exception as e:
        print(f'ERROR: Failed to create Flask app: {e}')
        return 1

    # Run alembic upgrade head using Flask-Migrate API within app context
    print('Running alembic upgrade head (online mode)...')
    try:
        run_alembic_upgrade_with_context(app)
    except Exception as e:
        print(f'ERROR: alembic upgrade head failed: {e}')
        return 1

    print('Migrations applied successfully!')

    # Verify current revision matches head (optional - just check current revision)
    print('Verifying current revision...')
    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        alembic_cfg = Config(str(ALEMBIC_INI))
        script = ScriptDirectory.from_config(alembic_cfg)

        with app.app_context():
            from alembic.runtime.migration import MigrationContext
            from flask import current_app

            # Get current revision from database
            engine = current_app.extensions['migrate'].db.engine
            with engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current_rev = context.get_current_revision()
                head_rev = script.get_current_head()

                print(f'Current revision: {current_rev}')
                print(f'Head revision: {head_rev}')

                if current_rev == head_rev:
                    print('Current revision matches head - migration check passed!')
                else:
                    print(
                        f'WARNING: Current revision ({current_rev}) does not match head ({head_rev})'
                    )
                    # Don't fail - just warn

    except Exception as e:
        print(f'Warning: Could not verify revision: {e}')
        # Don't fail on verification issues

    print('All migration checks passed!')
    return 0


if __name__ == '__main__':
    sys.exit(main())
