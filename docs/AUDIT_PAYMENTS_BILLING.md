# Audit Report: Payments & Billing Module

**Date:** 2026-07-31
**Scope:** `services/stripe_subscription_service.py`, `services/stripe_billing_service.py`, `services/payment_service.py`, `services/refund_service.py`, `routes/payment_routes.py`, `routes/saas_billing_routes.py`, `routes/accountant/*`, `routes/finance.py`
**Auditor:** OpenCode static analysis + runtime verification

---

## Fixes Applied (2026-07-31)

| # | Issue | File(s) Changed | Status |
|---|-------|-------------------|--------|
| 1 | Systemic `func.count()` tenant filter bypass | `app/shared/tenant_filter.py` | **FIXED** |
| 2 | Refund over-refund vulnerability | `services/refund_service.py` | **FIXED** |
| 3 | Payment idempotency race (IntegrityError 500) | `services/payment_service.py` | **FIXED** |
| 4 | Stripe webhook idempotency race (IntegrityError 500) | `services/stripe_subscription_service.py` | **FIXED** |
| 5 | `change_plan` package family validation | `services/stripe_billing_service.py` | **FIXED** |

**Test Results:** 68 targeted tests passed (pharmacy + POS + payment + refund + tenant context).

---

## CRITICAL — Systemic Tenant Isolation Bypass (affects entire codebase)

### Issue 1: `select(func.count()).select_from(Model)` bypasses ORM auto-filter
- **Mechanism:** The `tenant_filter_select` do_orm_execute hook (`app/shared/tenant_filter.py:379-398`) iterates `column_descriptions` and filters by `entity`. For `select(func.count()).select_from(Payment)` the `entity` is `None` (scalar count expression), so **no tenant filter is appended**.
- **Confirmed by runtime test:**
  ```python
  stmt = select(func.count()).select_from(Payment).filter(...)
  stmt.column_descriptions  # [{'entity': None, ...}]
  ```
- **Impact:** All dashboard/analytics count queries across the app count rows from **all tenants**, relying solely on PostgreSQL RLS `FORCE` policies (`s2_008`). If RLS is ever disabled, or on SQLite, or if a superuser connection bypasses RLS, every dashboard leaks cross-tenant financial and operational statistics.
- **Affected files in Payments & Billing:**
  - `routes/payment_routes.py` lines 48, 58, 61 (`payments_today`, `pending_payments`, `cancelled_payments`)
  - `routes/accountant/__init__.py` lines 40, 43, 49, 52, 56, 74, 79 (`total_payments`, `today_payments`, `total_invoices`, `open_invoices`, `paid_invoices`, `weekly_trend`, `monthly_trend`)
  - `routes/accountant/dashboard.py` line 56 (`open_invoices`)
  - `routes/finance.py` lines 40, 44, 49, 53, 58, 63 (`pending_payments`, `locked_visits`, `today_invoices`, `today_payments`, `pending_invoices`, `refunded_count`)
- **Severity:** CRITICAL (systemic, financial data exposure)
- **Note:** This pattern exists in ~100+ locations across lab, doctor, bed management, backup, and auth routes as well.

---

## HIGH — Payments

### Issue 2: Payment idempotency TOCTOU race
- **Location:** `services/payment_service.py` lines 51-60
- **Problem:** `create_payment` does a `SELECT` to check for existing `idempotency_key`, then `INSERT`s a new row. Two concurrent requests with the same key can both see no existing row, then both try to insert. The DB unique index `idx_payment_idempotency` (`models/payment.py:136`) catches one with an `IntegrityError`, which is caught by the outer `except Exception` and returned as `(False, str(e))` — a 500-style error instead of returning the existing payment.
- **Severity:** HIGH (double-charge possible under rare race; user sees error on legitimate retry)

### Issue 3: Refund over-refund vulnerability
- **Location:** `services/refund_service.py` lines 48-53, 113-184
- **Problem:**
  - `request_refund` only blocks duplicate **PENDING** requests for the same `payment_id`. Once a refund is executed, a new refund request can be created for the same payment.
  - `execute_refund` checks `request.status == APPROVED` and `refund_amount <= payment.amount` (checked at request time), but **never tracks cumulative refunded amount**. A payment of 100 could have refund requests of 60, then 40, then 50 — all approved and executed, totaling 150 in refunds.
  - No `with_for_update()` on `Payment`, `Invoice`, or `Receipt` rows during `execute_refund`. Concurrent execution of two refunds for the same payment could leave invoice `paid_amount` in an inconsistent state.
- **Severity:** HIGH (financial loss via over-refund)

---

## MEDIUM — Stripe Billing

