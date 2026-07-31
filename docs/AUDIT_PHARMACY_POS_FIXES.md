# Audit Report: Pharmacy / POS Stock & Ledger Fixes

**Date:** 2026-07-31
**Scope:** `services/inventory_ledger_service.py`, `services/pharmacy_sale_service.py`, `routes/medication_routes/pos.py`, `routes/medication_routes/prescriptions.py`
**Auditor:** OpenCode static analysis + targeted fix verification

---

## 1. Identified Issues

### Issue 1 — InventoryLedgerService.record_movement schema mismatch (HIGH)
- **Location:** `services/inventory_ledger_service.py` lines 31-41
- **Problem:** `record_movement()` constructed `StockMovement` with kwargs `unit_cost=` and `created_by=`. The `StockMovement` model (`app/modules/workflows/stock_models.py` lines 11-24) has **neither column** — it uses `performed_by` instead. Additionally `before_quantity` and `after_quantity` are `nullable=False` but were never set. This caused a guaranteed `TypeError` at construction time (invalid keyword) followed by an `IntegrityError` at flush (NOT NULL violation). No production caller existed (only a module-gate test), so the broken code was latent dead code that would crash the moment any feature tried to wire it in.
- **DB Schema Confirmation:** `prod_baseline_20260622.py` lines 2170-2189 confirm `stock_movements` table contains `tenant_id`, `medication_id`, `movement_type`, `quantity`, `before_quantity`, `after_quantity`, `reference_type`, `reference_id`, `batch_number`, `expiry_date`, `performed_by`, `notes`, `created_at` — **no `unit_cost` or `created_by` column**.

### Issue 2 — Divergent sale paths: two sources of truth, no ledger (HIGH)
- **Locations:**
  - `routes/medication_routes/pos.py` line 148 — decrements `med.stock_quantity` directly
  - `routes/medication_routes/prescriptions.py` lines 135-139 — decrements `med.stock_quantity` directly
  - `services/pharmacy_sale_service.py` lines 38-61 — **does not decrement stock at all**
- **Problem:** Three distinct stock-mutation paths existed. None of them wrote `stock_movements` ledger rows. `Medication.stock_quantity` (a scalar column) and `InventoryLedgerService.current_stock()` (computed from ledger) were two independent sources of truth that diverged permanently because the ledger was never populated.

### Issue 3 — Non-atomic stock check / decrement (HIGH)
- **Locations:**
  - `routes/medication_routes/pos.py` lines 124-148 — reads `stock_quantity`, checks `if med.stock_quantity < qty`, then decrements without any row-level lock
  - `routes/medication_routes/prescriptions.py` lines 122-139 — same pattern
- **Problem:** Two concurrent requests for the same medication could both read `stock_quantity = 10`, both pass the check, both decrement. The DB `chk_medication_stock >= 0` CheckConstraint (`prod_baseline_20260622.py` line 560) would turn the loser into an unhandled `IntegrityError` (HTTP 500) rather than a graceful "insufficient stock" response. The only existing `with_for_update()` usage in the pharmacy flow was in `routes/payment_routes.py` line 90.

### Issue 4 — api_sales_list missing explicit tenant filter & customer_name bug (LOW)
- **Location:** `routes/medication_routes/pos.py` lines 235, 251
- **Problem:**
  - Base query `q = select(PharmacySale)` had **no explicit tenant filter**, relying solely on the `do_orm_execute` auto-filter and RLS. This is a defense-in-depth gap compared with every other query in the same file which explicitly adds `PharmacySale.tenant_id == current_user.tenant_id`.
  - `customer_name` was mapped from `s.notes or '-'` instead of `s.customer_name or '-'`, causing the API to return prescription notes as the customer's name.

---

## 2. Fixes Applied

