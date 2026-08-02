"""Create the dedicated non-superuser runtime application DB role.

Generates a random password, creates the role (idempotent), grants only the
minimum privileges needed for the web application to operate, and writes the
connection string into .env so the application can use it.

Run:  python scripts/dev/setup_runtime_role.py

Passwords are never written to Git — they go into .env (already gitignored).
"""

import os
import re
import secrets
import string
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

ENV_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
ROLE_NAME = 'med_app_runtime'
# Migration role — used only for schema changes (already postgres, kept separate)
MIGRATION_ROLE = 'med_app_migration'

PGHOST = os.environ.get('PGHOST', 'localhost')
PGPORT = os.environ.get('PGPORT', '5432')
PGUSER = os.environ.get('PGSUPER', 'postgres')
PGPASS = os.environ.get('PGSUPERPASS', '123')
PGDB = os.environ.get('PGDATABASE', 'medical_system')
PSQL = r'C:\Program Files\PostgreSQL\18\bin\psql.exe'

if not os.path.isfile(PSQL):
    # Try fallback path
    for p in [
        r'C:\Program Files\PostgreSQL\17\bin\psql.exe',
        r'C:\Program Files\PostgreSQL\16\bin\psql.exe',
    ]:
        if os.path.isfile(p):
            PSQL = p
            break


def psql(sql, **kwargs):
    cmd = [PSQL, '-h', PGHOST, '-p', PGPORT, '-U', PGUSER, '-d', PGDB, '-t', '-A']
    if kwargs.get('db'):
        cmd[cmd.index('-d') + 1] = kwargs['db']
    cmd.extend(['-c', sql])
    env = os.environ.copy()
    env['PGPASSWORD'] = kwargs.get('passwd', PGPASS)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
    if r.returncode != 0:
        print(f'  ERROR: {r.stderr.strip()}')
        return None
    return r.stdout.strip()


def generate_password(length=32):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# 1. Generate password
password = generate_password()
print(f'=== Setting up runtime DB role: {ROLE_NAME} ===')

# 2. Determine tenant-scoped tables (exclude known global/platform tables)
global_tables = {
    'alembic_version',
    'cpt_codes',
    'drg_codes',
    'drug_interactions',
    'enterprise_contract_entitlements',
    'icd10_codes',
    'lab_test_panel_items',
    'module_definitions',
    'notification_rules',
    'package_version_availability',
    'package_version_entitlements',
    'package_version_limits',
    'package_version_pricing',
    'package_versions',
    'packages',
    'platform_tenant_assumptions',
    'product_bundles',
    'stripe_webhook_events',
    'subscription_plans',
    'tenants',
}

# Get all public tables
tables_output = psql(
    'SELECT c.relname FROM pg_catalog.pg_class c '
    'JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace '
    "WHERE n.nspname = 'public' AND c.relkind = 'r' "
    'ORDER BY c.relname'
)
if tables_output is None:
    print('FATAL: Could not query tables. Check database connection.')
    sys.exit(1)

all_tables = set(tables_output.split('\n'))
tenant_tables = all_tables - global_tables - {'alembic_version'}

print(f'  Total public tables: {len(all_tables)}')
print(f'  Tenant-scoped tables (grant access): {len(tenant_tables)}')
print(f'  Global/excluded tables: {len(global_tables & all_tables)}')

# 3. Create the role (idempotent)
result = psql(
    f'DO $$ BEGIN '
    f"  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE_NAME}') THEN "
    f"    CREATE ROLE {ROLE_NAME} WITH LOGIN PASSWORD '{password}' NOSUPERUSER "
    f'    NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS; '
    f'  END IF; '
    f'END $$;'
)
if result is None:
    print('FATAL: Could not create runtime role.')
    sys.exit(1)
print(f'  Role {ROLE_NAME} created/already exists')

