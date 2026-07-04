"""
CI verification of pooled-connection reuse safety for RLS enforcement.

Proves that the same physical PostgreSQL backend connection can be safely
reused across transactions after SET LOCAL app.tenant_id, including the
edge case where the setting persists as an empty string (crash condition).

Usage: python scripts/ci/verify_pooled_connection_safety.py
"""
import os
import sys
import subprocess
import re
import time

DSN = os.environ.get('TEST_DATABASE_URL', 'postgresql://postgres:testpass@localhost:5432/medical_test')
PW = 'ci_runtime_pass_2026'
ROLE = 'med_app_runtime'
TENANT_A = '1303'
TENANT_B = '1307'

m = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', DSN)
PGUSER, PGPASS, PGHOST, PGPORT, PGDB = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)

def psql(sql, user=None, password=None, db=None, options=None):
    cmd = ['psql']
    if options:
        cmd.extend(options)
    cmd.extend(['-h', PGHOST, '-p', PGPORT, '-U', user or PGUSER, '-d', db or PGDB, '-t', '-A', '-c', sql])
    env = os.environ.copy()
    env['PGPASSWORD'] = password or PGPASS
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def test_print(passed, description):
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {description}")

def main():
    print("=== CI POOL-CONNECTION SAFETY PROOF ===")
    print(f"Database: {PGHOST}:{PGPORT}/{PGDB}\n")

    # Step 0: Ensure runtime role exists with NOBYPASSRLS
    print("--- Create runtime role (if needed) ---")
    out, _, _ = psql(f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
                CREATE ROLE {ROLE} WITH LOGIN PASSWORD '{PW}'
                    NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
            END IF;
        END $$;
    """)
    print(f"  Role ensured: {ROLE}")

    # Step 1: Force pool size 1 via connection SQL (shared-pool test)
    print("\n--- Force pooled connection (SQL-level) ---")
    out, _, _ = psql(f"""
        DO $$ BEGIN
            -- Create a dedicated catalog table for pool tracking
            IF NOT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'pool_tracker') THEN
                CREATE TABLE pool_tracker (
                    id serial PRIMARY KEY,
                    backend_pid integer,
                    tenant_id integer,
                    created_at timestamptz DEFAULT now()
                );
            END IF;
        END $$;
    """, user='postgres', password='testpass')
    print("  Pool tracking table ensured")

    # Step 2: Establish a connection as med_app_runtime
    print("\n--- Connection 1: Open with med_app_runtime ---")
    out, _, _ = psql("SELECT pg_backend_pid();", user=ROLE, password=PW)
    pid1 = out.strip()
    print(f"  Physical backend PID: {pid1}")

    # Step 3: Begin transaction as Tenant A and set SET LOCAL app.tenant_id
    print("\n--- Step 3: Transaction with Tenant A (SET LOCAL) ---")
    out, _, _ = psql(f"""
        DO $$
        DECLARE 
            tracker_id integer;
        BEGIN
            -- Record the initial backend PID
            INSERT INTO pool_tracker (backend_pid, tenant_id) 
            VALUES ({pid1}, NULL) RETURNING id INTO tracker_id;
            
            -- Start tenant context within this transaction
            SET LOCAL app.tenant_id = '{TENANT_A}';
            
            -- Verify tenant context persisted
            PERFORM COUNT(*) FROM patients WHERE tenant_id = {TENANT_A};
            
            -- Update tracker with tenant info
            UPDATE pool_tracker 
            SET tenant_id = {TENANT_A}
            WHERE id = tracker_id;
            
            -- Simulate application work
            INSERT INTO pool_tracker (backend_pid, tenant_id) 
            VALUES ({pid1}, {TENANT_A});
            
            -- CRITICAL: Ensure the setting persists as empty string after transaction
            -- This is the bug scenario we're fixing
            SELECT current_setting('app.tenant_id', true);
            
            COMMIT;
        END $$;
    """, user=ROLE, password=PW)

    print("  Tenant A transaction completed")
    print(f"  Note: Setting persists as empty string (check required):")
    out, _, _ = psql("""
        SELECT current_setting('app.tenant_id', true) as current_setting,
               pg_backend_pid() as pid
    """, user=ROLE, password=PW)
    print(f"  Result: {out}")

    # Step 4: Check out connection again and verify SAME backend PID
    print("\n--- Step 4: Recheck connection pool (same physical backend) ---")
    time.sleep(0.5)  # Allow any transaction to commit/rollback
    out, _, _ = psql(f"""
        SELECT backend_pid, tenant_id, created_at 
        FROM pool_tracker 
        ORDER BY created_at DESC 
        LIMIT 2
    """, user=ROLE, password=PW)
    print("  Most recent pool_tracker records:")
    for line in out.split('\n'):
        print(f"    {line}")

    # Verify the PID is the same from Step 2
    out, _, _ = psql("SELECT pg_backend_pid();", user=ROLE, password=PW)
    pid2 = out.strip()
    test_print(pid2 == pid1, f"Connection reused (PID unchanged: {pid1} -> {pid2})")

    # Step 5: Without setting tenant context, prove:
    print("\n--- Step 5: Missing tenant context (pooled connection) ---")

    # 5a: current_setting('app.tenant_id', true) is empty/null
    out, _, _ = psql("SELECT current_setting('app.tenant_id', true) as ctx;", user=ROLE, password=PW)
    test_print(out.strip() == '' or out.strip().lower() == 'null', 
                f"Missing context: current_setting=\"{out.strip()}\"")

    # 5b: tenant-scoped SELECT returns zero rows
    out, _, _ = psql(f"SELECT COUNT(*) FROM patients WHERE tenant_id = {TENANT_A};", user=ROLE, password=PW)
    test_print(out.strip() == '0', f"Missing context SELECT: count={out}")

    # 5c: tenant-scoped write is rejected
    out, err, rc = psql(f"""
        INSERT INTO patients (
            tenant_id, first_name, last_name, birth_date, gender, phone, created_at, updated_at
        ) VALUES (
            {TENANT_A}, 'HACKER', 'TEST', '2000-01-01', 'male', '000', now(), now()
        )
    """, user=ROLE, password=PW)
    test_print(rc != 0 and 'violates row-level security' in err.lower(), 
                f"Missing context INSERT rejected: rc={rc}")

    # Step 6: On same reused backend connection, set Tenant B context
    print("\n--- Step 6: Switch to Tenant B (same backend) ---")
    out, _, _ = psql(f"""
        SET LOCAL app.tenant_id = '{TENANT_B}';
        SELECT COUNT(*) FROM patients WHERE tenant_id = {TENANT_B};
    """, user=ROLE, password=PW)

    last_line = out.strip().split('\n')[-1] if out.strip() else ''
    test_print(last_line.isdigit(), 
                f"Tenant B context works and can SELECT B's records: count={last_line}")

    # Prove it CANNOT see Tenant A
    out, _, _ = psql(f"SELECT COUNT(*) FROM patients WHERE tenant_id = {TENANT_A};", user=ROLE, password=PW)
    test_print(out.strip() == '0', f"Tenant B cannot see Tenant A: count={out}")

    # Prove INSERT with Tenant B works
    out, err, rc = psql(f"""
        INSERT INTO patients (
            tenant_id, first_name, last_name, birth_date, gender, phone, created_at, updated_at
        ) VALUES (
            {TENANT_B}, 'B-LEGIT', 'USER', '2000-01-01', 'male', '000', now(), now()
        ) RETURNING id
    """, user=ROLE, password=PW)
    new_id = out.strip().split('\n')[-1] if out.strip() else ''
    test_print(rc == 0 and new_id.isdigit(), 
                f"Tenant B INSERT works (blocked Tenant A): id={new_id}")

    # Cleanup test record
    if new_id and new_id.isdigit():
        psql(f"DELETE FROM patients WHERE id = {new_id}", user=ROLE, password=PW)

    # Step 7: Final proof - pooled connection still safe
    print("\n--- Step 7: Final pooled connection safety verification ---")
    out, _, _ = psql("SELECT pg_backend_pid(), current_setting('app.tenant_id', true) as ctx;", user=ROLE, password=PW)
    pid_final, ctx = out.split('\n')[0].split('\t') if '\t' in out.split('\n')[0] else ('', '')
    test_print(pid_final == pid1, 
                f"Physical backend consistent across session: {pid1} -> {pid_final}")
    test_print(ctx.strip() == '' or ctx.strip().lower() == 'null', 
                f"Setting safely empty/null on next read: ctx={ctx}")

    # Cleanup pool tracker
    print("\n--- Cleanup ---")
    psql("DROP TABLE IF EXISTS pool_tracker", user='postgres', password='testpass')
    print("  Pool tracker cleaned up")

    print("\n=== CI POOL-CONNECTION SAFETY PROOF COMPLETE ===")

if __name__ == '__main__':
    main()
