# Runbook: Orphaned Tenant Rows (tenant_id=0) Alert

**Alert name:** `MedicalSystem — Orphaned Tenant Rows Detected`  
**Severity:** `warning`  
**Category:** `data-integrity`  
**Team:** `infrastructure`  
**SLO:** Investigate within 30 minutes of page; remediate within 2 hours.

---

## Table of Contents

1. [Alert Overview](#1-alert-overview)
2. [What Triggers This Alert](#2-what-triggers-this-alert)
3. [Initial Triage](#3-initial-triage)
4. [Investigation](#4-investigation)
5. [Remediation](#5-remediation)
6. [Post-Fix Verification](#6-post-fix-verification)
7. [Prevention](#7-prevention)
8. [Reference](#8-reference)

---

## 1. Alert Overview

The Grafana alert rule `MedicalSystem — Orphaned Tenant Rows Detected` fires when the **total count of rows with `tenant_id=0` across all tenant-scoped tables** exceeds 0 for more than 5 continuous minutes.

The metric `medical_orphaned_tenant_rows{table="__total__"}` is exposed by the Prometheus exporter (sidecar container `metrics-exporter` on port `9180`, or the Flask `/metrics` endpoint).

### Why does tenant_id=0 exist?

The R6 migration (`s2_001_tenant_id_not_null.py`) backfilled any rows that had a NULL `tenant_id` to the sentinel value **0**, then added a `SET NOT NULL` constraint. Rows ending up with `tenant_id=0` are **orphaned** — they don't belong to any real tenant (the `tenants` table has no row with `id=0`). This can happen when:

| Cause | Description |
|-------|-------------|
| **Pre-migration NULLs** | Rows created before the `tenant_id NOT NULL` constraint existed, where the application logic failed to assign a tenant |
| **Race condition at tenant creation** | A row is created between the migration and proper tenant assignment |
| **Bulk import without tenant** | Data loaded via SQL scripts or migrations that omitted `tenant_id` |
| **Application bug** | Code path that creates records without setting `tenant_id` |

> **The sentinel value 0 is NOT a real tenant.** If the migration ran correctly, no new rows should be created with `tenant_id=0` because the `NOT NULL` constraint forces every insert to provide a valid tenant_id. If you see new orphaned rows appearing after the migration, there is an **application-level bug** that must be fixed.

---

## 2. What Triggers This Alert

### PromQL condition

```
medical_orphaned_tenant_rows{table="__total__"} > 0
```

- **Evaluation interval:** Every 30s (dashboard refresh) / 1min (alert rule)
- **Duration:** `for: 5m` — must be sustained for 5 minutes before firing
- **No-data state:** `OK` — the alert won't fire if the metric is absent (e.g., exporter is down)
- **Error state:** `Alerting` — if the exporter errors out, the team is notified

### Notification channels

The alert rule fires with labels:
- `severity=warning`
- `team=infrastructure`
- `category=data-integrity`

Configure notification channels via Grafana:
- **Slack/PagerDuty/MSTeams** → `#infrastructure-alerts`
- **Email** → infrastructure-team@example.com

---

## 3. Initial Triage

When the alert fires, follow these steps.

### Step 1 — Acknowledge the alert

Mark the alert as acknowledged in Grafana (prevents duplicate notifications).

### Step 2 — Check the dashboard

Open the **Medical System — Tenant Isolation** dashboard (UID: `medical-tenant-isolation`).

- **Total Orphaned Rows** stat panel — confirms the raw count
- **Affected Tables** stat panel — shows how many tables have orphaned rows
- **Orphaned Rows per Table (Time Series)** — shows the trend (is it growing?)
- **Current Orphaned Rows (Table)** — shows the per-table breakdown

Key questions:
- **Is the count growing?** If yes, there is an active application bug creating new orphans.
- **Is it stable or declining?** If stable, this is likely pre-existing data from the migration backfill.

### Step 3 — Check the exporter health

```bash
# Docker sidecar
docker compose ps metrics-exporter
docker compose logs metrics-exporter --tail=20

# Direct curl
curl -s http://localhost:9180/metrics | head -5

# If using Flask /metrics endpoint
curl -s http://localhost:8080/metrics | head -5
```

Expected:
```
medical_db_up 1
medical_orphaned_tenant_rows{table="__total__"} 5
```

If `medical_db_up 0`, the exporter cannot reach the database — fix the DB connection first.

### Step 4 — Determine if this is a new incident or recurring

- **New incident:** Orphaned rows were never detected before
- **Recurring:** This is a repeat — check if a previous fix was reverted or incomplete

---

## 4. Investigation

### 4.1 — Run the audit script (recommended)

```bash
# SSH into the production box, docker exec, or run directly

python scripts/ops/audit_orphaned_tenant_rows.py
```

Output example:
```
🔍 Scanning 112 tenant-scoped tables for tenant_id=0...

  ⚠️  patients: 3 orphaned row(s)
       Sample IDs: [1423, 1789, 2201]
  ⚠️  visits: 2 orphaned row(s)
       Sample IDs: [5678, 8901]
  ✅  invoices: clean
  ✅  payments: clean
  ...

⚠️  TOTAL: 5 orphaned row(s) across 2 table(s)
```

### 4.2 — Run with dry-run to preview

```bash
python scripts/ops/audit_orphaned_tenant_rows.py --dry-run
```

Same output as above but with `🔷 DRY RUN — would reassign to tenant_id=5 5 rows` appended. Use dry-run **before any destructive operation**.

### 4.3 — Manual SQL inspection

Use the Grafana dashboard's table view for a quick snapshot. For deeper investigation:

```bash
# Connect to production DB
psql $DATABASE_URL
```

```sql
-- Are the orphaned rows from recent data (active bug) or old data?
SELECT table_name, min(id), max(id), min(created_at), max(created_at)
FROM (
    SELECT id, 'patients' AS table_name, created_at
    FROM patients WHERE tenant_id = 0
    UNION ALL
    SELECT id, 'visits', created_at
    FROM visits WHERE tenant_id = 0
    -- ... repeat for all affected tables
) orphans
GROUP BY table_name;
```

```sql
-- Check if there are related rows in other tables
-- Example: if a patient is orphaned, do they have visits/invoices?
SELECT 'patient' AS type, p.id, p.name,
       (SELECT count(*) FROM visits v WHERE v.patient_id = p.id) AS visit_count,
       (SELECT count(*) FROM invoices i WHERE i.patient_id = p.id) AS invoice_count
FROM patients p WHERE p.tenant_id = 0;
```

### 4.4 — Determine Root Cause

| Finding | Likely Root Cause | Action |
|---------|-------------------|--------|
| Rows are old (pre-migration timestamps) | Pre-existing NULLs from the backfill | Remediate as below, no further action |
| Rows are recent (post-migration timestamps) | Application bug or missing tenant middleware | **Fix the bug in code** before remediating |
| Rows are from bulk import | Manual SQL or ETL job omitted tenant_id | Add tenant_id to the import script |
| Rows have realistic tenant_id (not 0) but are in the wrong tenant | Data migration error | Use `--fix-to <real_tenant_id>` |

---

## 5. Remediation

Two options, depending on context. **Always run `--dry-run` first.**

### Option A: Reassign to a real tenant (safer)

If the orphaned rows belong to a known tenant, reassign them:

```bash
# Dry-run first
python scripts/ops/audit_orphaned_tenant_rows.py --fix-to 5 --dry-run

# Verify the target tenant exists
psql $DATABASE_URL -c "SELECT id, name FROM tenants WHERE id = 5;"

# Apply the fix
python scripts/ops/audit_orphaned_tenant_rows.py --fix-to 5
```

The script validates that tenant `5` exists before making any changes. All updates are wrapped in a single transaction.

**When to use this:** The orphaned rows belong to a real, active tenant and should be preserved.

### Option B: Delete orphaned rows (cleaner)

If the orphaned rows are garbage data (test records, failed imports, duplicates):

```bash
# Dry-run first
python scripts/ops/audit_orphaned_tenant_rows.py --delete --dry-run

# Apply the fix
python scripts/ops/audit_orphaned_tenant_rows.py --delete
```

**When to use this:** The data is unrecoverable, test-only, or causes referential integrity issues.

#### Before deleting, check for referential integrity

Deleting orphaned rows might violate foreign key constraints. The audit script only shows direct `tenant_id=0` rows, but other tables might reference them. Always check:

```sql
-- Example: if deleting orphaned patients, check for child records
SELECT id FROM patients WHERE tenant_id = 0
AND id IN (SELECT patient_id FROM visits);
```

If child records exist, you have two choices:
1. Use `--fix-to` instead of `--delete` to preserve the chain
2. Delete child records first (requires manual SQL intervention)

### Option C: Live Grafana query fix (for small counts)

For 1–2 rows that are urgent, use the Grafana PostgreSQL data source to run:

```sql
UPDATE patients SET tenant_id = 5 WHERE id IN (1423, 1789, 2201) AND tenant_id = 0;
```

Then verify the dashboard clears. This is a surgical fix for emergencies only.

---

## 6. Post-Fix Verification

### 6.1 — Confirm the alert resolves

After remediation:

1. **Run the audit script** to confirm 0 orphaned rows:
   ```bash
   python scripts/ops/audit_orphaned_tenant_rows.py
   # Expected: ✅ No orphaned rows found — data integrity is clean!
   ```

2. **Check the dashboard** — the "Total Orphaned Rows" stat should drop to 0 within 30s (dashboard refresh interval)

3. **Wait for the alert to auto-resolve** — after 5 minutes of the metric being 0, the alert will automatically resolve in Grafana

### 6.2 — Verify the fix

```bash
# Confirm tenant_id=0 count is 0
curl -s http://localhost:9180/metrics | grep medical_orphaned_tenant_rows

# Verify the reassigned rows are accessible by the target tenant
psql $DATABASE_URL -c "SELECT count(*) FROM patients WHERE tenant_id = 5 AND id IN (1423, 1789, 2201);"
```

### 6.3 — Log the incident

Record the following in the incident log:
- Alert timestamp and duration
- Tables affected and row count
- Root cause (pre-migration vs. application bug vs. import)
- Remediation action taken (`--fix-to` or `--delete`)
- Verification result

---

## 7. Prevention

### 7.1 — Application-level guards (code fix required)

If new orphaned rows appear post-migration, the application has a bug. Common causes:

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Rows created without tenant | Middleware didn't set `g.current_tenant` | Check `set_tenant_context()` in `app/core/tenant/middleware.py` |
| Celery tasks creating orphaned rows | Background task lacks tenant context | Use `TenantJobRunner` or `with tenant_context(tid)` |
| Bulk import scripts | Script omitted tenant filter | Add `WHERE tenant_id IS NOT NULL` guard |
| API endpoint creating data without tenant | Missing `@tenant_required` decorator | Add guard to the endpoint |

### 7.2 — Database-level guard

The `NOT NULL` constraint on `tenant_id` prevents new NULLs, but doesn't prevent `tenant_id=0`. For a stronger guarantee:

```sql
-- Add a CHECK constraint (discuss with team — may break existing code)
ALTER TABLE patients ADD CONSTRAINT patients_tenant_id_check CHECK (tenant_id > 0);
```

> ⚠️ **Caution:** Adding a CHECK constraint requires verifying that no code path inserts `tenant_id=0`. If any code does this intentionally (unlikely), it will break.

### 7.3 — Monitoring

The alert rule already covers detection. Ensure the following are in place:

- [ ] Prometheus is scraping `metrics-exporter:9180/metrics`
- [ ] Grafana alert rule is firing correctly
- [ ] Notification channel is configured
- [ ] Dashboard is accessible to the infrastructure team

---

## 8. Reference

### Related files

| File | Purpose |
|------|---------|
| `scripts/ops/audit_orphaned_tenant_rows.py` | Primary audit/fix tool — run via `docker compose exec metrics-exporter python scripts/ops/audit_orphaned_tenant_rows.py` or with `DATABASE_URL` set on the host |
| `scripts/ops/prometheus_exporter.py` | Standalone Prometheus exporter (sidecar) for metric collection |
| `routes/monitoring_routes.py` | Flask `/metrics` endpoint (alternative to sidecar) |
| `monitoring/grafana_dashboard_tenant_isolation.json` | Grafana dashboard for visualizing orphaned rows |
| `monitoring/grafana_alert_orphaned_rows.json` | Grafana alert rule definition |
| `monitoring/sql_queries.sql` | SQL queries for manual inspection |
| `docker-compose.yml` | `metrics-exporter` service definition |
| `migrations/versions/s2_001_tenant_id_not_null.py` | Migration that backfilled NULLs to 0 and added NOT NULL |

### Quick commands

```bash
# Audit — how many orphaned rows exist?
docker compose exec metrics-exporter python scripts/ops/audit_orphaned_tenant_rows.py

# Dry-run reassignment
docker compose exec metrics-exporter \
    python scripts/ops/audit_orphaned_tenant_rows.py --fix-to 5 --dry-run

# Apply reassignment
docker compose exec metrics-exporter \
    python scripts/ops/audit_orphaned_tenant_rows.py --fix-to 5

# Dry-run deletion
docker compose exec metrics-exporter \
    python scripts/ops/audit_orphaned_tenant_rows.py --delete --dry-run

# Apply deletion
docker compose exec metrics-exporter \
    python scripts/ops/audit_orphaned_tenant_rows.py --delete

# Check exporter health
docker compose ps metrics-exporter
docker compose logs metrics-exporter --tail=20
curl -s http://localhost:9180/metrics | grep medical_orphaned_tenant_rows

# Check the migration state (if you suspect new orphans are from a rollback)
docker compose exec app flask db current
```

### Grafana links

| Resource | Location |
|----------|----------|
| Dashboard | Grafana → Dashboards → **Medical System — Tenant Isolation** |
| Alert rule | Grafana → Alerting → Alert rules → **MedicalSystem — Orphaned Tenant Rows Detected** |
| Notification channels | Grafana → Alerting → Contact points |

---

> **Last updated:** July 7, 2026  
> **Maintainer:** Infrastructure Team  
> **Review cadence:** Monthly or after any change to tenant isolation logic