### Fix 1 — InventoryLedgerService aligned to canonical writer
- **File:** `services/inventory_ledger_service.py`
- **Change:** `record_movement()` now delegates to `PharmacyStockService.adjust_stock` (the single working stock writer in `app/modules/workflows/pharmacy.py`). It computes the signed quantity (`+` for `purchase`/`return`/`adjustment`, `-` for `dispense`/`sale`/`transfer`/`waste`), resolves `performed_by` from `g.current_user`, and passes it to `adjust_stock` which correctly sets `before_quantity`/`after_quantity` and writes a valid `StockMovement` row.
- **Removed:** `unit_cost` parameter (column does not exist). `safe_commit` import removed because `adjust_stock` queues objects for the caller's transaction.
- **Change:** `current_stock()` now sums signed quantities directly (`sum(m.quantity for m in movements)`), consistent with the signed-quantity convention used by `adjust_stock`. Previously it double-interpreted direction by branching on `movement_type`.

### Fix 2 — All three sale paths now use atomic locking + ledger
- **File:** `routes/medication_routes/pos.py` lines 124-144
  - Added `.with_for_update()` to the medication SELECT.
  - Replaced manual `med.stock_quantity -= qty` with `PharmacyStockService.adjust_stock(..., movement_type='sale', reference_type='PharmacySale', reference_id=sale.id, performed_by=current_user.id)`.
  - Catches `ValueError` from `adjust_stock` (insufficient stock) and returns the original Arabic error message.
- **File:** `routes/medication_routes/prescriptions.py` lines 134-148
  - Same pattern: `.with_for_update()` + `adjust_stock` with `reference_type='PrescriptionItem'`.
- **File:** `services/pharmacy_sale_service.py` lines 38-61
  - Same pattern: `.with_for_update()` + `adjust_stock` with `reference_type='PharmacySale'`.
  - Stock check is now enforced; previously `create_sale` silently allowed overselling.

### Fix 3 — api_sales_list defense-in-depth + display fix
- **File:** `routes/medication_routes/pos.py` lines 241-251
  - Added explicit `PharmacySale.tenant_id == current_user.tenant_id` to the base query.
  - Fixed `customer_name: s.customer_name or '-'`.

---

## 3. Test Verification

| Test File | Result | Count |
|-----------|--------|-------|
| `tests/test_pharmacy.py` | **PASS** | 19/19 |
| `tests/test_phase35_pos.py` | **PASS** | 12/12 |
| `tests/test_pharmacy_billing_workflows.py` | **PASS** | 13/13 |
| `tests/unit/test_sale_service_chunk3.py` | **PASS** | 13/13 |
| `tests/test_module_require_service.py` (sampled gate+enabled) | **PASS** | 2/2 sampled |

**Total targeted tests:** 59/59 passed.

**Test adjustment note:** `tests/unit/test_sale_service_chunk3.py` required a new `_make_user()` helper because `performed_by` is now a real FK into `users`. The previous hard-coded `dispensed_by=1` triggered a `ForeignKeyViolation` once the ledger started actually writing rows. This confirms the fix is working end-to-end.

---

## 4. Remaining Risk / Follow-up Items

- **Medium (defense-in-depth):** `appointment_routes.py:88-90`, `prescriptions.py:114-126` (timer expiry), and `lab_routes.py` update statements still use Core `update()` without explicit `tenant_id` in the WHERE clause. They are mitigated by PostgreSQL `FORCE ROW LEVEL SECURITY` policies (`s2_008_comprehensive_rls_force.py`), but will silently no-op if RLS is disabled or on non-Postgres.
- **Medium:** `dispense_prescription` early stock check (line 125) still runs without a lock; the authoritative guard is now the `adjust_stock` call inside the locked loop. Race condition window narrowed but not fully closed for the friendly error message.
- **Low:** `StockMovementType` enum (`app/shared/enums.py`) does not contain `dispense`, `waste`, or plain `transfer` — only `transfer_in`/`transfer_out`. `adjust_stock` accepts raw strings, so this is not a functional bug, but the enum and the `MOVEMENT_TYPES` tuple should be reconciled in a future schema cleanup.

---

## 5. Files Modified

```
routes/medication_routes/pos.py           | 25 +++++++++++-----
routes/medication_routes/prescriptions.py | 18 +++++++++---
services/inventory_ledger_service.py       | 48 ++++++++++++++++------------
services/pharmacy_sale_service.py         | 17 +++++++++--
tests/unit/test_sale_service_chunk3.py   | 40 ++++++++++++++++-------
```
