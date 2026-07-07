# Incident Log: Orphaned Tenant Rows (tenant_id=0)

**Purpose:** Track all occurrences of the `MedicalSystem — Orphaned Tenant Rows Detected` alert over time for trend analysis, root-cause patterns, and post-mortem follow-up.

**Referenced by:** [RUNBOOK_ORPHANED_TENANT_ROWS.md](RUNBOOK_ORPHANED_TENANT_ROWS.md)

---

## 1. Incident Template

Each time the alert fires, create a new entry using this template. Copy and paste it into the [Incident Log](#2-incident-log) section.

```
---
**INCIDENT-YYYY-MM-DD-NNN**

| Field | Value |
|-------|-------|
| **Date/Time (UTC)** | YYYY-MM-DD HH:MM |
| **Duration** | Xh YYm |
| **Total orphaned rows** | N |
| **Tables affected** | table_a, table_b |
| **Audit script run** | Yes / No |
| **Root cause** | pre-migration / app-bug / import / unknown |
| **Remediation** | --fix-to N / --delete / manual-SQL / none |
| **Verification** | Audit: clean / Alert: resolved |
| **On-call engineer** | @name |
| **GitHub issue** | #NNN |

**Summary:**
Brief description of what happened and what was done.

**Details:**
- Script output or key metrics
- Any manual queries run
- Links to Grafana snapshots or PRs
```

---

## 2. Incident Log

<!--
    ─────────────────────────────────────────────────────────────────────
    INSTRUCTIONS FOR TEAM MEMBERS
    ─────────────────────────────────────────────────────────────────────
    Add new incidents at the TOP of this list so the most recent is
    always first.  Use the template above, then paste the filled entry
    under the header below.  Keep the YYYY-MM-DD-NNN format for IDs.
    ─────────────────────────────────────────────────────────────────────
-->

<!-- ---------- New entries go ABOVE this line ---------- -->

<!--
    Example entry (delete once first real incident is logged):
---
**INCIDENT-2026-07-07-001**

| Field | Value |
|-------|-------|
| **Date/Time (UTC)** | 2026-07-07 14:30 |
| **Duration** | 35m |
| **Total orphaned rows** | 5 |
| **Tables affected** | patients, visits |
| **Audit script run** | Yes |
| **Root cause** | pre-migration |
| **Remediation** | --fix-to 5 |
| **Verification** | Audit: clean / Alert: resolved |
| **On-call engineer** | @jdoe |
| **GitHub issue** | #142 |

**Summary:**
Five rows (3 patients + 2 visits) from the S2-001 NULL backfill were
still orphaned.  Audited, identified the correct tenant, reassigned.

**Details:**
- Ran: `python scripts/ops/audit_orphaned_tenant_rows.py`
- Found 5 orphaned rows across patients (IDs 1423, 1789, 2201) and
  visits (IDs 5678, 8901)
- Verified patient data belonged to tenant_id=5 (Acme Medical Center)
- Ran: `python scripts/ops/audit_orphaned_tenant_rows.py --fix-to 5`
- Confirmed: re-audit returned clean
- Alert auto-resolved within 5 minutes
-->

*No incidents recorded yet.*

---

## 3. Incident Statistics

> **Update this section after each entry is added.**

| Metric | Value |
|--------|-------|
| **Total incidents** | 0 |
| **Last incident** | — |
| **MTTR (mean time to resolve)** | — |
| **Most common root cause** | — |
| **Most common remediation** | — |

---

## 4. Trend Tracker

> **Update this section after each entry is added.** Used to spot whether the fix rate is improving or regressing.

| Month | Incidents | Total Rows | Top Table |
|-------|-----------|------------|-----------|
| 2026-07 | — | — | — |

---

## 5. Action Items

> **Cross-reference:** Each time an incident root cause is `app-bug`, create a GitHub issue and track it here.

| # | Incident ID | Issue | Description | Status | Target |
|---|-------------|-------|-------------|--------|--------|
| — | — | — | — | — | — |

---

> **Last updated:** July 7, 2026  
> **Maintainer:** Infrastructure Team  
> **Review cadence:** After every incident; stats updated quarterly
