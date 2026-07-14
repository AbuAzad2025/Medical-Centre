# Incident Log — Orphaned Tenant Rows

## 1. Incident Summary
| # | Incident ID | Date | Severity | Status |
|---|-------------|------|----------|--------|
| 1 | ORPHAN-2024-001 | 2024-01-15 | Medium | Resolved |

## 2. Root Cause Analysis
| Incident ID | Root Cause | Affected Tables |
|-------------|------------|-----------------|
| ORPHAN-2024-001 | Migration missed tenant_id assignment | users, patients |

## 3. Impact Assessment
| Incident ID | Impact | Affected Rows |
|-------------|--------|---------------|
| ORPHAN-2024-001 | Low | 23 rows |

## 4. Remediation Steps
| Incident ID | Action | Status | Owner | Due Date |
|-------------|--------|--------|-------|----------|
| ORPHAN-2024-001 | Backfill tenant_id | Done | DevOps | 2024-01-20 |

## 5. Action Items
| # | Incident ID | Issue | Description | Status | Target |
|---|-------------|-------|-------------|--------|--------|
| 1 | ORPHAN-2024-001 | Verify cleanup | Confirm all tenant_id=0 rows removed | Done | 2024-01-20 |
| 2 | ORPHAN-2024-001 | Add constraint | Add DB constraint to prevent tenant_id=0 | Done | 2024-01-25 |
| 3 | ORPHAN-2024-001 | Audit trigger | Add trigger to prevent future orphans | Done | 2024-01-30 |
| 4 | ORPHAN-2025-001 | Quarterly audit | Run audit_orphaned_tenant_rows.py quarterly | Open | 2025-07-01 |
| 5 | ORPHAN-2025-002 | CI integration | Add audit to CI pipeline | Open | 2025-07-15 |

---
*Last updated: 2026-07-14*