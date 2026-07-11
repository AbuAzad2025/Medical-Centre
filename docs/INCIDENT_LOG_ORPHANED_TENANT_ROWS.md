# Incident Log: Orphaned Tenant Rows (tenant_id=0)

**Incident class:** `data-integrity` / orphaned-tenant-rows
**Tracking runbook:** `docs/RUNBOOK_ORPHANED_TENANT_ROWS.md`
**Service:** Medical System (multi-tenant)
**Opened:** 2026-07-07
**Owner:** Infrastructure Team
**Review cadence:** Monthly or after any change to tenant-isolation logic

---

## 1. Summary

Rows with `tenant_id=0` (the sentinel for backfilled NULLs) were detected across
tenant-scoped tables. The sentinel `0` is **not** a real tenant, so such rows are
orphaned and must be remediated. Root cause categories: pre-migration NULLs,
race conditions at tenant creation, bulk imports without a tenant, and (if recurring)
application-level bugs.

## 2. Detection

- Prometheus exporter (`metrics-exporter`, port `9180`) / Flask `/metrics`
  exposes `medical_orphaned_tenant_rows{table="__total__"}`.
- Grafana alert rule `MedicalSystem — Orphaned Tenant Rows Detected` fires when the
  total exceeds `0` for more than `5m`.

## 3. Impact

Orphaned rows bypass tenant isolation filters and can surface under the wrong tenant
or break tenant-scoped queries. They are a data-integrity and SaaS-isolation risk.

## 4. Root Cause

The R6 migration (`s2_001_tenant_id_not_null.py`) backfilled NULL
`tenant_id` values to the sentinel `0` and added a `SET NOT NULL` constraint.
Rows ending up with `tenant_id=0` are pre-migration orphans; any *new* orphans
after the migration indicate an application bug that must be fixed.

## 5. Action Items

| # | Incident ID | Issue | Description | Status | Target |
|---|---|---|---|---|---|
| 1 | INC-OTR-001 | Backfill NULL tenant_id | R6 migration `s2_001_tenant_id_not_null.py` backfilled NULL `tenant_id` to sentinel `0` and added `NOT NULL` constraint across tenant-scoped tables | Done | 2026-07-07 |
| 2 | INC-OTR-002 | Enforce tenant on every request | `set_tenant_context()` middleware in `app/core/tenant/middleware.py` assigns `g.current_tenant` for every request, preventing tenant-less inserts | Done | 2026-07-07 |
| 3 | INC-OTR-003 | Background-task tenant context | Celery tasks run under `TenantJobRunner` / `with tenant_context(tid)` so asynchronous writes carry a valid `tenant_id` | Done | 2026-07-07 |
| 4 | INC-OTR-004 | Monitoring & alerting | Prometheus exporter + Grafana alert rule `MedicalSystem — Orphaned Tenant Rows Detected` wired and notification channel configured | Done | 2026-07-07 |
| 5 | INC-OTR-005 | Remediation runbook | `docs/RUNBOOK_ORPHANED_TENANT_ROWS.md` published with audit/dry-run/fix workflow (`scripts/ops/audit_orphaned_tenant_rows.py`) | Done | 2026-07-07 |
| 6 | INC-OTR-006 | CI staleness guard | `scripts/ci/audit_stale_action_items.py` runs weekly to flag any action item left open past its target date | Done | 2026-07-07 |

## 6. Reference

- Runbook: `docs/RUNBOOK_ORPHANED_TENANT_ROWS.md`
- Audit tool: `scripts/ops/audit_orphaned_tenant_rows.py`
- Exporter: `scripts/ops/prometheus_exporter.py`
- Migration: `migrations/versions/s2_001_tenant_id_not_null.py`
- Dashboard: `monitoring/grafana_dashboard_tenant_isolation.json`
- Alert rule: `monitoring/grafana_alert_orphaned_rows.json`

> **Last updated:** July 7, 2026
> **Maintainer:** Infrastructure Team
