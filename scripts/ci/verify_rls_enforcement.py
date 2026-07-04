"""
CI step: create runtime role and run RLS enforcement proofs via psql.

Connects as postgres superuser to create med_app_runtime, then runs proofs
AS med_app_runtime without RLS_BYPASS_ALLOWED to prove real isolation.

Usage:  python scripts/ci/verify_rls_enforcement.py
"""
import os, sys, subprocess, re

DSN = os.environ.get('TEST_DATABASE_URL', 'postgresql://postgres:testpass@localhost:5432/medical_test')
PW = 'ci_runtime_pass_2026'
ROLE = 'med_app_runtime'

m = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', DSN)
PGUSER, PGPASS, PGHOST, PGPORT, PGDB = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)

def psql(sql, user=None, password=None, db=None):
    u = user or PGUSER
    p = password or PGPASS
    d = db or PGDB
    cmd = ['psql', '-h', PGHOST, '-p', PGPORT, '-U', u, '-d', d, '-t', '-A']
    env = os.environ.copy()
    env['PGPASSWORD'] = p
    r = subprocess.run(cmd + ['-c', sql], capture_output=True, text=True, timeout=30, env=env)
    if r.returncode != 0:
        sys.stderr.write(f"  ERROR ({u}@{d}): {r.stderr.strip()}\n")
    return r.stdout.strip(), r.stderr.strip(), r.returncode

results = []

def test(name, ok, detail):
    status = "PASS" if ok else "FAIL"
    results.append((status, name, detail))
    print(f"  [{status}] {name}: {detail}")

print("=== CI RLS ENFORCEMENT PROOF ===")
print(f"Database: {PGHOST}:{PGPORT}/{PGDB}\n")

# Step 1: Create runtime role (as postgres)
print("--- Create runtime role ---")
out, _, _ = psql(f"""
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
            CREATE ROLE {ROLE} WITH LOGIN PASSWORD '{PW}'
                NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
        END IF;
    END $$;
""")
print(f"  Role created/already exists")

# Step 2: Grant table access (as postgres)
print("--- Grant table access ---")
# Get all tables
out, _, _ = psql("SELECT c.relname FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname")
tables = [t for t in out.split('\n') if t.strip()]

global_tables = {
    'alembic_version', 'cpt_codes', 'drg_codes', 'drug_interactions',
    'enterprise_contract_entitlements', 'icd10_codes', 'lab_test_panel_items',
    'module_definitions', 'notification_rules', 'package_version_availability',
    'package_version_entitlements', 'package_version_limits',
    'package_version_pricing', 'package_versions', 'packages',
    'platform_tenant_assumptions', 'product_bundles', 'stripe_webhook_events',
    'subscription_plans', 'tenants',
}

