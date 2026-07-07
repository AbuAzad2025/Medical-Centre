-- ============================================================================
-- Tenant Isolation Monitoring Queries
-- ============================================================================
-- These queries work with:
--   - Grafana PostgreSQL data source
--   - pgAdmin / psql manual inspection
--   - Any SQL-compatible monitoring tool
--
-- The dynamic table discovery uses information_schema.columns to find all
-- tenant-scoped tables.  Global tables (tenants, roles, permissions, etc.)
-- are excluded — they naturally have nullable tenant_id.
-- ============================================================================

-- ───────────────────────────────────────────────────────────────────────────────
-- 1. Summary: total orphaned rows across all tenant-scoped tables
-- ───────────────────────────────────────────────────────────────────────────────

WITH tenant_tables AS (
    SELECT c.relname AS table_name
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    JOIN information_schema.columns col
      ON col.table_name = c.relname
     AND col.table_schema = 'public'
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
      AND col.column_name = 'tenant_id'
      AND c.relname NOT IN (
          'tenants', 'roles', 'permissions', 'role_permissions', 'user_permissions',
          'module_permissions', 'department_permissions',
          'system_configs', 'branding_settings', 'platform_audit_logs'
      )
)
SELECT count(*) AS table_count
FROM tenant_tables;

-- ───────────────────────────────────────────────────────────────────────────────
-- 2. Detail: orphaned rows per table (run dynamically per table)
-- ───────────────────────────────────────────────────────────────────────────────
-- Generate queries for each table:
SELECT format(
    'SELECT ''%s'' AS table_name, count(*) AS orphan_count FROM %I WHERE tenant_id = 0;',
    table_name, table_name
) AS query
FROM (
    SELECT c.relname AS table_name
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    JOIN information_schema.columns col
      ON col.table_name = c.relname
     AND col.table_schema = 'public'
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
      AND col.column_name = 'tenant_id'
      AND c.relname NOT IN (
          'tenants', 'roles', 'permissions', 'role_permissions', 'user_permissions',
          'module_permissions', 'department_permissions',
          'system_configs', 'branding_settings', 'platform_audit_logs'
      )
) t
ORDER BY table_name;

-- ───────────────────────────────────────────────────────────────────────────────
-- 3. UNION ALL: combined orphan count (for Grafana single-query panel)
-- ───────────────────────────────────────────────────────────────────────────────
-- Paste the generated queries from #2 into a UNION ALL wrapper.
-- Example (3 tables shown; repeat for all tenant-scoped tables):
--   SELECT 'patients' AS table_name, count(*) AS count FROM patients WHERE tenant_id = 0
--   UNION ALL
--   SELECT 'visits', count(*) FROM visits WHERE tenant_id = 0
--   UNION ALL
--   SELECT 'payments', count(*) FROM payments WHERE tenant_id = 0
--   ORDER BY count DESC;

-- ───────────────────────────────────────────────────────────────────────────────
-- 4. Grafana PostgreSQL alert query
-- ───────────────────────────────────────────────────────────────────────────────
-- NOTE: Dynamic table references require PL/pgSQL, not plain SQL.
-- Two options for Grafana alerts:
--
-- Option A: Use the Prometheus exporter (recommended).
--   medical_orphaned_tenant_rows{table="__total__"} > 0
--
-- Option B: Use the standalone script as a Grafana webhook check:
--   python scripts/ops/audit_orphaned_tenant_rows.py
--   → exit code 1 if orphans found, 0 if clean
--
-- Option C: For a PostgreSQL data source, use a Grafana alert with
-- the UNION ALL query from #3 (paste all generated queries) and set
-- alert condition: MAX(count) > 0.

-- ───────────────────────────────────────────────────────────────────────────────
-- 5. Sample IDs of orphaned rows (for debugging)
-- ───────────────────────────────────────────────────────────────────────────────
-- Find the first 10 IDs of orphaned rows in each table:
SELECT format(
    'SELECT ''%s'' AS table_name, id FROM %I WHERE tenant_id = 0 LIMIT 10;',
    table_name, table_name
) AS query
FROM (
    SELECT c.relname AS table_name
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    JOIN information_schema.columns col
      ON col.table_name = c.relname
     AND col.table_schema = 'public'
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
      AND col.column_name = 'tenant_id'
      AND c.relname NOT IN (
          'tenants', 'roles', 'permissions', 'role_permissions', 'user_permissions',
          'module_permissions', 'department_permissions',
          'system_configs', 'branding_settings', 'platform_audit_logs'
      )
) t
ORDER BY table_name;

-- ───────────────────────────────────────────────────────────────────────────────
-- 6. Grafana PostgreSQL dashboard variable query
-- ───────────────────────────────────────────────────────────────────────────────
-- Use this for a Grafana template variable named "table_name":
SELECT c.relname AS __text
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
JOIN information_schema.columns col
  ON col.table_name = c.relname
 AND col.table_schema = 'public'
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
  AND col.column_name = 'tenant_id'
  AND c.relname NOT IN (
      'tenants', 'roles', 'permissions', 'role_permissions', 'user_permissions',
      'module_permissions', 'department_permissions',
      'system_configs', 'branding_settings', 'platform_audit_logs'
  )
ORDER BY c.relname;