### Issue 4: Stripe webhook idempotency race
- **Location:** `services/stripe_subscription_service.py` lines 170-222
- **Problem:** `ingest_webhook` calls `_check_idempotency` (lines 154-167) which checks Redis and then DB via `db.session.get(StripeWebhookEvent, event_id)`. If two identical webhooks arrive concurrently, both pass the check (the record hasn't been flushed/committed by the first yet), then both call `db.session.flush()` at line 191. The PK `event_id` collision causes an `IntegrityError` on the second. The first proceeds to process the event; the second fails with an unhandled exception that bubbles up as HTTP 500.
- **Mitigation:** The DB PK prevents duplicate rows, but the second request gets a 500 instead of a graceful `already_processed` response.
- **Severity:** MEDIUM (webhook replay from Stripe causes noise/error logs; no double-processing due to PK)

### Issue 5: Stripe API + local DB not atomic
- **Locations:**
  - `services/stripe_billing_service.py` lines 210-231 (`change_plan`)
  - `services/stripe_billing_service.py` lines 160-190 (`cancel_subscription`)
- **Problem:** These methods call the Stripe API first (external mutable operation), then update local `SubscriptionLine` / tenant state. If the local DB commit fails after Stripe succeeds, the tenant's Stripe subscription state diverges from the local database state. There is no compensating transaction, SAGA, or Stripe rollback.
- **Severity:** MEDIUM (state divergence; requires manual reconciliation)

### Issue 6: `change_plan` does not verify the new version belongs to the tenant
- **Location:** `services/stripe_billing_service.py` lines 205-208
- **Problem:** `db.session.get(PackageVersion, new_package_version_id)` fetches the version by PK with **no tenant filter**. RLS does not apply to `package_versions` because it is a global reference table (`TENANT_TABLES_NO_POLICY` in `s2_008`). Any tenant can request an upgrade to any package version ID (including those from other tenants' packages), because the method only validates the version exists, not that the tenant is entitled to it.
- **Severity:** MEDIUM (subscription plan manipulation)

---

## LOW — Defense-in-depth

### Issue 7: Payment dashboard missing explicit tenant filters on scalar counts
- **Same as Issue 1**, but specifically flagged because payment/accounting dashboards are high-value targets. All `func.count()` queries in `routes/payment_routes.py`, `routes/accountant/__init__.py`, and `routes/finance.py` should add explicit `.filter(Model.tenant_id == current_user.tenant_id)`.

### Issue 8: `payment_history` route uses `.all()` on unbounded query
- **Location:** `routes/payment_routes.py` line 427: `payments = query.order_by(Payment.created_at.desc()).all()`
- **Problem:** No pagination or `LIMIT`. A tenant with millions of payments could cause a memory/timeout issue. Also no explicit tenant filter on the base query (relies on auto-filter, which does apply here because `select(Payment)` has `entity=Payment`).
- **Severity:** LOW (performance / DoS)

---

## Verified Correct Patterns

- **Stripe webhook signature verification** (`stripe_subscription_service.py:39-47`) — uses `stripe.Webhook.construct_event` with the configured secret. Properly rejects invalid signatures with `StripeWebhookError`.
- **Webhook route CSRF exemption** (`saas_billing_routes.py:21`) — `@csrf.exempt` is appropriate for external POST webhooks.
- **Payment idempotency DB unique index** (`models/payment.py:136`) — `idx_payment_idempotency` on `(tenant_id, operation_type, idempotency_key)` correctly enforces uniqueness at the DB level.
- **Tenant resolution from Stripe metadata** (`stripe_subscription_service.py:50-61`) — reads `tenant_id` from checkout/session metadata first, falls back to `stripe_customer_id` in tenant settings. Reasonable mapping.
- **`process_payment` row lock** (`payment_routes.py:90`) — `select(Visit).filter_by(id=visit_id, tenant_id=g.tenant_id).with_for_update()` correctly locks the visit row during payment processing.
- **Refund request/approve/execute workflow** — three-step approval with role guards (`accountant`, `admin`, `manager`) is a proper segregation-of-duties pattern.

---

## Recommendations

1. **Fix the ORM auto-filter for `func.count()` queries** by enhancing `tenant_filter_select` to also inspect `select_from` entities when `column_descriptions` has no entity. This is a single-point fix that resolves the systemic issue across the entire app.
2. **Payment idempotency:** Use `INSERT ... ON CONFLICT DO NOTHING` or catch `IntegrityError` explicitly inside `create_payment` and return the existing row instead of `(False, error)`.
3. **Refund safety:** Add a `refunded_amount` column to `Payment` (or track in `RefundRequest`) and enforce `cumulative_refunds <= payment.amount` in `execute_refund`. Add `with_for_update()` on `Payment` and related `Invoice` rows during refund execution.
4. **Stripe state divergence:** Wrap Stripe API calls in a local DB transaction with a "pending Stripe operation" audit log; on DB failure, alert ops for reconciliation.
5. **Package version entitlement check:** In `change_plan`, verify the target `PackageVersion` belongs to a `Package` the tenant's current subscription is allowed to access.
6. **Webhook idempotency:** Set the Redis cache key (with a short TTL) **before** processing, or use `SELECT FOR UPDATE` on the `stripe_webhook_events` row (or rely on the PK conflict and catch it gracefully).

---

*Next step: Fix the systemic `func.count()` tenant filter bypass, then tackle the refund over-refund and payment idempotency race.*
