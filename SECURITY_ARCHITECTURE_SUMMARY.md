# Security Architecture Summary

> **Final reference for engineers joining the team.**  
> This document explains the protection layers currently enforced — what they are, why they exist, and how they compose into a defense-in-depth posture.  
> It does **not** propose new features. It records the baseline.

---

## Table of Contents

1. [Why This Architecture Exists](#1-why-this-architecture-exists)
2. [Layer 1 — Row-Level Security (RLS)](#2-layer-1--row-level-security-rls)
3. [Layer 2 — Application-Level Tenant Filtering](#3-layer-2--application-level-tenant-filtering)
4. [Layer 3 — NOT NULL Constraints](#4-layer-3--not-null-constraints)
5. [Layer 4 — Data Integrity Monitoring](#5-layer-4--data-integrity-monitoring)
6. [Layer 5 — CI Audits & Guardrails](#6-layer-5--ci-audits--guardrails)
7. [Composition — How the Layers Interlock](#7-composition--how-the-layers-interlock)
8. [Source Files Reference](#8-source-files-reference)

---

## 1. Why This Architecture Exists

The system is a **multi-tenant platform** serving multiple independent medical centers from a single database. Without deliberate isolation, every tenant's data — patient records, invoices, prescriptions, lab results — would be accessible to every other tenant. A single query mistake, a missing `WHERE tenant_id = ?`, or a bulk-update job without tenant context could leak or corrupt data across organizational boundaries.

The five layers below were built to eliminate that risk. They treat tenant isolation as a **default property of the system**, not something each developer must remember to implement per query. The system is fail-closed: if tenant context is missing, operations on tenant-scoped data are rejected by default.

---

## 2. Layer 1 — Row-Level Security (RLS)

### What it is

PostgreSQL Row-Level Security (RLS) is a **database-enforced** access control: every query against a tenant-scoped table is transparently filtered by `tenant_id`. The filter is defined as a PostgreSQL policy on each table and enforced by the database engine itself — no application code can bypass it unless connected as a superuser or a role with `BYPASSRLS`.

```sql
CREATE POLICY tenant_isolation ON patients USING (tenant_id = current_setting('app.tenant_id')::int);
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients FORCE ROW LEVEL SECURITY;
```

### Why we did this

- **Defense in depth:** Even if a bug in the Python ORM layer omits the `tenant_id` filter, the database refuses to return rows from the wrong tenant.
- **Protection against raw SQL actions:** A developer running `psql` with the application role, or a bulk-import script, is subject to the same RLS policies as the web application.
- **Protection for background workers:** Celery tasks and cron jobs must explicitly declare a tenant context; without it, `current_setting('app.tenant_id')` returns NULL and RLS returns zero rows.

### How it works

1. **Middleware** calls `SET LOCAL app.tenant_id = '<tid>'` at the start of every request.
2. **Celery tasks** call the same via `TenantJobRunner`, ensuring async work runs under the correct tenant identity.
3. **The ORM re-asserts** `SET LOCAL` before every statement (see `reassert_set_local` in `tenant_filter.py`), because a PostgreSQL `COMMIT` clears session-local settings.
4. **Runtime roles** (`med_app_runtime*`) are created without `BYPASSRLS` or `SUPERUSER`, so they cannot circumvent the policies.

### What tables are excluded

Nine tables have RLS **disabled** because they are cross-tenant by design:

- `tenants` — the tenant registry itself
- `roles`, `permissions`, `role_permissions`, `user_permissions`, `module_permissions`, `department_permissions` — auth and authorization tables shared across tenants
- `system_configs` — platform-wide configuration
- `branding_settings` — per-tenant UI branding (readable across tenants)
- `platform_audit_logs` — cross-tenant audit trail

---

## 3. Layer 2 — Application-Level Tenant Filtering

### What it is

Three SQLAlchemy event listeners (`tenant_filter.py`) that are **independent** of RLS and provide the first line of defense at the ORM level:

| Listener | Intercepts | What it does |
|----------|-----------|--------------|
| `tenant_filter_query` | Every `SELECT` via the ORM Query object | Automatically appends `WHERE tenant_id = <current>` to every query on tenant-scoped models |
| `auto_assign_tenant` | Every `INSERT` during session flush | Automatically sets `tenant_id` on new records if the code didn't explicitly provide one |
| `cross_tenant_guard` | Every `UPDATE`/`DELETE` during session flush | Raises `PermissionError` if the code attempts to modify a record belonging to a different tenant |
| `_guard_session_get` | Every `session.get(Model, pk)` call | Catches primary-key lookups that bypass the Query pipeline — verifies the loaded object's `tenant_id` matches the current context |

### Why we did this

- **Fail-closed defaults:** The ORM layer raises `TenantIsolationError` if any operation runs on a tenant-scoped model without a tenant context in SaaS mode.
- **Transparency:** Developers write `Patient.query.filter_by(name=...)` without manually adding `tenant_id`. The filter is automatic and invisible.
- **Bundle limits:** The same listener also enforces subscription limits (`max_users`, `max_patients`) at the point of creation, preventing over-provisioning without additional application checks.

### How "global" vs. "tenant-scoped" is determined

The system uses **dynamic introspection** of the SQLAlchemy model metadata. A model is:
- **Global** if it lacks a `tenant_id` column (no filter needed).
- **Global** if it has `tenant_id` but is in the `_GLOBAL_TENANT_TABLES` allowlist (9 tables listed above).
- **Tenant-scoped** in all other cases.

This means adding a new model to the database requires **zero changes** to the filtering layer. New tables with a `tenant_id` column are automatically tenant-scoped; new tables without one are automatically global.

---

## 4. Layer 3 — NOT NULL Constraints

### What it is

A database migration (`s2_001_tenant_id_not_null.py`) that added `SET NOT NULL` to the `tenant_id` column on every tenant-scoped table.

### Why we did this

Before this migration, `tenant_id` was nullable. This meant:

- A missing `tenant_id` silently created a row that would never appear in any tenant's query results (because both RLS and ORM filtering match on `tenant_id = <value>` and NULL ≠ any value).
- Such rows became **orphaned data** — they consumed space, could cause referential-integrity errors, and made data reconciliation difficult.

### What the migration did

1. Queried `information_schema.columns` to discover every public table with a `tenant_id` column.
2. Skipped the 9 global tables (same allowlist as RLS and tenant filtering).
3. For each tenant-scoped table:
   - **Backfilled** any NULL `tenant_id` rows to the sentinel value `0` (with a printed warning if any were found).
   - **Altered** the column to `SET NOT NULL`.
4. The sentinel `0` does not correspond to any real tenant — it is a flag indicating "_this row needs manual remediation_".

### Data integrity guarantee

After this migration, **new rows cannot be inserted without a `tenant_id`**. The database rejects them at the storage layer. Combined with the ORM's `auto_assign_tenant` listener and the RLS `WITH CHECK` policy, the system now provides three layers of protection against missing tenant assignment.

---

## 5. Layer 4 — Data Integrity Monitoring

### What it is

A production monitoring stack that continuously measures and alerts on the health of tenant isolation:

| Component | Purpose | Location |
|-----------|---------|----------|
| **Prometheus metrics endpoint** | Exposes `medical_orphaned_tenant_rows{table="..."}` gauge at `/metrics` on the Flask app and via a standalone sidecar on port `9180` | `routes/monitoring_routes.py`, `scripts/ops/prometheus_exporter.py` |
| **Grafana dashboard** | Visualizes total orphaned rows, affected tables, trend over time, and database health with a 30-second refresh | `monitoring/grafana_dashboard_tenant_isolation.json` |
| **Grafana alert rule** | Fires when `medical_orphaned_tenant_rows{table="__total__"} > 0` for more than 5 minutes | `monitoring/grafana_alert_orphaned_rows.json` |
| **SQL monitoring queries** | Reference queries for manual inspection and Grafana PostgreSQL data source | `monitoring/sql_queries.sql` |
| **Sidecar container** | `metrics-exporter` service in `docker-compose.yml` that runs independently of the Flask app | `docker-compose.yml` |

### Why we did this

- **Visibility:** Without monitoring, orphaned rows (`tenant_id=0`) could accumulate silently for weeks or months before being discovered during a manual audit.
- **Alert-driven response:** The 5-minute evaluation window prevents noise from transient conditions while ensuring that persistent data integrity issues are surfaced to the infrastructure team.
- **Operator tooling:** The `audit_orphaned_tenant_rows.py` script provides a single command for on-call engineers to audit, dry-run, and remediate (reassign or delete) orphaned rows.

### How the metrics are collected

Every 60 seconds (configurable), the exporter polls `information_schema.columns` to discover tenant-scoped tables, then runs `SELECT count(*) FROM <table> WHERE tenant_id = 0` on each. Results are cached and served to Prometheus scrapes in text format. A `__total__` label aggregates all per-table counts into a single gauge value used by the alert rule.

---

## 6. Layer 5 — CI Audits & Guardrails

### What it is

Every push and pull request on `main`/`develop` runs automated verification scripts that check the security and data-integrity posture:

| CI Step | What it verifies | Why |
|---------|-----------------|-----|
| `audit_rls_coverage.py` | Every tenant-scoped table has RLS enabled and forced | Catches new tables that were added without RLS policies |
| `verify_rls_enforcement.py` | Creates a restricted runtime role, connects as it, and proves RLS filtering works end-to-end | Validates that the RLS policies actually filter (not just exist on paper) |
| `verify_rls_guard_rejection.py` | Proves the Flask app refuses to start when connected as a superuser without `RLS_BYPASS_ALLOWED` | Ensures the startup guard cannot be accidentally removed |
| `audit_orphaned_tenant_rows.py` | Scans for sentinel `tenant_id=0` rows on every CI run | Catches regressions where the migration or application creates orphaned data |
| `audit_stale_action_items.py` | Weekly check of the incident log for unresolved action items older than 30 days | Ensures the team follows up on known data-integrity issues |

### Why we did this

- **Regression prevention:** A developer adding a new model with `tenant_id` but forgetting to enable RLS is caught before the code reaches production.
- **Guard against configuration drift:** The CI environment provisions a fresh PostgreSQL instance, runs migrations, and verifies RLS from first principles. This catches both code bugs and environment mismatches.
- **Post-bootstrap double-check:** The RLS audit runs twice: once after migrations and once after `bootstrap_platform.py` (which creates platform-level records). This catches tables created by the bootstrap process.
- **Traceability:** The incident log and stale-item checker ensure that data-integrity events are tracked, investigated, and resolved rather than forgotten.

---

## 7. Composition — How the Layers Interlock

The five layers are **independent but overlapping**. A failure in any single layer does not create a data-leak vulnerability because the remaining layers still enforce isolation.

### Example: a new INSERT

```
1. Application code creates Patient(name="...")
       ↓
2. ORM listener auto_assign_tenant sets tenant_id = current tenant
       ↓
3. Flush triggers PostgreSQL INSERT
       ↓
4. RLS WITH CHECK policy verifies tenant_id matches app.tenant_id
       ↓
5. NOT NULL constraint on tenant_id column (redundant, but fails closed)
```

If step 2 fails (no tenant context), steps 3–5 still prevent the row from being created:
- The ORM raises `TenantIsolationError` before the SQL is sent.
- If the ORM guard is somehow bypassed, the database RLS policy uses `USING (tenant_id = current_setting(...))`, which returns no rows for NULL context, effectively rejecting the write.
- If RLS is bypassed, the `NOT NULL` constraint still forces `tenant_id` to be provided.

### Example: a cross-tenant SELECT

```
1. Application queries Patient.query.filter_by(name="...")
       ↓
2. ORM listener tenant_filter_query appends WHERE tenant_id = current
       ↓
3. PostgreSQL RLS policy additionally filters WHERE tenant_id = current_setting(...)
       ↓
4. Returned rows must pass both filters
```

If step 2 is incorrect (wrong tenant filter), step 3 still applies the correct filter. If step 3 is missing (RLS not enabled on a new table), the CI audit (`audit_rls_coverage.py`) catches it on the next push.

### Attack surface summary

| Threat | Layer 1 (RLS) | Layer 2 (ORM) | Layer 3 (NOT NULL) | Layer 4 (Monitoring) | Layer 5 (CI) |
|--------|:---:|:---:|:---:|:---:|:---:|
| Missing `tenant_id` on INSERT | ✅ | ✅ | ✅ | — | — |
| Wrong `tenant_id` on INSERT | ✅ | ✅ | — | — | — |
| Missing `WHERE tenant_id` on SELECT | ✅ | ✅ | — | — | — |
| Wrong `tenant_id` on SELECT | ✅ | ✅ | — | — | — |
| Cross-tenant UPDATE/DELETE | ✅ | ✅ | — | — | — |
| New table without RLS | — | — | — | — | ✅ |
| Orphaned rows (tenant_id=0) | — | — | — | ✅ | ✅ |
| Unresolved action items | — | — | — | — | ✅ |

---

## 8. Source Files Reference

### Core implementation

| File | Role |
|------|------|
| `app/shared/tenant_filter.py` | ORM-level tenant filter listeners (auto-assign, query filter, cross-tenant guard) |
| `app/core/tenant/middleware.py` | Tenant resolution from path/subdomain/domain, `SET LOCAL app.tenant_id` |
| `app_factory.py` | RLS startup guard, blueprint registration |
| `migrations/versions/s2_001_tenant_id_not_null.py` | Migration: backfill NULLs, add `NOT NULL` on `tenant_id` |

### CI verification

| File | Role |
|------|------|
| `scripts/ci/audit_rls_coverage.py` | Verify all tenant-scoped tables have RLS enabled and forced |
| `scripts/ci/verify_rls_enforcement.py` | End-to-end: create runtime role, prove RLS works |
| `scripts/ci/verify_rls_guard_rejection.py` | Prove startup guard rejects superuser connections |
| `scripts/ci/audit_stale_action_items.py` | Weekly check for unresolved incident action items |
| `.github/workflows/ci.yml` | CI pipeline wiring all audit steps |

### Data integrity tooling

| File | Role |
|------|------|
| `scripts/ops/audit_orphaned_tenant_rows.py` | Standalone audit/fix for rows with `tenant_id=0` |
| `scripts/ops/prometheus_exporter.py` | Sidecar exporter for production monitoring |

### Production monitoring

| File | Role |
|------|------|
| `routes/monitoring_routes.py` | Flask `/metrics` endpoint |
| `monitoring/grafana_dashboard_tenant_isolation.json` | Grafana dashboard |
| `monitoring/grafana_alert_orphaned_rows.json` | Grafana alert rule |
| `monitoring/sql_queries.sql` | Reference SQL monitoring queries |
| `docker-compose.yml` | `metrics-exporter` sidecar service |

### Documentation

| File | Role |
|------|------|
| `docs/RUNBOOK_ORPHANED_TENANT_ROWS.md` | Incident response procedure when the alert fires |
| `docs/INCIDENT_LOG_ORPHANED_TENANT_ROWS.md` | Log for tracking orphaned-rows events over time |

---

> **Last updated:** July 7, 2026  
> **Baseline scope:** Security architecture as completed — no further changes planned without explicit project direction.