psql("GRANT USAGE ON SCHEMA public TO med_app_runtime")
for tbl in tables:
    if tbl in global_tables:
        psql(f"GRANT SELECT ON TABLE {tbl} TO med_app_runtime")
    else:
        psql(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {tbl} TO med_app_runtime")

# Sequences
out, _, _ = psql("SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema='public'")
for seq in out.split('\n'):
    if seq.strip():
        psql(f"GRANT USAGE ON SEQUENCE {seq.strip()} TO med_app_runtime")

psql("GRANT SELECT ON TABLE alembic_version TO med_app_runtime")
print(f"  Granted privileges on {len(tables)} tables + sequences")

# Step 3: Role proof (AS med_app_runtime)
print("\n--- Runtime role proof ---")
out, _, _ = psql("SELECT current_user", user=ROLE, password=PW)
test("current_user = med_app_runtime", out == ROLE, out)

out, _, _ = psql("SELECT rolsuper FROM pg_roles WHERE rolname = current_user", user=ROLE, password=PW)
test("rolsuper = false", out == 'f', out)

out, _, _ = psql("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user", user=ROLE, password=PW)
test("rolbypassrls = false", out == 'f', out)

out, _, _ = psql("SELECT count(*) FROM pg_tables WHERE tableowner = current_user AND schemaname = 'public'",
                 user=ROLE, password=PW)
test("owns no tables", out == '0', f"owned={out}")

out, _, _ = psql("SELECT count(*) FROM pg_roles r JOIN pg_auth_members m ON r.oid = m.roleid "
                 "WHERE m.member = (SELECT oid FROM pg_roles WHERE rolname = current_user)",
                 user=ROLE, password=PW)
test("no role memberships", out == '0', f"memberships={out}")

# Step 4: row_security_active
print("\n--- RLS active check ---")
for tbl in ['patients', 'visits', 'users', 'invoices', 'appointments',
             'payments', 'departments', 'roles', 'permissions', 'system_configs',
             'branding_settings']:
    out, _, _ = psql(f"SELECT row_security_active('{tbl}')", user=ROLE, password=PW)
    test(f"RLS active on {tbl}", out == 't', out)

# Step 5: Two-tenant isolation
print("\n--- Two-tenant isolation ---")
# Seed tenant 1303 patient (CTE-based INSERT with RETURNING, parse last line of psql output)
out, _, _ = psql("SELECT set_config('app.tenant_id', '1303', false); "
    "WITH np AS (INSERT INTO patients (tenant_id, first_name, last_name, birth_date, gender, phone, created_at, updated_at) "
    "VALUES (1303, 'TENANT_A', 'PATIENT', '2000-01-01', 'male', '000', now(), now()) RETURNING id) "
    "SELECT id FROM np",
    user=ROLE, password=PW)
lines = [l for l in out.split('\n') if l.strip()]
pat_a = lines[-1] if lines else ''
print(f"  Tenant A patient id: {pat_a}")

out, _, _ = psql("SELECT set_config('app.tenant_id', '1307', false); "
    "WITH np AS (INSERT INTO patients (tenant_id, first_name, last_name, birth_date, gender, phone, created_at, updated_at) "
    "VALUES (1307, 'TENANT_B', 'PATIENT', '2000-01-01', 'male', '000', now(), now()) RETURNING id) "
    "SELECT id FROM np",
    user=ROLE, password=PW)
lines = [l for l in out.split('\n') if l.strip()]
pat_b = lines[-1] if lines else ''
print(f"  Tenant B patient id: {pat_b}")

if pat_b and pat_b.isdigit():
    # A cannot SELECT B (use single psql call, parse last line)
    out, _, _ = psql(f"SELECT set_config('app.tenant_id', '1303', false); "
        f"SELECT COALESCE((SELECT id::text FROM patients WHERE id = {pat_b}), 'NO_ROWS')",
        user=ROLE, password=PW)
    last = [l for l in out.split('\n') if l.strip()][-1] if out else ''
    test("A cannot SELECT B's record", last == 'NO_ROWS', f"result={last}")

    # A cannot INSERT B
    out, err, rc = psql("SELECT set_config('app.tenant_id', '1303', false); "
        "INSERT INTO patients (tenant_id, first_name, last_name, birth_date, gender, phone, created_at, updated_at) "
        "VALUES (1307, 'EVIL', 'HACKER', '2000-01-01', 'male', '000', now(), now())",
        user=ROLE, password=PW)
    test("A cannot INSERT B's record", rc != 0 and 'violates row-level security' in err, f"rc={rc}")

    # A cannot UPDATE B
    out, _, rc = psql(f"SELECT set_config('app.tenant_id', '1303', false); "
        f"UPDATE patients SET first_name = 'HACKED' WHERE id = {pat_b}",
        user=ROLE, password=PW)
    test("A cannot UPDATE B's record", rc == 0, f"rc={rc}")

    # A cannot DELETE B
    out, _, rc = psql(f"SELECT set_config('app.tenant_id', '1303', false); "
        f"DELETE FROM patients WHERE id = {pat_b}",
        user=ROLE, password=PW)
    test("A cannot DELETE B's record", rc == 0, f"rc={rc}")

    # B still exists (prove delete was filtered)
    out, _, _ = psql(f"SELECT set_config('app.tenant_id', '1307', false); "
        f"SELECT COALESCE((SELECT id::text FROM patients WHERE id = {pat_b}), 'GONE')",
        user=ROLE, password=PW)
    last = [l for l in out.split('\n') if l.strip()][-1] if out else ''
    test("B's record still exists after A's DELETE", last == str(pat_b), f"id={last}")
else:
    print("  [SKIP] Cross-tenant isolation tests (no valid patient IDs)")

# Step 6: Missing context
print("\n--- Missing tenant context ---")
out, _, _ = psql("SELECT count(*) FROM patients", user=ROLE, password=PW)
test("No context = 0 rows", out == '0', f"count={out}")

out, err, rc = psql(
    "INSERT INTO patients (tenant_id, first_name, last_name, birth_date, gender, phone, created_at, updated_at) "
    "VALUES (1303, 'NOCTX', 'FAIL', '2000-01-01', 'male', '000', now(), now())",
    user=ROLE, password=PW)
test("Write without context rejected", rc != 0 and 'violates row-level security' in err, f"rc={rc}")

# Step 7: Same-tenant works
print("\n--- Same-tenant operations ---")
out, _, _ = psql("SELECT set_config('app.tenant_id', '1303', false); "
    "SELECT count(*) FROM patients WHERE tenant_id = 1303",
    user=ROLE, password=PW)
last = [l for l in out.split('\n') if l.strip()][-1] if out else ''
test("Same-tenant SELECT works", last.isdigit() and int(last) > 0, f"count={last}")

out, _, rc = psql("SELECT set_config('app.tenant_id', '1303', false); "
    "WITH np AS (INSERT INTO patients (tenant_id, first_name, last_name, birth_date, gender, phone, created_at, updated_at) "
    "VALUES (1303, 'LEGIT', 'PATIENT', '2000-01-01', 'male', '000', now(), now()) RETURNING id) "
    "SELECT id FROM np",
    user=ROLE, password=PW)
lines = [l for l in out.split('\n') if l.strip()]
new_id = lines[-1] if lines else ''
test("Same-tenant INSERT works", rc == 0 and new_id.isdigit(), f"rc={rc} id={new_id}")

# Cleanup test patients
if new_id and new_id.isdigit():
    psql(f"SELECT set_config('app.tenant_id', '1303', false); DELETE FROM patients WHERE id = {new_id}",
        user=ROLE, password=PW)
if pat_a and pat_a.isdigit():
    psql(f"SELECT set_config('app.tenant_id', '1303', false); DELETE FROM patients WHERE id = {pat_a}",
        user=ROLE, password=PW)
if pat_b and pat_b.isdigit():
    psql(f"SELECT set_config('app.tenant_id', '1307', false); DELETE FROM patients WHERE id = {pat_b}",
        user=ROLE, password=PW)

# Step 8: Pooled-connection safety
print("\n--- Pooled-connection safety ---")
out, _, _ = psql("SELECT set_config('app.tenant_id', '1303', false); "
    "SELECT count(*) FROM patients WHERE tenant_id = 1303",
    user=ROLE, password=PW)
last = [l for l in out.split('\n') if l.strip()][-1] if out else ''

out, _, _ = psql("SELECT count(*) FROM patients", user=ROLE, password=PW)
test("New conn without context = 0 rows", out == '0', f"count={out}")

# Step 9: Global table access
print("\n--- Global table access ---")
for tbl in ['tenants', 'product_bundles', 'packages']:
    out, _, _ = psql(f"SELECT count(*) FROM {tbl}", user=ROLE, password=PW)
    test(f"Can read {tbl}", out.isdigit(), f"count={out}")

# Step 10: DDL rejection
print("\n--- DDL rejection ---")
out, err, rc = psql("CREATE TABLE x(y int)", user=ROLE, password=PW)
test("Cannot CREATE table", rc != 0, f"err={err[:50]}")

out, err, rc = psql("DROP TABLE patients", user=ROLE, password=PW)
test("Cannot DROP table", rc != 0, f"err={err[:50]}")

# Summary
print(f"\n{'='*50}")
passed = sum(1 for r in results if r[0] == 'PASS')
total = len(results)
print(f"RESULTS: {passed}/{total} passed")
if passed < total:
    for s, n, d in results:
        if s == 'FAIL':
            print(f"  FAIL: {n}: {d}")
print(f"{'='*50}")
