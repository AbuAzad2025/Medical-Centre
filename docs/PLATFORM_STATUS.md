# Platform Status

This document tracks the current operational status of the Medical System platform.

## Current State

- **Modularity & Independence (Phase 1–3): COMPLETE**
  - Cross-module service calls are gated by `@require_module` / `require_feature_service`
    (`feature_gate_service.py`) so disabled modules fail closed instead of triggering
    cross-tenant logic.
  - Notification fan-out is skipped (fail-closed) when the target module is disabled.
  - 14 pre-existing test failures resolved; remaining suite green.

## Tenant Isolation

- Row-Level Security (RLS) is enforced on the primary connection.
- All `db.session.commit()` / `db.session.rollback()` calls route through
  `utils.db_safety.safe_commit` / `safe_rollback`.

## Known Technical Debt

- Doctor dashboard / note-template `SystemConfig` rows are now correctly scoped by
  `tenant_id` (previously inserted with `NULL` tenant, causing unique-constraint
  collisions on repeated lookups).
- `safe_commit(..., reraise=True)` re-raises the original exception. Callers that need
  a wrapped error must handle the underlying exception type.

## Test Health

- Full regression suite passing. Module gating and notification guards covered by
  dedicated unit tests (`tests/test_module_require_service.py`,
  `tests/test_notification_module_guard.py`).
