# Manual Scripts — Not Alembic Revisions

This directory contains standalone Python scripts that are **not** Alembic
migration revisions. They must not be auto-discovered or auto-executed by
`alembic upgrade` or `flask db upgrade`.

## Files

### `fix_staff_work_schedule_tenant_id.py`

- **Type:** Manual tenant_id backfill script
- **Purpose:** Backfills NULL `tenant_id` on existing `StaffWorkSchedule`
  records by looking up the associated `User.tenant_id`.
- **Status:** Pending separate approval before execution.
- **Do not auto-run.** Execute manually only when explicitly instructed:
  ```
  python migrations/manual_scripts/fix_staff_work_schedule_tenant_id.py
  ```