# 4. Grant schema USAGE
psql(f'GRANT USAGE ON SCHEMA public TO {ROLE_NAME};')
print('  Granted USAGE on schema public')

# 5. Grant table privileges (tenant-scoped only)
for tbl in sorted(tenant_tables):
    psql(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {tbl} TO {ROLE_NAME};')

# 6. Grant sequence USAGE
seqs_output = psql(
    "SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public'"
)
if seqs_output:
    for seq_name in seqs_output.split('\n'):
        seq_name = seq_name.strip()
        if seq_name:
            psql(f'GRANT USAGE ON SEQUENCE {seq_name} TO {ROLE_NAME};')

print(f'  Granted SELECT/INSERT/UPDATE/DELETE on {len(tenant_tables)} tables')
print('  Granted USAGE on sequences')

# Grant read on alembic_version so Flask-Migrate can check current revision
psql(f'GRANT SELECT ON TABLE alembic_version TO {ROLE_NAME};')
print('  Granted SELECT on alembic_version')

# Also grant the migration role if it doesn't exist (without login)
psql(
    f'DO $$ BEGIN '
    f"  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{MIGRATION_ROLE}') THEN "
    f"    CREATE ROLE {MIGRATION_ROLE} WITH LOGIN PASSWORD '{generate_password()}' "
    f'    NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS; '
    f'  END IF; '
    f'END $$;'
)
# Migration role needs CREATE on schema and full table access
psql(f'GRANT USAGE, CREATE ON SCHEMA public TO {MIGRATION_ROLE};')
for tbl in sorted(all_tables):
    psql(f'GRANT ALL PRIVILEGES ON TABLE {tbl} TO {MIGRATION_ROLE};')
if seqs_output:
    for seq_name in seqs_output.split('\n'):
        seq_name = seq_name.strip()
        if seq_name:
            psql(f'GRANT ALL PRIVILEGES ON SEQUENCE {seq_name} TO {MIGRATION_ROLE};')
print(f'  Created migration role: {MIGRATION_ROLE}')

# 7. Verify the role
verify = psql(
    f'SELECT rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, '
    f"rolreplication FROM pg_roles WHERE rolname = '{ROLE_NAME}'"
)
print(f'\n  Verification: {verify}')

# 8. Update .env with the new connection string
new_url = f'postgresql://{ROLE_NAME}:{password}@{PGHOST}:{PGPORT}/{PGDB}'

if os.path.isfile(ENV_PATH):
    with open(ENV_PATH, encoding='utf-8') as f:
        env_content = f.read()
    # Replace or add DATABASE_URL
    if re.search(r'^DATABASE_URL=', env_content, re.MULTILINE):
        env_content = re.sub(
            r'^DATABASE_URL=.*$', f'DATABASE_URL={new_url}', env_content, flags=re.MULTILINE
        )
    else:
        env_content += f'\n# Runtime application database connection\nDATABASE_URL={new_url}\n'
    # Store the runtime password for reference
    if re.search(r'^# Runtime application', env_content, re.MULTILINE):
        env_content = re.sub(
            r'^# Runtime application database connection\nDATABASE_URL=.*$',
            f'# Runtime application database connection\nDATABASE_URL={new_url}',
            env_content,
            flags=re.MULTILINE,
        )
    with open(ENV_PATH, 'w', encoding='utf-8') as f:
        f.write(env_content)
    print('\n  .env updated with new DATABASE_URL')
else:
    with open(ENV_PATH, 'w', encoding='utf-8') as f:
        f.write(f'# Runtime application database connection\nDATABASE_URL={new_url}\n')
    print('\n  .env created with DATABASE_URL')

print(f'\n  Runtime role:     {ROLE_NAME}')
print(f'  Migration role:   {MIGRATION_ROLE}')
print(f'  Connection saved to: {ENV_PATH}')
print('\n  WARNING: Keep this password safe. It will NOT be shown again.')
print(f'  Password: {password}')
print('\n=== DONE ===')
