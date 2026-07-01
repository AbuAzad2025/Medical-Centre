# Medical Centre — Remediation Plan

**Plan status:** `Draft — Audit and Decision Phase`  
**Implementation status:** `No implementation approved`  
**Canonical source file path:** `docs/MEDICAL_CENTRE_REMEDIATION_PLAN_2026-07-01.md`  
**Date created / updated:** 2026-07-01  
**Last updated:** 2026-07-02 (Update 9 — MC-014 evidence pass corrections: WP-3 partial-payment queue entry reclassified as direct workflow contradiction; WP-2 custom-service immediate global activation reclassified as direct workflow contradiction; WP-4/5 canonical financial service-line structure determined; five ordered work packages with implementation-readiness matrix; minimum structural gaps recorded)  
**Reference audit report:** `docs/AUDIT_REPORT_2026-07-01.md`  
**Rule:** Only explicitly approved items may move into implementation.  
**Last updated by:** OpenCode agent — read-only audit phase.  

---

## A. Scope and Non-Negotiable Business Rules

| # | Rule | Status | Basis |
|---|------|--------|-------|
| A-01 | Reception creates and assigns visits. | **Technically verified in current code** | `routes/reception/visits.py::create_visit()`, `routes/reception/visits.py::transfer_visit()` |
| A-02 | Only the appropriate doctor, department, or medical unit may work on an assigned item. | **Requires technical verification** | Doctor routes enforce `doctor_id`; department/unit enforcement is partial or missing for lab/radiology/emergency |
| A-03 | After treatment completion, the visit must not be automatically archived. | **Technically verified in current code** | `VisitStateMachineService` transitions to `COMPLETED`; `archive_status` remains `ACTIVE` until `GatekeeperService.archive_visit()` |
| A-04 | Reception controls the next administrative decision: reassignment, return to treatment, archive, or billing workflow. | **Product requirement confirmed by owner** | `transfer_visit` allows reassignment; `GatekeeperService.archive_visit()` validates financial completion; billing routes exist but visit-ownership checks are partial |
| A-05 | Emergency treatment must not be blocked by mandatory payment. | **Technically verified in current code** | Emergency routes create visits with `is_emergency=True`, `is_force_payment=True`; no payment gate before treatment |
| A-06 | Services may be added during a visit, but must be financially settled before final closure or archive. | **Product requirement confirmed by owner — administration maintains all approved chargeable service catalogs and configured prices; each doctor, department, and unit has a configured service list that reception sees dynamically after selecting that doctor, department, or unit; reception alone selects requested services, adds approved catalog services or controlled custom service entries to the visit, and controls all financial entries; a normal visit cannot enter any queue until its initial reception-selected fees are paid and backend-validated; emergency treatment is not blocked by payment; reception may add catalog services or custom services before final settlement or archive without reopening the clinical visit or queue; all reception-recorded chargeable services must be financially resolved before final settlement or archive; prescriptions and medications are excluded** | `create_visit()` accepts `selected_tests` and records initial costs from catalog; `_process_custom_services` creates custom `ServiceMaster` entries with reception-entered name and price; doctor routes add lab/radiology requests mid-visit (only while `IN_PROGRESS`) as clinical records only; prescriptions are clinical documents only and do not create charges; `GatekeeperService.can_archive_visit()` checks `gl_posted_at`, `financial_locked`, and emergency completion flags; post-queue service charging behavior requires technical verification |
| A-07 | Tenant data, roles, department/unit authority, and package entitlements must be enforced separately. | **Product requirement confirmed by owner** | Role hierarchy exists (`ROLE_HIERARCHY`); tenant isolation exists (ORM hooks + PostgreSQL RLS with **199 table references declared across five additive RLS migrations; exact unique-table manifest and runtime enforcement still require verification**); department/unit isolation is partial; package entitlements are partially enforced (`guard_module` on 8 blueprints only) |
| A-08 | UI hiding alone is never an authorization control. | **Product requirement confirmed by owner** (inherited from SaaS architecture) | `guard_module` and `require_module` exist for backend blocking, but many route files lack them |

**RLS evidence source:**  
- `s1_002_tenant_rls_policies` — 11 table references  
- `s1_004_expenses_rls_uniques` — 20 table references  
- `s1_005_rls_phase2` — 30 table references  
- `s1_006_rls_phase3` — 68 table references  
- `s1_007_rls_phase4` — 70 table references  
- **Total: 199 table references declared** (additive lists; overlap not yet verified)

**RLS runtime verification task (must complete before any ticket claims RLS as a safety net):**
1. Produce the exact unique table manifest with no duplicate count.
2. Confirm which migrations are applied in the real target database.
3. Confirm RLS is enabled on each relevant table at runtime (`\d+ tablename` in psql).
4. Identify the exact application database role and all inherited role memberships.
5. Check whether the application role has `BYPASSRLS`.
6. Check table ownership for every protected table.
7. Check `relrowsecurity` and `relforcerowsecurity` for each relevant table.
8. Run `row_security_active(...)` under the actual application database role.
9. Execute isolated two-tenant read, insert, update, and delete tests using the same application role and the same tenant-context mechanism used by production.
10. Verify the RLS policy `USING` and `WITH CHECK` behavior for reads and writes.
11. Record the exact migration state and active policy definitions.

Do not treat migration text alone as proof of effective runtime isolation.

---

## B. Evidence and Findings Register

**Register contains 17 items (B-001 through B-017).**
- B-007: Resolved
- B-009: Resolved
- B-013: Rejected (disproven)
- **Active findings: 14**
  - 12 Candidate
  - 1 Verified fail-open code path
  - 1 Awaiting product decision

| ID | Area | Finding | Evidence Status | Evidence Source | Current Risk | Decision Needed | Existing PLAN Mapping | Proposed Next Step | Status |
| -- | ---- | ------- | --------------- | --------------- | ------------ | --------------- | --------------------- | ------------------ | ------ |
| B-001 | Visit creation | `Visit` constructor in `create_visit()` does not set `tenant_id` explicitly; relies on `before_flush` auto-assign hook | **Confirmed unsafe coding pattern; exploit impact still requires isolated verification** | `routes/reception/visits.py` lines 451-466; `app/shared/tenant_filter.py` lines 146-166 | If `g.tenant_id` is None and bypass flag is active, visit gets `tenant_id=NULL` | None — hardening required | Phase 0 extension (tenant_job_runner area) | Add explicit `tenant_id` from validated context to constructor | Candidate |
| B-002 | Visit access — reception | `archive_visit` and `end_visit` use `db.session.get(Visit, id)` which bypasses `before_compile` tenant filter | **Confirmed unsafe coding pattern; exploit impact still requires isolated verification** | `routes/reception/visits.py` lines 93, 116; `app/shared/tenant_filter.py` lines 99-139 | Any user with `reception` or `super_admin` role could access any visit by ID across tenants if `g.tenant_id` is somehow bypassed | None — hardening required | Phase 1 extension (RLS hardening) | Replace with `get_tenant_record(Visit, id)` or explicit tenant-filtered query | Candidate |
| B-003 | Visit access — emergency | Emergency routes use `Visit.query.filter_by(id=visit_id).first()` without explicit tenant filter | **Technical hardening candidate; isolated runtime verification pending** | Original claim that `Visit.query.filter_by(...)` is completely tenant-unscoped is **corrected/disproven** when a valid tenant context exists; `before_compile` DOES inject `tenant_id` when `g.tenant_id` is set. Remaining concern is only implicit-hook dependence and defense-in-depth. | Risk lowered to "single point of failure" rather than "completely unscoped". Not classified as a confirmed cross-tenant vulnerability unless a two-tenant runtime test proves it. | None — still needs defense-in-depth | Phase 1 extension | Add explicit `tenant_id` filter as defense-in-depth; add department-level check if required | Candidate |
| B-004 | Visit access — billing | `payment_routes.py` and `finance.py` pass `visit_id` directly to services without route-level ownership validation | **Confirmed unsafe coding pattern; exploit impact still requires isolated verification** | `routes/payment_routes.py`, `routes/finance.py` | Any `accountant`-role user could process any visit by ID if service-level validation is bypassed or inconsistent | None — hardening required | Phase 3 extension (financial service coverage) | Add `get_tenant_record(Visit, id)` in route before service call | Candidate |
| B-005 | Module gating | `guard_module()` returns silently when `g.current_tenant` is None instead of aborting 403 | **Verified fail-open code path; runtime reachability and exposure impact pending** | `services/feature_gate_service.py` lines 68-70 | If tenant context is missing (e.g., internal redirect, bypass path), protected module becomes accessible | None — bug fix | Phase 2 extension (feature gate service) | Change `return` to `abort(403)` on missing tenant | Verified |
| B-006 | User-to-tenant binding | No explicit validation that `current_user.tenant_id == g.tenant_id` anywhere in codebase | **Suspected / requires clarification** | Entire codebase — zero matches for `current_user.tenant_id == g.tenant_id`; session precedence in middleware mitigates but is not cryptographically validated | Session manipulation or slug hopping theoretically possible; exploitability depends on session secret strength (not audited) | **Product requirement confirmed by owner:** mismatch must fail closed with 403 for ordinary users; platform users must use explicit audited tenant-assumption workflow | Phase 1 extension (middleware hardening) | Add explicit mismatch check with exempt paths for platform admin | Candidate |
| B-007 | SystemConfig ownership | `SystemConfig` is in `_skip_table` (explicitly global) but inherits `TenantMixin` with `tenant_id` column and `config_key` is globally unique | **Product requirement confirmed by owner:** `SystemConfig` remains platform-global for this remediation scope | `app/shared/tenant_filter.py` lines 60-67; `models/system_config.py` line 17 | Two tenants cannot have the same config key; whether configs should be per-tenant or global is a product decision | **Resolved:** keep global; inventory all consumers to verify no tenant-specific settings are being stored | Phase 2 extension (feature flags / capabilities) | Verify no tenant-specific data is stored; if found, record as separate future design issue | Resolved |
| B-008 | Module gating — loose routes | Loose route files (`patient_portal.py`, `ai_imaging_routes.py`, `telemedicine_routes.py`, `fhir_routes.py`, `biometric_routes.py`, `bed_management_routes.py`) lack `guard_module` | **Confirmed by code; isolated runtime verification pending** | Grep of `routes/*.py` — only package `__init__.py` files register `guard_module`; loose files do not | Patient-data routes (portal, AI imaging, telemedicine, FHIR) expose clinical data without module entitlement check | None — hardening required | Phase 2 extension (platform capabilities) | Per-endpoint classification before module enforcement (see MC-006) | Candidate |
| B-009 | Package/entitlement source of truth | Dual system: legacy `SubscriptionPlan.modules_included` (JSON) + modern `PackageVersion` → `SubscriptionLine` → `TenantEntitlement` | **Product requirement confirmed by owner:** modern package/subscription/entitlement is contractual source of truth; `TenantModule` is runtime projection; legacy is compatibility-only | `app/core/tenant/models.py` lines 123-141; `app/core/saas/models.py` lines 71-593 | Two sources of truth can drift; `TenantModule` rows (used by `guard_module`) are not auto-synced with subscription changes | **Resolved:** modern structure is authoritative; legacy JSON must not become competing runtime authority | Phase 2 extension (SaaS entitlements) | Define sync trigger on subscription change; document authoritative resolver order | Resolved |
| B-010 | Super admin tenant scope | `_is_admin_user()` checks `current_user.role == "super_admin"` and bypasses all module guards unconditionally | **Confirmed by code; isolated runtime verification pending** | `services/feature_gate_service.py` lines 12, 48, 66 | Super admin on a regular tenant path (e.g., `/doctor/patient-queue`) is exempt from all module and tenant checks | **Product requirement confirmed by owner:** no blanket role-name exemption on normal tenant routes; cross-tenant access must use explicit audited tenant-assumption workflow | Phase 1 extension (access control) | Constrain super admin module bypass to platform paths only; add audit logging for cross-tenant access | Candidate |
| B-011 | Lab/radiology unit authorization | Lab and radiology routes check `LabRequest.tenant_id` / `RadiologyRequest.tenant_id` but not performing-unit or request-level assignment | **Confirmed unsafe coding pattern; exploit impact still requires isolated verification** | `routes/lab/worklist.py`, `routes/radiology/worklist.py` | Lab tech in Unit A can access lab requests for Unit B within same tenant if IDs are known | **Product requirement confirmed by owner:** restricted to own performing unit or explicitly assigned request; do not use `Visit.department_id` as universal rule | Phase 1 extension (department-level checks) | Discovery-first: inventory all existing fields and relationships; define authorization rule using existing data if possible; only if no existing safe boundary exists, record as separate future design decision | Candidate |
| B-012 | Return-to-treatment functional gap | After `COMPLETED`, a visit reassigned to Doctor B does **not** appear in Doctor B's active queue because the queue filter excludes `COMPLETED` | **Confirmed by code; isolated runtime verification pending** | `routes/doctor/queue.py:46` (filters by `OPEN, IN_PROGRESS`); `QueueManagementService.transfer_visit()` supports reassignment but does not reset visit status | Doctor B cannot receive or work on the reassigned visit; workflow is not fully implemented | **Product requirement confirmed by owner:** only an explicit reception-authorized "return to treatment" action may trigger `COMPLETED → OPEN`; recreate/reopen queue ticket as `waiting`; preserve history | No PLAN mapping needed (functional fix) | First determine whether existing route/service has explicit action/intent parameter for "return to treatment"; if not, record as design gap | Candidate |
| B-013 | Doctor financial fields | Original audit claimed doctors can set financial fields; corrected: doctor routes do not write `total_amount`, `payment_method`, `paid_amount` | **Corrected / disproven** | `routes/doctor/visits.py::end_treatment()` — no financial field writes; `routes/doctor/dashboard.py:174` reads `total_amount` only | No risk — original claim was incorrect | None | N/A | N/A — no action needed | Rejected |
| B-014 | Background job tenant context | Celery tasks and system tasks may run without explicit `g.tenant_id` binding | **Confirmed unsafe coding pattern; exploit impact still requires isolated verification** | `celery_app.py`, `tasks/system_tasks.py`, `services/backup_automation_service.py` | Background jobs that query tenant-scoped models without `with_tenant_context` wrapper may run unscoped | **Technical verification required:** complete inventory of all background tasks, entry points, wrappers, and runtime risk | Phase 0 extension (Celery tenant isolation) | Audit all `@celery.task` definitions; wrap with `with_tenant_context` where missing | Candidate |
| B-015 | Visit notification on completion | Doctor `end_treatment` sends notification to reception: "visit completed — please finalize" | **Confirmed by code; isolated runtime verification pending** | `routes/doctor/visits.py:481-490` | Notification path exists; but notification service itself may not validate tenant context in background delivery | None — verify as part of B-014 | Phase 0 extension | Verify `NotificationService.send_notification` preserves tenant context in background delivery | Candidate |
| B-016 | Reception completed-visit dashboard (UX enhancement) | Reception can see all visits, but there is no dedicated filter or dashboard for "completed, awaiting action" visits | **Confirmed by code; isolated runtime verification pending** | `routes/reception/visits.py:37` (shows all statuses); no dedicated `COMPLETED + archive_status=ACTIVE` filter | Reception workflow efficiency gap; not a security risk | **Optional product decision:** Is a dedicated "completed awaiting closure" dashboard required, or is the existing visits list + status filter sufficient? | No PLAN mapping needed (UX enhancement) | Add query filter helper for `status=COMPLETED, archive_status=ACTIVE` if product requests | Awaiting product decision |
| B-017 | Administration catalog, reception service selection, and financial reconciliation | **Confirmed owner requirement:** administration maintains all approved chargeable service catalogs and configured prices. Each doctor, department, and unit has a configured service list that reception sees dynamically after selecting that doctor, department, or unit. Reception alone selects requested services, adds approved catalog services or controlled custom service entries to the visit, and controls all financial entries. A normal visit cannot enter any queue until its initial reception-selected fees are paid and backend-validated. Emergency treatment is not blocked by payment. Reception may add catalog services or custom services before final settlement or archive without reopening the clinical visit or queue. All reception-recorded chargeable services must be financially resolved before final settlement or archive. Prescriptions and medications are excluded. **Custom service entry is an approved reception-controlled exception for services not yet configured in the administration catalog. Reception may enter the service name and price for the current visit. A manager must later review and approve the service before it becomes a fixed reusable catalog item. This workflow must remain auditable and must not grant doctors or clinical departments authority to enter financial prices or costs.** | **Confirmed by code; isolated runtime verification pending** | `routes/reception/visits.py` (visit creation with `selected_tests`, `_process_custom_services` — line 208); `routes/doctor/lab.py:33-65`, `routes/doctor/radiology.py:33-65` (clinical service reporting mid-visit); `services/gatekeeper_service.py:91-118` (archive financial checks); `routes/reception/payments.py:51-111`, `routes/payment_routes.py:80-371` (payment processing); `routes/manager/pricing.py` (manager catalog CRUD) | Post-queue clinical service additions (lab, radiology) are not automatically charged; financial totals may become decoupled from rendered services if reception does not manually record post-creation charges; archive eligibility may approve a visit with unrecorded post-creation services; normal queue-entry payment condition enforcement requires technical verification; emergency final-reconciliation exception requires technical verification; custom service entry creates `ServiceMaster` record immediately with `is_active=True` and no structural distinction from catalog services | None — owner requirement confirmed; remaining technical audit needed | Phase 3 extension (financial service coverage) | Identify the existing administration-managed service catalog, pricing tables, doctor-specific service mappings, department/unit service mappings, and active/inactive controls; trace the reception screen and backend path that dynamically loads services after selecting a doctor, department, or unit; verify that reception can select only approved applicable services and cannot manually alter configured prices; verify the exact backend rule that prevents any normal visit from entering any queue until initial selected fees are paid; verify every queue-entry route, including doctor, laboratory, radiology, and other department queues; verify that emergency queue entry bypasses initial payment without bypassing later financial reconciliation; verify reception can add catalog services or custom services to an active completed-but-unarchived visit without changing clinical status or queue state; verify no department or doctor route can create or edit financial service entries, prices, costs, invoice items, payments, receipts, locks, or accounting values; identify the existing authoritative financial records for selected services, payment validation, final settlement, and archive eligibility; verify final settlement/archive blocks whenever any reception-recorded catalog service remains unresolved; verify final settlement/archive prevents subsequent service or cost additions unless a separately approved correction/reversal workflow exists | Candidate |

**Evidence label rules applied:**
- `Confirmed by code and isolated runtime evidence` → changed to `Confirmed by code; isolated runtime verification pending` for B-005, B-008, B-010, B-012, B-015, B-016, B-017.
- For any future claim of runtime verification, the plan must record: test name or reproducible command; environment or test database used; preconditions; expected outcome; actual outcome; whether it proves disclosure, mutation, authorization denial, or only code-path behavior.

**B-005 mandatory reachability test before P0 exposure classification:**
- SaaS mode enabled.
- Protected module route.
- Missing `g.current_tenant`.
- Full real middleware chain active.
- Expected result before fix and after fix.
- Confirm whether the route is reachable or already blocked earlier.

---

## C. Visit Lifecycle and Authority Matrix

**Post-treatment authority — Product requirement confirmed by owner:**

After treatment completion, reception is the **normal operational authority** for:
- Returning a visit to treatment.
- Reassigning a visit.
- Initiating the billing handoff.
- Archiving a visit after all financial and closure requirements are satisfied.

Doctors, departments, and units **must not** archive a visit or initiate billing.

Accountants may process payments and post accounting entries, but they do **not** replace reception as the visit workflow owner.

Managers **must not** silently inherit reception archive or billing authority through role hierarchy.

Platform super-admin access is a **separate audited platform function**, not ordinary reception authority.

| Action | Reception | Doctor | Department / Unit User | Accountant | Manager | Platform Super Admin | Current Code Evidence | Required Decision or Gap |
| ------ | --------- | ------ | ---------------------- | ---------- | ------- | -------------------- | --------------------- | ------------------------ |
| **Create visit** | ✅ Allowed (`reception` role) | ❌ Not allowed (`can_create_visits` restricts to `reception`) | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed (hierarchy does not inherit `reception` creation) | ⚠️ Allowed by role hierarchy? Unclear — `can_create_visits` checks exact role `reception` | `routes/reception/visits.py::create_visit()`; `utils/decorators.py::can_create_visits()` checks `current_user.role == 'reception'` | Is `super_admin` intended to create visits? If not, add explicit block. **Default deny until explicitly approved.** |
| **Select chargeable services from approved catalog** | ✅ Allowed (reception selects from dynamic doctor/department/unit service list) | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ⚠️ Allowed? | `routes/reception/visits.py::create_visit()` with `selected_tests`; administration-managed catalog | Reception alone may select services; no department or doctor may create or edit financial service entries or prices. **Default deny until explicitly approved.** |
| **Enter queue — normal visit** | ✅ Allowed (reception adds to queue after initial fees are paid and backend-validated) | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ⚠️ Allowed? | `routes/reception/queue.py::add_patient_to_queue()`; `routes/reception/visits.py` payment validation | Backend must enforce: no queue entry for normal visits until initial reception-selected fees are paid. **Default deny until explicitly approved.** |
| **Enter queue — emergency** | ✅ Allowed (reception creates emergency visit) | ❌ Not allowed | ✅ Allowed (emergency staff can triage and enter emergency workflow) | ❌ Not allowed | ❌ Not allowed | ⚠️ Allowed? | `routes/emergency/` — no payment gate before triage/treatment | Emergency treatment must not be blocked by payment. **Default deny until explicitly approved.** |
| **Assign doctor or department** | ✅ Allowed (`transfer_visit` with `reception` role) | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ⚠️ Allowed by role? `transfer_visit` checks `reception` or `super_admin` | `routes/reception/visits.py::transfer_visit()` | Is `super_admin` intended to transfer visits? **Default deny until explicitly approved.** |
| **View active visit** | ✅ Allowed (all visits in tenant) | ✅ Allowed (own assigned visits only) | ⚠️ Partial (lab/radiology see requests but not visit-level doctor filter) | ❌ Not allowed (no visit view route) | ⚠️ Allowed (inherits via hierarchy?) | ⚠️ Allowed (no assignment filter) | Doctor: `Visit.doctor_id == current_user.id`; Reception: no doctor filter; Lab/Radiology: request-level | Should managers see all visits or only visits within an approved management scope? **Default deny until explicitly approved.** |
| **Start treatment** | ❌ Not allowed | ✅ Allowed (on own assigned visit with `IN_PROGRESS` queue ticket) | ⚠️ Emergency staff can start emergency visits | ❌ Not allowed | ❌ Not allowed | ⚠️ Allowed? No role filter beyond `doctor`/`emergency` | `routes/doctor/queue.py` — validates queue ticket `called` status | Should emergency staff work on all emergency cases in the tenant, or only assigned emergency unit cases? **Default deny until explicitly approved.** |
| **Complete treatment** | ❌ Not allowed | ✅ Allowed (`end_treatment` on own visit with `IN_PROGRESS` status) | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ⚠️ Allowed? `end_treatment` checks `doctor_id` match | `routes/doctor/visits.py::end_treatment()` | Can manager or super_admin force-complete a visit? **Default deny until explicitly approved.** |
| **Return completed visit to active treatment** | ✅ Allowed (via explicit "return to treatment" action; status `COMPLETED` → `OPEN`; recreate queue ticket as `waiting`) | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ⚠️ Allowed? | `QueueManagementService.transfer_visit()` | Must verify financial/archive eligibility before return. **Default deny until explicitly approved.** |
| **Reassign visit** | ✅ Allowed (`transfer_visit`) | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ⚠️ Allowed? | Same as assign | Should reassignment require queue ticket reset? **Confirmed:** yes, for completed visits via explicit return-to-treatment. |
| **Archive visit** | ✅ Allowed (`archive_visit` with `reception` role — **confirmed as normal operational authority**) | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed (must not silently inherit) | ⚠️ Allowed? Route allows `super_admin` but decorator only allows `reception` | Inconsistent: `can_archive_visits` decorator allows `reception`, `manager`; route allows `reception`, `super_admin` | Resolve inconsistency: `reception` only as normal authority; `super_admin` as separate audited platform function. **Default deny until explicitly approved.** |
| **Add approved catalog service to active or completed visit** | ✅ Allowed (reception selects from approved catalog; does not reopen clinical visit or queue) | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ⚠️ Allowed? | `routes/reception/visits.py` (visit editing); administration-managed catalog | Reception alone may add catalog services before final settlement or archive without changing `COMPLETED` status or queue state. **Default deny until explicitly approved.** |
| **Start billing workflow** | ✅ Allowed (`send-to-accounting` route exists for reception — **confirmed as reception authority**) | ❌ Not allowed | ❌ Not allowed | ⚠️ Partial (can process but not initiate) | ❌ Not allowed | ⚠️ Allowed? | `routes/reception/payments.py`, `routes/finance.py` | Reception initiates; accountant executes. |
| **Process payment** | ⚠️ Partial (`process_payment` with reception/accountant role) | ❌ Not allowed | ❌ Not allowed | ✅ Allowed | ❌ Not allowed | ⚠️ Allowed? | `routes/payment_routes.py::process_payment()` | May reception process a payment directly, or only initiate a billing handoff to accounting? **Default deny until explicitly approved.** |
| **Post accounting entry (GL)** | ❌ Not allowed | ❌ Not allowed | ❌ Not allowed | ✅ Allowed (`accountant` role) | ❌ Not allowed | ⚠️ Allowed? | `routes/finance.py::post_gl()` | Who can post GL? Accountant only? **Default deny until explicitly approved.** |
| **View historical visit** | ✅ Allowed (all archived visits) | ⚠️ Partial (own completed visits may be visible if not filtered out) | ⚠️ Partial | ⚠️ Partial (no dedicated view route) | ✅ Allowed | ✅ Allowed | No explicit historical view route; doctor queue filters out `COMPLETED` | Should doctors have read-only access to their completed historical visits for continuity of care? **Default deny until explicitly approved.** |

**Important notes:**
- `ROLE_HIERARCHY` in `utils/decorators.py` defines inheritance: `super_admin` → `admin` → `manager` → `reception`, `accountant`. This means `super_admin` technically inherits `reception` authority through the hierarchy. The audit has not verified whether all route-level manual checks respect this hierarchy.
- `can_archive_visits` decorator allows `reception` and `manager`, but `archive_visit` route manually allows `reception` and `super_admin`. This is an **inconsistency** requiring resolution. **Owner decision:** reception is normal operational authority; manager and super_admin must not silently inherit it.
- **Default deny until explicitly approved** applies to all authority questions not yet decided by the owner.

---

## D. Return-to-Reception and Return-to-Treatment Trace

### Step-by-step trace from current code

| Step | Actor | Action | Code Evidence | Result | Tenant/Assignment/History Evidence |
|------|-------|--------|---------------|--------|-----------------------------------|
| 1 | Administration | Predefine approved service catalog and prices | Administration-managed catalog (e.g., `ServiceCatalog`, `DoctorPricing`) | Each doctor, department, and unit has a configured service list with approved prices | Catalog is authoritative; no user may invent or edit prices during visit workflow |
| 2 | Reception | Create visit and select services from approved catalog | `routes/reception/visits.py::create_visit()` — `selected_tests` from dynamic service list | `Visit` created with `status=OPEN`, `doctor_id=A`, `department_id=X`; initial chargeable services recorded from catalog | `VisitTransferLog` NOT created on initial creation (only on transfer) |
| 3 | Reception | Validate initial payment for normal visit | `routes/reception/visits.py` payment validation; `routes/reception/payments.py` | Normal visit: initial reception-selected fees must be paid and backend-validated before queue entry. Emergency visit: payment not required before queue entry. | Backend enforcement required; not UI-only |
| 4 | Reception | Add patient to queue for Department X | `routes/reception/queue.py::add_patient_to_queue()` | `QueueManagement` ticket created with `status=waiting`, `doctor_id=A`, `department_id=X` | Queue ticket links to visit |
| 5 | Reception / System | Call patient | `routes/reception/queue.py::call_next_patient()` or `routes/doctor/queue.py::call_patient()` | Queue ticket `status=called` | Queue state transition |
| 6 | Doctor A | Start treatment | `routes/doctor/queue.py::start_treatment()` | `Visit.status=IN_PROGRESS`, queue ticket `status=in_progress` | `VisitWorkflowEvent` records `OPEN → IN_PROGRESS` |
| 7 | Doctor A / Department | Add or report additional clinical services during treatment | `routes/doctor/lab.py:33-65`, `routes/doctor/radiology.py:33-65` | Clinical records created (lab requests, radiology requests); **no automatic financial charge** | Department records clinical services only; reception must add corresponding catalog charge |
| 8 | Doctor A | Complete treatment | `routes/doctor/visits.py::end_treatment()` | `Visit.status=COMPLETED`, `completed_by=A`, `completed_at=now()`, `archive_status=ACTIVE` | `VisitWorkflowEvent` records `IN_PROGRESS → COMPLETED`; `MedicalRecord` created; **notification sent to reception** |
| 9 | System | Doctor queue refresh | `routes/doctor/queue.py::patient_queue()` | Visit **disappears** from doctor queue because query filters `status.in_([OPEN, IN_PROGRESS])` | Doctor no longer sees visit |
| 10 | Reception | View visit list | `routes/reception/visits.py::visits()` | Visit **visible** in reception list (no status filter applied by default) | Reception can filter by status if needed |
| 11 | Reception | Add approved catalog service after treatment completion | Reception selects from approved catalog via existing visit edit route | Charge added to visit financial record; `COMPLETED` status and queue state **unchanged** | Reception alone may add catalog services without reopening clinical visit or queue |
| 12 | Reception | Reassign to Doctor B (return to treatment) | `routes/reception/visits.py::transfer_visit()` with explicit "return to treatment" intent | `Visit.status=COMPLETED → OPEN` via state machine; queue ticket recreated as `waiting` for Doctor B | `VisitTransferLog` created; `VisitWorkflowEvent` records state transition |
| 13 | Doctor B | View patient queue | `routes/doctor/queue.py::patient_queue()` | Visit **appears** in Doctor B queue because `status=OPEN` and queue ticket is `waiting` | Doctor B can receive and work on the visit |

### Gaps identified in trace

| Gap ID | Description | Severity | Decision Needed |
|--------|-------------|----------|---------------|
| D-GAP-01 | Backend enforcement of normal queue-entry payment condition requires verification | **P1** | Does backend code enforce that normal visits cannot enter any queue until initial reception-selected fees are paid? Or is this UI-only behavior? |
| D-GAP-02 | Doctor B cannot see reassigned completed visit because queue filters by `OPEN, IN_PROGRESS` | **P1** | **Resolved by owner decision:** only an explicit reception-authorized "return to treatment" action may trigger `COMPLETED → OPEN` and recreate/reopen queue ticket as `waiting`. Do NOT set to `IN_PROGRESS` until Doctor B actually starts treatment. |
| D-GAP-03 | `VisitTransferLog` is not created on initial visit creation (only on transfer) | **P2** | Should initial creation be logged as "created by reception, assigned to Doctor A"? |
| D-GAP-04 | No explicit "return to reception" state or queue bucket exists | **P2** | Is the existing `COMPLETED` + reception visibility sufficient, or is a dedicated "awaiting reception action" queue needed? **Owner decision:** existing reception list is sufficient; optional dedicated filter is UX enhancement (B-016). |
| D-GAP-05 | Queue ticket state after transfer is uncertain | **P2** | `transfer_visit` only updates queue ticket if `status==waiting`. If ticket was `completed`, what happens? |
| D-GAP-06 | Post-completion catalog service addition by reception requires verification | **P2** | Can reception add approved catalog services to a `COMPLETED` visit without changing clinical status or queue state? Is this supported by existing code or a gap? |

### Conclusion from trace

**The return-to-reception workflow is structurally supported by existing code (`COMPLETED` status + `transfer_visit`). The return-to-treatment path (reassigning a completed visit to a new doctor) has a functional gap: the new doctor cannot see the visit in their active queue because the queue query filters out `COMPLETED` visits.**

**Do not describe the return-to-treatment workflow as implemented until the reassigned doctor can actually receive and work on the visit.**

**The financial workflow requires these verified behaviors:**
1. Administration preconfigures the approved service catalog and prices.
2. Reception selects patient-requested chargeable services from the dynamic approved catalog at visit entry.
3. Normal visits cannot enter any queue until initial reception-selected fees are paid and backend-validated.
4. Emergency treatment is not blocked by payment.
5. Departments may add or report clinical services during or after treatment, but reception alone controls all costs using the approved catalog.
6. Reception may add approved catalog services before final settlement or archive without reopening the clinical visit or queue.
7. All reception-recorded chargeable services must be financially resolved before final settlement or archive.
8. Prescriptions and medications are excluded from this workflow.

**Target acceptance behavior (confirmed by owner):**
- When reception intentionally returns a completed visit to treatment or reassigns it to another doctor:
  - Do **not** add a new Enum or state unless later evidence proves it is necessary.
  - Only an explicit reception-authorized **"return to treatment"** action may trigger the transition from `COMPLETED` back to the existing actionable state `OPEN`.
  - Do **not** make every transfer of a `COMPLETED` visit automatically reset to `OPEN`. The system must distinguish between: clinical return to treatment, administrative reassignment, transfer to laboratory or radiology, and billing or closure workflow.
  - Do **not** set it directly to `IN_PROGRESS`; that state must begin only when the newly assigned doctor actually starts treatment.
  - The related queue ticket must be recreated or reopened as `waiting`, assigned to the intended doctor/unit, and become visible in that actor's active queue.
  - Preserve prior clinical history.
  - Create the appropriate existing `VisitWorkflowEvent` and `VisitTransferLog` entry.
  - The implementation must **fail safely** if the current state machine does not allow the required transition; do not bypass the state machine.

No new Model, Enum, or state is approved or proposed at this stage. This remains subject to verification of the QueueManagement data model, state-machine transition contract, existing route/service intent model, and financial closure rules.

---

## E. Tenant, Module, and Entitlement Source-of-Truth Matrix

| Capability Question | Current Source of Truth | Synchronization Method | Current Failure Risk | Decision Required | Planned Resolution |
| ------------------- | ----------------------- | ---------------------- | -------------------- | ----------------- | ------------------ |
| **Tenant identity for current request** | `g.tenant_id` resolved from session first, then URL slug, then subdomain, then user fallback | `set_tenant_context()` in `app/core/tenant/middleware.py` | Session precedence usually prevents hopping, but no explicit `current_user.tenant_id == g.tenant_id` validation | **Product requirement confirmed by owner:** mismatch must fail closed with 403 for ordinary users; no fallback such as `current_user.tenant_id or g.tenant_id` | Candidate: Add middleware check after `set_tenant_context()` (MC-005) |
| **User-to-tenant relationship** | `User.tenant_id` column (nullable) | Set at user creation/login | Platform users (`super_admin`, `owner`) may have `tenant_id=NULL` | **Product requirement confirmed by owner:** platform users must not silently bypass tenant or module controls on ordinary tenant paths; cross-tenant access must use explicit audited tenant-assumption workflow | Awaiting explicit tenant-assumption workflow design and approval |
| **Package owned by tenant** | `Tenant.subscription_plan_id` (legacy) OR `SubscriptionLine.package_version_id` (modern) | Dual write during provisioning | Drift: legacy and modern may disagree | **Product requirement confirmed by owner:** modern package/subscription/entitlement structure is contractual source of truth | Candidate: Add `EntitlementProjectionService.calculate(tenant_id)` on subscription webhook (MC-010) |
| **Modules included in package** | `SubscriptionPlan.modules_included` (JSON, legacy) OR `PackageVersion.entitlements` (modern) | `LegacyEntitlementAdapter` bridges at read-time | Modern changes do not auto-sync to legacy; `TenantModule` rows may be stale | **Product requirement confirmed by owner:** `TenantModule` is the effective runtime projection checked by module guards; legacy JSON remains compatibility-only during migration and must not become a competing runtime authority | Candidate: Add sync trigger on subscription change; document authoritative resolver order (MC-010) |
| **Modules currently enabled** | `TenantModule` rows + `TenantFeatureFlag` rows | `get_active_modules_for_tenant()` queries both | If `TenantModule` is stale, `guard_module` enforces outdated permissions | **Product requirement confirmed by owner:** `TenantFeatureFlag` is an explicit override layer only where already intended | Candidate: Add `EntitlementProjectionService.calculate(tenant_id)` on subscription webhook (MC-010) |
| **Value checked by `guard_module`** | `FeatureGateService.module_enabled(tenant.id, module)` → queries `get_active_modules_for_tenant()` | Real-time query on each request | If tenant context missing, `guard_module` returns silently instead of 403 | Fix `guard_module` to abort on missing tenant | Verified fail-open code path: Change `return` to `abort(403)` (B-005 / MC-001) |
| **Upgrade/downgrade behavior** | `StripeWebhookEvent` processing in `stripe_subscription_service.py` | Webhook handlers call `TenantProvisioningService` | `subscription.deleted` webhook exists; SDK cancel may not trigger local entitlement update | Verify cancel_subscription → cancel_tenant linkage | Candidate: Phase 0 Stripe fix already in PLAN |
| **Platform-owner or super-admin tenant switching** | Not implemented as explicit switch | Super admin uses exempt paths (`/owner/`, `/super-admin/`) or inherits session tenant | No audited "impersonate tenant" flow | **Product requirement confirmed by owner:** any cross-tenant access must eventually use explicit, audited tenant-assumption workflow; until designed and approved, platform roles must not silently bypass tenant or module controls on ordinary tenant paths | Awaiting explicit tenant-assumption workflow design and approval |
| **Audit logging for elevated cross-tenant operations** | `AuditTrail` table logs `user_id`, `action`, `entity_type` | `log_action` decorator and manual `AuditTrail` creation | Does not log `tenant_id` context or tenant switches | Should audit trail include `from_tenant_id`, `to_tenant_id` for switches? | Awaiting product decision |

---

## F. Route, Blueprint, and Background-Job Coverage Inventory

### F.1 Route and Blueprint Inventory

| Route Group | Registration Location | Classification | Tenant Check | Module Key | Role Check | Assignment / Unit Check | Sensitive Data or Mutation | Status |
| ----------- | --------------------- | -------------- | ------------ | ---------- | ---------- | ----------------------- | -------------------------- | ------ |
| `routes/auth.py` | Loose file | Public | N/A | N/A | Login only | N/A | Authentication | Public |
| `routes/main.py` | Loose file | Public / shared | N/A | N/A | N/A | N/A | Dashboard redirects | Public |
| `routes/reception/` | `__init__.py` | Module-specific | `before_compile` (implicit) | `reception` | `role_required`, manual checks | No doctor/unit filter on list | Visit CRUD, patient data | Guarded |
| `routes/doctor/` | `__init__.py` | Module-specific | Explicit `tenant_id` + `doctor_id` | `doctor` | `role_required` | `doctor_id == current_user.id` | Visit CRUD, prescriptions, diagnoses | Guarded |
| `routes/lab/` | `__init__.py` | Module-specific | Explicit `tenant_id` | `lab` | `role_required` | No unit-level check | Lab requests, results | Guarded |
| `routes/radiology/` | `__init__.py` | Module-specific | Explicit `tenant_id` | `radiology` | `role_required` | No unit-level check | Radiology requests, images | Guarded |
| `routes/emergency/` | `__init__.py` | Module-specific | `before_compile` (implicit) | `emergency` | Manual role checks | No emergency-unit check | Emergency cases, triage | Guarded |
| `routes/medication_routes/` | `__init__.py` | Module-specific | Explicit `tenant_id` | `pharmacy` | `role_required` | No unit-level check | Prescriptions, inventory | Guarded |
| `routes/nurse_routes/` | `__init__.py` | Module-specific | Explicit `tenant_id` | `nursing` | `role_required` | No unit-level check | Medication admin, vitals | Guarded |
| `routes/accountant/` | `__init__.py` | Module-specific | `before_compile` (implicit) | `billing` | `role_required` | No invoice-ownership check | Invoices, payments, GL | Guarded |
| `routes/manager/` | `__init__.py` | Shared capability | `before_compile` (implicit) | N/A | `manager_or_admin_only` | No department filter | Analytics, staff, schedules | **UNGUARDED** |
| `routes/super_admin/` | `__init__.py` | Platform scope | Exempt paths | N/A | `super_admin_required` | N/A | Platform admin | Platform |
| `routes/owner/` | `__init__.py` | Platform scope | Exempt paths | N/A | `owner` role check | N/A | Owner console | Platform |
| `routes/saas_routes.py` | Loose file | Shared capability | `before_compile` (implicit) | N/A | Mixed (public signup + auth) | N/A | Registration, signup | Shared |
| `routes/patient_portal.py` | Loose file | Module-specific | `before_compile` (implicit) | `portal` | `login_required` only | Patient owns own data | Patient self-service data | **UNGUARDED** |
| `routes/ai_imaging_routes.py` | Loose file | Module-specific | `before_compile` (implicit) | `ai_imaging` | Role checks | No unit check | AI diagnostics on images | **UNGUARDED** |
| `routes/telemedicine_routes.py` | Loose file | Module-specific | `before_compile` (implicit) | `telemedicine` | Role checks | No unit check | Video sessions | **UNGUARDED** |
| `routes/fhir_routes.py` | Loose file | Module-specific | `before_compile` (implicit) | `fhir_api` | `role_required` | No unit check | Structured patient data export | **UNGUARDED** |
| `routes/biometric_routes.py` | Loose file | Module-specific | `before_compile` (implicit) | `webauthn` | Role checks | N/A | Authentication credentials | **UNGUARDED** |
| `routes/bed_management_routes.py` | Loose file | Module-specific | `before_compile` (implicit) | `bed_management` | Role checks | Ward/room assignment | Bed allocation | **UNGUARDED** |

### F.2 Background Job and Notification Path Inventory

| Background Job / Notification Path | Trigger | Tenant Context Source | Explicit Tenant Validation | Module Check | Risk | Status |
| ---------------------------------- | ------- | --------------------- | -------------------------- | ------------ | ---- | ------ |
| **Treatment completion notification** | `routes/doctor/visits.py::end_treatment()` calls `NotificationService.send_notification(recipient_role='reception')` | `g.tenant_id` from request context | None in notification service | None | Notification may be delivered to wrong tenant if background worker loses context | Candidate |
| **Billing webhook processing** | Stripe webhook handler | `StripeWebhookEvent.tenant_id` | None visible in handler code | N/A | Webhook may process for wrong tenant if ID is not validated | Candidate |
| **Celery system tasks** | `celery_app.py` | `app_context()` only — no `g.tenant_id` binding | None | None | Unscoped queries possible | Candidate |
| **Tenant job runner** | `services/tenant_job_runner.py::for_each_tenant()` | Explicit `with_tenant_context(app, tenant_id)` | Yes, per-tenant iteration | None | If `with_tenant_context` is not used, queries leak | Verified (Phase 0 fix already in PLAN) |
| **Backup automation** | `services/backup_automation_service.py` | `Backup.tenant_id` | Should use `with_tenant_context` | None | If not wrapped, backup queries may be unscoped | Candidate |
| **Scheduled notifications** | `app_factory.py` ~1071-1084 | `g.tenant_id` from request that triggered schedule? | Unclear | None | May lose tenant context in scheduler | Suspected |

### F.3 Background Job Technical Verification Inventory (B-014)

**Status:** Technical verification required. This is an audit question, not a product-owner decision.

| Task / Job | Entry Point | Tenant-Scoped Data? | Tenant Context Source | Wrapper / Decorator Present? | Runtime Risk | Verification Status |
| ---------- | ----------- | ------------------- | --------------------- | ---------------------------- | ------------ | ------------------- |
| Celery system tasks | `celery_app.py` | Yes | `app_context()` only | No `tenant_task` or `with_tenant_context` visible | Unscoped queries possible | ⬜ Not verified |
| Tenant job runner | `services/tenant_job_runner.py::for_each_tenant()` | Yes | `with_tenant_context(app, tenant_id)` | Yes — explicit wrapper | If wrapper skipped, queries leak | ⬜ Not verified at call sites |
| Backup automation | `services/backup_automation_service.py` | Yes | `Backup.tenant_id` | No visible wrapper | Unscoped backup queries possible | ⬜ Not verified |
| Billing webhook processing | Stripe webhook handler | Yes | `StripeWebhookEvent.tenant_id` | No visible wrapper | Webhook may process for wrong tenant | ⬜ Not verified |
| Treatment completion notification | `NotificationService.send_notification()` | Yes | `g.tenant_id` from request context | No visible wrapper in notification service | Notification may deliver to wrong tenant | ⬜ Not verified |
| Scheduled notifications | `app_factory.py` ~1071-1084 | Yes | Unclear | No visible wrapper | May lose tenant context in scheduler | ⬜ Not verified |
| Lab/radiology asynchronous workflow | Repository-wide task inventory required | Yes | Unknown | Unknown | Unknown | ⬜ Not inventoried |

**Action:** Complete the inventory for all Celery tasks, scheduler tasks, notification delivery, backups, billing webhooks, lab/radiology workflows, and system tasks. Verify whether `tenant_task` or `with_tenant_context` is present at every entry point.

**Treatment-completion notification verification (B-015):**
- Which users are selected for `recipient_role='reception'`.
- Whether the recipient query includes the correct tenant and branch context.
- Whether background delivery preserves that same tenant context.
- Whether a notification can ever cross tenants.

---

## G. Proposed Tickets and Approval Gate

**Prerequisites for any P0 implementation:**
1. **Baseline backup** of current code and database before any change.
2. **Migration head verified** — `alembic current` matches expected baseline.
3. **Rollback procedure** documented for each P0 ticket (single-line revert or documented steps).
4. **No P0 ticket may move toward implementation until prerequisites 1-3 are recorded as satisfied in this plan.**

**Dependency rules:**
- Dependencies are used only where one ticket technically blocks another.
- Artificial coupling has been removed.

| Ticket ID | Priority | Problem Proven | Existing Structure to Reuse | Smallest Safe Change | Dependencies | Prerequisites Satisfied | Required Tests | Rollback | Approval Status |
| --------- | -------- | -------------- | --------------------------- | -------------------- | ------------ | ---------------------- | -------------- | -------- | --------------- |
| **MC-001** | P0 | B-005: `guard_module` returns silently on missing tenant | `FeatureGateService` | Change line 70 from `return` to `abort(403, description="Tenant context required for module access")` | None | ⬜ Pending baseline, migration head, rollback docs | `test_guard_module_missing_tenant_aborts_403` | Revert single line | **Awaiting explicit implementation approval** |
| **MC-002** | P0 | B-001: `Visit` creation lacks explicit `tenant_id` | `Visit` model, `before_flush` hook | Add `tenant_id=g.tenant_id` to `Visit(...)` constructor in `create_visit()` and `create_emergency_case()`; validate `g.tenant_id` is not None first via fail-closed check | Validated fail-closed tenant context (MC-005 or equivalent already-verified tenant-context invariant) | ⬜ Pending baseline, migration head, rollback docs | `test_create_visit_has_tenant_id`, `test_create_visit_no_tenant_context_fails` | Remove explicit parameter | **Awaiting explicit implementation approval** |
| **MC-003** | P0 | B-002: Reception routes use naked `db.session.get(Visit, id)` | `get_tenant_record()` helper | Replace `db.session.get(Visit, id)` with `get_tenant_record(Visit, id)` in `archive_visit`, `end_visit`, `view_visit`, `edit_visit` | Verified `get_tenant_record()` contract (does not require MC-001 unless actual code dependency proven) | ⬜ Pending baseline, migration head, rollback docs | `test_reception_archive_visit_cross_tenant_blocked` | Revert to `db.session.get` | **Awaiting explicit implementation approval** |
| **MC-004** | P0 | B-004: Billing routes lack visit ownership validation | `GatekeeperService`, `get_tenant_record()` | Add `get_tenant_record(Visit, id)` in `process_payment`, `archive_visit` (finance), `post_gl` before service delegation | Verified `get_tenant_record()` contract if helper is selected; otherwise specify explicit tenant-filtered query behavior | ⬜ Pending baseline, migration head, rollback docs | `test_billing_visit_ownership_check`, `test_accountant_cannot_process_cross_tenant` | Remove explicit lookup | **Awaiting explicit implementation approval** |
| **MC-005** | P1 | B-006: No `current_user.tenant_id == g.tenant_id` validation | `set_tenant_context()` middleware | Add assertion after tenant resolution: if authenticated user has `tenant_id` and it mismatches resolved tenant, abort 403 (with exempt paths for `/owner/`, `/super-admin/`) | None (tenant-security foundation; does not depend on MC-001) | ⬜ Pending baseline, migration head, rollback docs | `test_user_cannot_hop_tenants_by_slug`, `test_super_admin_exempt_on_platform_paths` | Remove assertion | **Awaiting explicit implementation approval** |
| **MC-006** | P1 | B-008: Loose patient-data route files lack module guards | `require_module` decorator, `guard_module` | Per-endpoint classification before module enforcement: for every loose route module, classify each endpoint as public authentication/bootstrap, platform administration, tenant shared capability, module-specific read/write, or callback/webhook/integration. Only tenant module-specific operations may receive module enforcement. Public login, bootstrap, webhook verification, or platform paths must not be accidentally blocked. | Verified effective entitlement-projection contract from MC-010, or an explicitly documented temporary enforcement rule using the current runtime projection | ⬜ Pending baseline, migration head, rollback docs | `test_patient_portal_disabled_module_403`, `test_ai_imaging_disabled_module_403` | Remove decorators | **Awaiting explicit implementation approval** |
| **MC-007** | P1 | B-010: `super_admin` blanket module bypass | `FeatureGateService`, `_is_admin_user()` | Restrict super admin bypass to paths starting with `/super-admin/` or `/owner/`; on regular paths, enforce same module checks as normal users | Precise platform-path and tenant-context boundary definition (does not depend solely on MC-001) | ⬜ Pending baseline, migration head, rollback docs | `test_super_admin_regular_path_module_enforced` | Revert bypass restriction | **Awaiting explicit implementation approval** |
| **MC-008** | P1 | B-011: Lab/radiology unit authorization | `LabRequest`, `RadiologyRequest` models | Discovery-first: (1) inventory all existing fields and relationships on `LabRequest`, `RadiologyRequest`, queue records, departments, branches, users, and any assignment tables; (2) determine whether any existing field already identifies the performing unit or explicit assignee; (3) define the authorization rule using existing data if possible; (4) only if no existing safe boundary exists, record a separate future design decision — do not propose a field, Model, migration, or new table yet | Request/unit field inventory (does not depend on MC-003) | ⬜ Pending baseline, migration head, rollback docs | `test_lab_tech_cross_unit_blocked` | Remove unit filter | **Awaiting explicit implementation approval** |
| **MC-009** | P1 | B-012 / D-GAP-01: Reassigned completed visit invisible to new doctor | `VisitStateMachineService`, `transfer_visit()` | Implementation first determines whether the current route/service already has an explicit action or intent parameter that can safely represent "return to treatment." If no safe existing distinction exists, record this as a design gap. Only an explicit "return to treatment" action may trigger `COMPLETED → OPEN`. Must verify financial/archive eligibility before transition. | State-machine transition review; QueueManagement data model and constraints review; Financial/archive eligibility review; Existing transfer route/service contract review; Clinical record and order integrity review | ⬜ Pending baseline, migration head, rollback docs | `test_reassigned_completed_visit_visible_to_new_doctor`, `test_reassignment_fails_closed_on_invalid_state_transition`, `test_return_to_treatment_requires_explicit_intent` | Revert status change and queue ticket logic | **Awaiting explicit implementation approval** |
| **MC-010** | P1 | B-009: Package/entitlement dual source of truth | `EntitlementResolver`, `TenantModule` | Define sync trigger on subscription change: regenerate `TenantModule` projection from modern `PackageVersion` + `SubscriptionLine` + `TenantEntitlement`; document authoritative resolver order; legacy JSON read-only | Platform engineering decision | ⬜ Pending baseline, migration head, rollback docs | `test_entitlement_sync_on_subscription_change`, `test_legacy_json_not_used_at_runtime` | Revert to dual-query | **Awaiting explicit implementation approval** |
| **MC-011** | P2 | B-007: `SystemConfig` ownership model | `SystemConfig` model, `_skip_table` | **No model or constraint changes.** Verification task only: inventory all `SystemConfig` consumers. If any tenant-specific settings are being stored, record them as a separate future design issue and first look for existing tenant-settings or feature-flag structure before proposing any new Model or migration | None | ⬜ Pending baseline, migration head, rollback docs | `test_system_config_global_only` | N/A (verification only) | **Awaiting explicit implementation approval** |
| **MC-012** | P2 | B-014: Background job tenant context | `tenant_job_runner.py`, `celery_app.py` | Complete inventory per F.3; ensure `with_tenant_context` wraps all tenant-scoped work | Phase 0 Celery fix already in PLAN | ⬜ Pending baseline, migration head, rollback docs | `test_celery_task_preserves_tenant_context` | Remove wrappers | **Awaiting explicit implementation approval** |
| **MC-013** | P2 | B-016: Dedicated "completed awaiting action" reception dashboard | Reception visits list | If product requests: add filter helper `get_completed_awaiting_action_visits()`; no new state needed | None | ⬜ Pending baseline, migration head, rollback docs | `test_completed_visits_visible_to_reception` | Remove helper | **Awaiting explicit implementation approval** |
| **MC-014** | P1 — confirmed financial and workflow integrity requirement | B-017: Administration catalog, reception service selection, initial queue payment, and final reconciliation | `Visit`, `LabRequest`, `RadiologyRequest`, `Invoice`, `Payment`, `ServiceCatalog` (or equivalent) | Preserve department ability to report or add clinical services during and after treatment. Enforce reception-only control of all costs and financial entries using the administration-approved catalog or controlled custom service entry. Enforce the rule that a normal visit cannot enter any queue until its initial reception-selected fees are paid and backend-validated. Preserve emergency treatment without payment blocking. Allow reception to add approved catalog services or custom services before final settlement or archive without reopening the clinical visit or queue. Reconcile all reception-recorded chargeable services before final settlement or archive. Exclude prescriptions and external medication purchases. Reuse existing financial structures only; do not propose a new billing model, invoice model, or pharmacy financial workflow. | Add dependencies only when the audited reception or department service path actually uses unsafe tenant or ownership access (B-001, B-002 are not automatic blockers) | ⬜ Pending baseline, migration head, rollback docs | `test_reception_sees_dynamic_doctor_service_catalog`, `test_reception_sees_dynamic_department_service_catalog`, `test_reception_cannot_override_configured_service_price`, `test_normal_visit_cannot_enter_any_queue_before_initial_fees_paid`, `test_emergency_can_enter_queue_without_initial_payment`, `test_reception_can_add_catalog_service_after_treatment_completion`, `test_post_completed_reception_service_addition_does_not_reopen_visit_or_queue`, `test_department_cannot_write_financial_service_or_price_fields`, `test_archive_blocks_when_reception_catalog_services_are_unsettled`, `test_final_settlement_or_archive_blocks_new_service_additions` | Revert route/service changes | **Evidence-ready — awaiting implementation approval** |

**MC-009 mandatory pre-implementation investigations:**
1. **QueueManagement constraints and indexes:** Identify all unique constraints, foreign keys, and indexes on `queue_management` and related tables.
2. **Queue ticket cardinality:** Confirm whether more than one queue ticket may exist for one visit.
3. **Completed ticket immutability:** Confirm whether completed tickets are immutable historical records.
4. **Second queue cycle support:** Confirm whether the system already supports a second queue cycle for the same visit.
5. **Assignment/department/status/history relationships:** Document how doctor assignment, department assignment, ticket status, and ticket history relate.
6. **Current transfer behavior:** Document what happens today when a completed ticket is transferred.
7. **Queue history auditability:** Confirm whether queue history remains auditable after return to treatment.
8. **MedicalRecord immutability/versioning:** Confirm whether `MedicalRecord` created at treatment completion is immutable, versioned, or editable.
9. **Clinical record overwrite risk:** Confirm whether returning the visit to treatment could overwrite or duplicate a completed clinical record.
10. **Order linkage integrity:** Confirm how existing prescriptions, lab requests, radiology requests, diagnoses, and clinical notes behave after reopening.
11. **Outstanding/completed order linkage:** Confirm whether outstanding or completed orders remain linked correctly to the same visit.
12. **Completion metadata preservation:** Confirm whether `completed_by` and `completed_at` remain historically correct after reopening, or whether the history is preserved only through workflow events.
13. **State machine safeguard:** Confirm whether the state machine permits `COMPLETED → OPEN` without bypassing its intended clinical safeguards.

**Preferred principle:** Do not mutate a completed historical ticket unless the existing data model explicitly supports reopening it safely. Create a new queue cycle only if the current schema and audit model support it without losing history or violating uniqueness constraints. Do not choose either approach before this review is complete.

**MC-009 financial and archive guards (must verify before any return to treatment):**
- The visit is not archived (`archive_status != ARCHIVED`).
- The visit is not financially locked (`financial_locked != True`).
- No final GL posting has occurred (`gl_posted_at is None`), unless an approved reversal workflow exists.
- No final invoice or receipt state would be invalidated.
- Any mandatory clinical or legal closure rule is not violated.
- If a financial reversal is needed, do not invent one. Record it as a separate future workflow decision.

**MC-006 per-endpoint classification requirement:**
For every loose route file (`patient_portal.py`, `ai_imaging_routes.py`, `telemedicine_routes.py`, `fhir_routes.py`, `biometric_routes.py`, `bed_management_routes.py`), classify each endpoint as:
- **Public authentication or bootstrap** — must NOT receive module enforcement.
- **Platform administration** — must NOT receive tenant module enforcement.
- **Tenant shared capability** — may need capability check but not module entitlement.
- **Module-specific read/write operation** — candidate for `@require_module(...)` or `guard_module`.
- **Callback, webhook, or integration endpoint** — must NOT receive module enforcement.

Only tenant module-specific operations may receive module enforcement. Public login, bootstrap, webhook verification, or platform paths must not be accidentally blocked or broken.

**MC-008 discovery-first steps:**
1. Inventory all existing fields and relationships on `LabRequest`, `RadiologyRequest`, queue records, departments, branches, users, and any assignment tables.
2. Determine whether any existing field already identifies the performing unit or explicit assignee.
3. Define the authorization rule using existing data if possible.
4. Only if no existing safe boundary exists, record a separate future design decision.
5. Do not propose a field, Model, migration, or new table until step 4 is reached.

**MC-014 technical discovery — administration catalog, reception service selection, initial queue payment, and final reconciliation:**

| Event | Allowed Actor | Financial Actor | Required Result |
| ----- | ------------- | --------------- | --------------- |
| Service catalog and prices | Administration | Administration | Approved service catalog and configured prices exist and are authoritative; each doctor, department, and unit has a dynamic configured service list |
| Initial visit service selection | Reception | Reception | Reception selects from dynamic approved catalog or enters controlled custom service after selecting doctor, department, or unit; initial costs and payment condition recorded before normal queue entry |
| Clinical service added during treatment | Department / doctor | Reception only | Clinical record exists; reception selects from approved catalog to record the approved cost |
| Clinical service reported after treatment | Department / doctor | Reception only | Reception selects from approved catalog to record the charge before closure/archive |
| Reception adds service directly to completed visit | Reception | Reception | Financial obligation recorded through existing financial flow using approved catalog price or custom service price; `COMPLETED` status and queue state unchanged |
| Prescription or medication | Doctor / department | None | Clinical only; no automatic financial charge |
| Emergency treatment | Emergency unit | Reception later | Treatment never blocked by payment; later charge reconciliation before final closure using approved catalog or custom service price |
| Final closure or archive | Reception | Reception / accountant according to existing flow | Block unless all reception-recorded chargeable services are financially settled; block new service additions unless separately approved correction/reversal workflow exists |

**MC-014 work packages:**

| Work Package | Scope | Verified Evidence | Gap or Remediation Candidate | Approval Status |
| ------------ | ----- | ----------------- | -------------------------- | --------------- |
| **WP-1: Catalog service selection and configured pricing** | Administration-managed `ServiceMaster`, `DoctorPricing`, `PricingCatalog`, `PricingManagement`; dynamic service loading via `api_department_services`; reception selects from approved catalog; no manual price override | `models/service.py` `ServiceMaster`; `models/pricing.py` `DoctorPricing`/`PricingCatalog`; `models/pricing_management.py` `PricingManagement`; `routes/reception/api.py` `api_department_services`; `routes/manager/pricing.py` CRUD endpoints | `_process_custom_services` creates `ServiceMaster` immediately with `is_active=True` and no structural distinction from catalog services; no `is_custom` or `pending_approval` flag exists | **Awaiting explicit implementation approval** |
| **WP-2: Controlled custom-service entry, current-visit validity, manager review, and later promotion to reusable catalog service** | Reception may manually enter custom service name and price when service is not in catalog; manager later reviews and approves before it becomes a fixed reusable catalog item; workflow must remain auditable; no department may enter prices | `routes/reception/visits.py` `_process_custom_services` — lines 208-247: creates `ServiceMaster` with `code=CUSTOM-{dept}-{UUID}`, reception-entered `name`, `base_price`, `description` includes creator name; `routes/manager/pricing.py` allows manager to edit/delete `ServiceMaster` but has no dedicated approval/promotion route | **Direct workflow contradiction:** `_process_custom_services` creates `ServiceMaster` with `is_active=True` immediately, making the custom service available to all future visits without manager review or approval. **Structural gaps:** No `is_custom`/`pending_approval`/`approved_by`/`created_by` on `ServiceMaster`; no `service_master_id` or `created_by` on `InvoiceService`; `AuditTrail.entity_type` check constraint excludes `'service'`. | **Awaiting explicit implementation approval** |
| **WP-3: Strict full initial-payment gate before any normal queue entry** | Backend-enforced rule: normal (non-emergency, non-force) visits cannot enter any queue until all initial reception-selected service fees are fully paid and validated | `services/queue_management_service.py` `_check_queue_entry_conditions` — line 246: `PENDING` status blocked; `PAID` allowed; `PARTIAL` + `allow_partial_payment=True` (default) -> allowed; `is_emergency` always allowed; `QueueSettings` defaults to `payment_required=True`, `allow_debt=False`; queue-entry paths: `routes/reception/visits.py` line 673 (auto after creation), `routes/reception/queue.py` line 92 (manual), `routes/reception/appointments.py` lines 120/197 (appointment), `routes/reception/queue.py` line 997 (`add_patient_to_queue_auto`) | **Direct workflow contradiction:** `PARTIAL` payment status is permitted into any normal queue when `allow_partial_payment=True` (default per-department `QueueSettings`). Owner rule: a normal non-emergency visit must not enter any queue until all initial reception-selected fees are fully paid. Emergency and force-entry remain the only exceptions. | **Awaiting explicit implementation approval** |
| **WP-4: Reception addition of catalog or controlled custom services to completed-but-active visits without reopening clinical status or queue** | Reception may add approved catalog services or controlled custom services before final settlement/archive without changing `COMPLETED` status or queue state | `routes/reception/visits.py` `edit_visit` — line 1048: does not accept `selected_tests`, modify `visit.total_amount`, create `InvoiceService` lines, or change visit status; `routes/reception/payments.py` `process_payment` — line 54: creates aggregate `InvoiceLine` only, does not add new services | **Feature gap:** No backend path exists for reception to append a catalog or custom service to a `COMPLETED` visit while preserving clinical state and queue history. Canonical financial line structure is `InvoiceService` (see Finding 3 below). | **Awaiting explicit implementation approval** |
| **WP-5: Final financial reconciliation and archive blocking** | Visit cannot be finally settled or archived until all reception-recorded catalog and custom services are financially resolved; after final settlement/archive, no new service or cost may be added unless an approved correction/reversal workflow exists | `services/gatekeeper_service.py` `can_archive_visit` — line 91: blocks on missing `gl_posted_at`, `financial_locked`, or (emergency) missing `financial_completed_at`; `services/gatekeeper_service.py` `archive_visit` — line 316: single owner of `Visit.archive_status` writes | **Architectural gap:** Archive check uses aggregate `visit.total_amount` vs `visit.paid_amount`, not per-service itemization; `process_payment` creates single aggregate `InvoiceLine` copying `visit.total_amount`; cannot detect whether an individual added service is unsettled | **Awaiting explicit implementation approval** |

**MC-014 bounded technical verification — custom service entry and manager approval (read-only, no new structures proposed):**

| Required Capability | Existing Evidence | Evidence Level | Gap |
|---------------------|-------------------|----------------|-----|
| Custom service name recorded | `_process_custom_services` writes `ServiceMaster.name` from form input | Code confirmed | None |
| Custom service price recorded | `_process_custom_services` writes `ServiceMaster.base_price` / `emergency_price` / `insurance_price` from form input | Code confirmed | None |
| Reception user who created it | `_process_custom_services` embeds `current_user.full_name or current_user.username` into `ServiceMaster.description` free-text field only | Code confirmed | **No dedicated `created_by` column on `ServiceMaster`** |
| Visit linkage | Custom service ID is appended to `selected_tests` and linked via `LabRequest`/`RadiologyRequest` rows; no direct visit-to-service junction table | Code confirmed | **No `VisitService` or equivalent junction table** |
| Timestamp | `ServiceMaster.created_at` is set by model default | Code confirmed | None |
| Manager review/approval status | **Not found** — no `approval_status`, `pending_approval`, `is_custom`, or `approved_by` field exists on `ServiceMaster` | Not found | **No structural flag or approval workflow exists** |
| Promotion or copying into reusable service catalog | **Not found** — custom services are immediately created as `ServiceMaster` with `is_active=True`; no promotion step exists | Not found | **No promotion workflow; custom and catalog services are structurally identical** |
| Audit trail of original custom entry and later approval | **Not found** — `_process_custom_services` does not write `AuditTrail`, `VisitWorkflowEvent`, or `VisitTransferLog`; `AuditTrail.entity_type` does not include `service` | Not found | **No audit trail records custom service creation or approval** |

**No new table, field, Enum, or migration is proposed at this stage.** Gaps are recorded precisely for future design decision.

**MC-014 evidence verification matrix (bounded pass — read-only):**

| # | Item Verified | Exact File / Function | Current Behavior | Evidence Level | Complies with Confirmed Workflow | Direct Contradiction | Smallest Safe Remediation Candidate |
|---|---------------|----------------------|------------------|----------------|-----------------------------------|---------------------|-------------------------------------|
| 1 | Administration-managed service catalog, pricing, and doctor/department/unit mappings | `models/service.py` `ServiceMaster` — line 10; `models/pricing.py` `ServicePrice` — line 12, `DoctorPricing` — line 90, `PricingCatalog` — line 241; `models/pricing_management.py` `PricingManagement` — line 12, `PricingRule` — line 105; `routes/manager/pricing.py` `get_services_api` / `add_service_api` / `update_service_api` — lines 57, 89, 129 | Administration REST endpoints provide full CRUD on `ServiceMaster` with `is_active`, `department_id`, `base_price`; `DoctorPricing` maps doctor-specific and department-specific prices; `PricingCatalog` provides central pricing by `service_type`; `PricingManagement` links `service_master.id` to `department_id` with granular pricing and conditional rules | Code confirmed | **Yes** | None | N/A |
| 2 | Reception backend path that dynamically loads approved services after doctor/department/unit selection | `routes/reception/api.py` `api_department_services` — line 129; `routes/reception/visits.py` `create_visit` — line 272; `routes/reception/visits.py` `_process_custom_services` — line 208 | `api_department_services` receives `department_id`, derives department type, queries `ServiceMaster` where `category == <type>` AND `department_id == <id>` AND `is_active == True`, returns JSON with `id`, `code`, `name`, `base_price`. `create_visit` reads `selected_tests` from form and validates IDs against active `ServiceMaster`. `_process_custom_services` receives manually entered custom names/prices, deduplicates against existing `ServiceMaster`, and creates a new `ServiceMaster` record with `code=CUSTOM-{dept}-{UUID}`, `is_active=True`, and the reception-entered price | Code confirmed | **Yes** — custom service entry is an approved reception-controlled exception | None — `_process_custom_services` is the existing custom-service entry path; it must remain restricted to reception only | Ensure `_process_custom_services` remains accessible only to reception role; verify no department route can invoke it; verify the resulting custom `ServiceMaster` record is structurally distinguishable or auditable for later manager review |
| 3 | Backend queue-entry path blocking normal visits until initial reception-selected fees are paid | `services/queue_management_service.py` `_check_queue_entry_conditions` — line 246; `services/queue_management_service.py` `add_patient_to_queue` — line 84; `routes/reception/queue.py` `add_patient_to_queue_auto` — line 997; `routes/reception/queue.py` `add_patient_to_queue` — line 92; `routes/reception/appointments.py` — lines 120/197 | Backend-enforced payment gate: `is_emergency` -> always allowed; `PAID` -> allowed; `PARTIAL` + `allow_partial_payment=True` (default) -> **allowed** with message `"دفع جزئي - يمكن الدخول"`; `PENDING` (default for unpaid) -> blocked with message `"يجب الدفع أولاً أو الحصول على موافقة للدين"`; `QueueSettings` is per-department (line 148) with `allow_partial_payment` default `True`. | Code confirmed | **No** — direct workflow contradiction | **Yes:** `PARTIAL` payment enters normal queues. Owner rule requires full payment before any normal queue entry. | Remove `PARTIAL` branch for normal (non-emergency, non-force) visits in `_check_queue_entry_conditions`; only `PAID` allows normal queue entry. Preserve emergency, force-entry, and explicitly-enabled debt exceptions. |
| 4 | Emergency exception path: treatment without payment, later reconciliation required | `routes/reception/visits.py` `create_visit` — lines 314–367; `services/gatekeeper_service.py` `can_enqueue_visit` — line 32; `services/gatekeeper_service.py` `create_provisional_receipt` — line 179; `services/gatekeeper_service.py` `can_archive_visit` — line 91 | Emergency visit auto-sets `is_emergency=True`, `is_force_payment=True`. `can_enqueue_visit` requires `liability_acknowledged_at` and sets `financial_locked=True`. `create_provisional_receipt` creates provisional `Payment` but keeps `financial_locked=True`. `can_archive_visit` requires `financial_completed_at` for emergency/strong-pay in addition to `gl_posted_at` and `financial_locked==False` | Code confirmed | **Yes** | None | N/A |
| 5 | Reception path for adding approved catalog services to a completed-but-unarchived visit without reopening | `routes/reception/visits.py` `edit_visit` — line 1048; `routes/reception/payments.py` `process_payment` — line 54 | `edit_visit` updates `department_id`, `doctor_id`, `visit_type`, `symptoms`, `notes`, `payment_method`. It does **not** accept `selected_tests`, modify `visit.total_amount`, create `InvoiceService` lines, or change visit status. `process_payment` creates an `Invoice` and single aggregate `InvoiceLine` mirroring existing `visit.total_amount`; it does **not** add new catalog services. **No backend path exists for reception to append a catalog service to a `COMPLETED` visit** | Code confirmed / Not found | **No** — feature gap, not contradiction | None — the confirmed owner workflow requires this capability, but the codebase does not currently support it | Add a reception route/service that accepts `visit_id` + `service_master_id` (or controlled custom-service entry), validates the service is active and in the approved catalog (or follows custom-service workflow), creates `InvoiceService` line(s) via the canonical existing structure, increments `visit.total_amount`, updates `payment_status` to `PARTIAL`/`PENDING` if now unpaid, writes `AuditTrail`, and blocks if `archive_status=ARCHIVED` or `financial_locked=True` or `gl_posted_at` is set. No `visit.status` or queue change. |
| 6 | Authoritative financial records and archive/final-settlement check that blocks unresolved reception-recorded services | `services/gatekeeper_service.py` `can_archive_visit` — line 91; `services/gatekeeper_service.py` `archive_visit` — line 316; `models/invoice.py` `Invoice` — line 10, `InvoiceService` — line 77; `models/payment.py` `Payment` — line 16; `models/receipt.py` `Receipt` — line 14 | `can_archive_visit` blocks if `gl_posted_at` is missing, `financial_locked` is True, or (for emergency) `financial_completed_at` is missing. `archive_visit` is the single owner of `Visit.archive_status` writes (comment P1-002). `Invoice` + `InvoiceService` hold per-line `unit_price`/`total_price`. `Payment` records every transaction. `Receipt` holds receipt-level totals. **However, `process_payment` creates only one aggregate `InvoiceLine` copying `visit.total_amount`; it does not itemize individual services, so archive check cannot verify per-service settlement** | Code confirmed | **Partial** — aggregate-level check exists; per-service settlement check missing | None — the archive check operates on aggregate `visit.total_amount` vs `visit.paid_amount`, not on individual catalog services. This is an architectural gap, not a direct contradiction with the owner workflow, but it means the system cannot detect whether an individual added service is unsettled | **Canonical existing financial service-line structure is `InvoiceService`** (see Finding 3 below). For WP-5, enforce per-service itemization via `InvoiceService` before archive: each reception-selected service must have a matching `InvoiceService` line; aggregate `visit.total_amount` must equal sum of `InvoiceService.total_price` for the visit; `visit.paid_amount` must cover the full sum. This reuses existing `InvoiceService` structure without new models. |

**Department financial field write blocking (bonus verification):**
- `routes/doctor/` — no writes to `total_amount`, `paid_amount`, `payment_method`, `invoice`, `receipt`, `financial_locked`, `gl_posted_at` found. **Compliant.**
- `routes/lab/` — no visit-level financial field writes found. **Compliant.**
- `routes/radiology/` — no visit-level financial field writes found. **Compliant.**
- `routes/emergency/` — no visit-level financial field writes found; only modifies clinical fields. **Compliant.**
- `routes/nurse_routes/` — no visit-level financial field writes found. **Compliant.**
- `routes/medication_routes/` — `pos.py` writes `PharmacySale.total_amount` and `payment_method` (pharmacy-sale-level, not visit-level). `catalog.py`, `external.py`, `suppliers.py` write catalog-level `price`/`purchase_price`/`selling_price` (not visit financial fields). **Partial** — pharmacy POS is a separate workflow; no visit-level financial writes.

---

## G.2 MC-014 Corrected Findings (Update 9)

### Finding 1: Normal Visit Payment Gate — PARTIAL Payment Must Not Enter Any Normal Queue

**Confirmed owner rule:** `A normal non-emergency visit must not enter any queue until all initial reception-selected service fees are fully paid.`

**Evidence:**
- `services/queue_management_service.py` `_check_queue_entry_conditions` — line 262: `elif payment_status == PaymentStatus.PARTIAL and getattr(settings, 'allow_partial_payment', True): return True, "دفع جزئي - يمكن الدخول"`
- `models/queue_management.py` `QueueSettings` — line 160: `allow_partial_payment = db.Column(db.Boolean, default=True)`; line 148: `department_id` FK, so `allow_partial_payment` is **per-department**, not global or per-queue.
- `QueueSettings` defaults created in `add_patient_to_queue` (lines 99-108 of `queue_management_service.py`) set `allow_partial_payment=True`.
- Every queue-entry path passes `visit.payment_status` or form-provided `payment_status` into `_check_queue_entry_conditions`:
  - `routes/reception/visits.py` line 673: auto-add after visit creation via `add_patient_to_queue_auto` (line 997 of `queue.py`), passing `visit.payment_status`
  - `routes/reception/queue.py` line 92: manual queue entry, reading `payment_status` from form (line 115)
  - `routes/reception/appointments.py` lines 120/197: appointment queue entry via `add_patient_to_queue_auto`
- When a visit is created with partial payment (e.g., insurance patient share at line 600 of `visits.py`, or cash partial at line 574), `payment_status` is set to `PARTIAL`, then queue entry is attempted immediately after `db.session.commit()` (line 673).

**Classification:** Direct workflow contradiction — not “no gap.” Current code permits `PARTIAL` to enter doctor, laboratory, radiology, and any other normal queue when `allow_partial_payment=True`.

**Smallest safe remediation:** In `_check_queue_entry_conditions`, remove the `PARTIAL` branch for normal (non-emergency, non-force_entry) visits. Only `PAID` should allow normal queue entry. Preserve existing emergency bypass (`is_emergency`), force-entry bypass (`force_entry + settings.force_entry_allowed`), and explicitly-enabled debt path (`DEBT + allow_debt=True`). Do not change payment policies for archived or historical visits.

**Required tests:**
- `test_normal_visit_partial_payment_blocked_from_all_queues`
- `test_normal_visit_paid_enters_queue`
- `test_emergency_partial_payment_allowed`
- `test_force_entry_partial_payment_allowed`
- `test_debt_with_explicit_allow_blocked_by_default`
- `test_debt_with_explicit_allow_allowed_when_enabled`

**Rollback path:** Revert the single branch removal in `_check_queue_entry_conditions`.

**Implementation-ready:** Yes — the change is one branch removal with existing test coverage already in `tests/test_queue_management_service.py`.

---

### Finding 2: Custom Service — Immediate Global Activation is a Direct Workflow Contradiction

**Confirmed owner rule:** `Reception may enter a custom service name and price for the current visit. The custom service must be financially valid for that current visit. It must not automatically become an active reusable service for future visits. A manager must later review and approve it before it becomes a reusable approved catalog service.`

**Evidence:**
- `routes/reception/visits.py` `_process_custom_services` — lines 208-247:
  - Line 227-231: deduplicates against existing active `ServiceMaster` by name
  - Line 237-242: creates new `ServiceMaster` with `is_active=True`, making it immediately available to all future visits via `api_department_services` (which filters `is_active=True`)
  - No `is_custom`, `pending_approval`, `approved_by`, or `created_by` fields exist
  - Creator only embedded in free-text `description` (line 239)
  - No `AuditTrail` written for custom service creation
- `routes/manager/pricing.py` `get_services_api` / `update_service_api` — manager can see and edit all `ServiceMaster`, but there is no dedicated “approve custom service” or “promote to catalog” workflow.

**Classification:** Direct workflow contradiction — not “no gap.” Current behavior creates `ServiceMaster` with `is_active=True`, making it a globally active reusable catalog service immediately, bypassing the required manager review/approval step.

**Bounded technical design audit (existing structures only):**

| Question | Finding | Evidence | Verdict |
|----------|---------|--------|---------|
| 1. Can an inactive `ServiceMaster` remain valid and price-preserved for the current visit after being selected? | **Yes, with caveat.** `InvoiceService` stores `service_code` and `service_name` as strings with `unit_price`/`total_price` — it does NOT reference `ServiceMaster` by FK. So invoice lines are self-contained and survive `ServiceMaster` deactivation or deletion. However, `create_visit` validates selected tests against `ServiceMaster.is_active == True` (line 504 of `visits.py`). A custom service created in the same request and appended to `selected_tests` would pass because it is already in the list, but post-creation addition to a `COMPLETED` visit would need a separate validation path. | `models/invoice.py` `InvoiceService` lines 86-91; `routes/reception/visits.py` line 504 | `is_active=False` is safe for current-visit billing **if** the service addition path does not re-query `is_active` for already-selected items. |
| 2. Does the current visit have an existing financial/service-line record that can store the custom service name, amount, creator, and timestamp independently from the reusable catalog? | **Partially.** `InvoiceService` already stores `service_code`, `service_name`, `unit_price`, `total_price`, `quantity`, `notes`, `visit_id`, `created_at`. It does **not** store `created_by` (the reception user who added the line). | `models/invoice.py` `InvoiceService` lines 77-104 | Sufficient for name/amount/timestamp; insufficient for creator attribution. |
| 3. Can existing manager pricing routes activate or promote the service after manager review? | **Partially.** `update_service_api` (line 126 of `pricing.py`) can set `is_active=True`. There is no dedicated “approve custom service” or “promote to catalog” route, and no audit trail of the approval action. | `routes/manager/pricing.py` lines 126-156 | Existing generic update API supports activation, but lacks workflow semantics and audit logging. |
| 4. Can existing `AuditTrail` record creation, manager review, approval, rejection, and promotion without schema changes? | **Partially, with workaround.** `AuditTrail` has `entity_type`, `entity_id`, `action`, `user_id`, `old_values`, `new_values`, `description`, `notes`. However, the `entity_type` check constraint (`chk_entity_type`) does **not** include `'service'`. Events could be recorded using `entity_type='system'` with details in `notes`, but this loses specificity and queryability. | `models/audit_trail.py` lines 11-69, especially line 39 | Existing structure can store the data, but the check constraint blocks clean `entity_type='service'`. Minimum structural change: add `'service'` to `chk_entity_type`. |
| 5. Are existing models sufficient to distinguish: catalog service; custom service valid only for one visit; pending manager approval; approved reusable catalog service? | **No.** The existing `ServiceMaster` model has no `is_custom`, `pending_approval`, `approved_by`, `approved_at`, or `created_by` fields. All active services look identical. | `models/service.py` `ServiceMaster` lines 10-41 | Insufficient. |
| 6. Exact missing capability and minimum structural change required | **Missing:** `ServiceMaster.is_custom` (boolean), `ServiceMaster.pending_approval` (boolean), `ServiceMaster.approved_by` (FK to users), `ServiceMaster.approved_at` (datetime), `ServiceMaster.created_by` (FK to users). **Missing:** `InvoiceService.created_by` (FK to users), `InvoiceService.service_master_id` (nullable FK to ServiceMaster) to link lines back to source. **Missing:** `'service'` in `AuditTrail.chk_entity_type`. **No new table or Enum required.** | Synthesis from above | Minimum structural changes are column additions and a check-constraint expansion. No new model or migration blockers beyond these columns. |

**Conclusion on `is_active=False` safety:**
- Current-visit billing: **Safe** because `InvoiceService` stores strings, not FK.
- Historical visibility: **Safe** because invoice lines are self-contained.
- Manager approval behavior: **Partially safe** — manager can see and activate inactive services via existing API, but there is no workflow distinction between “activate a deactivated catalog service” and “approve a pending custom service.”
- Therefore, `is_active=False` alone is **insufficient** without additional structural flags (`is_custom`, `pending_approval`, `approved_by`) to distinguish the workflow intent.

**Smallest safe remediation candidate:**
1. Modify `_process_custom_services` to create `ServiceMaster` with `is_active=False` (or with a new `pending_approval=True` flag after schema change).
2. For current-visit validity, ensure the invoice line is created via `InvoiceService` with the custom name/price before the service is deactivated.
3. Add manager approval route that sets `is_active=True` and records `AuditTrail`.
4. Do not implement until the minimum structural changes are approved.

**Required tests:**
- `test_custom_service_creates_pending_not_active`
- `test_custom_service_not_visible_in_future_visit_catalog`
- `test_manager_can_approve_custom_service`
- `test_audit_trail_records_custom_service_creation_and_approval`
- `test_custom_service_invoice_line_preserved_after_deactivation`

**Rollback path:** Revert `_process_custom_services` to create `is_active=True`; remove any new columns if added.

**Implementation-ready:** No — requires minimum structural changes (column additions) before safe implementation.

---

### Finding 3: Canonical Existing Financial Service-Line Structure for Completed-Visit Addition

**Feature gap confirmed:** No backend path exists for reception to add a service to a `COMPLETED`, active, unarchived visit while preserving its clinical state and queue history.

**Trace of existing financial structures:**

| Structure | Role in Service-Line Recording | Evidence |
|-----------|-------------------------------|----------|
| `ServiceMaster` | Administration-managed catalog of approved services with configured prices | `models/service.py` lines 10-41 |
| `InvoiceService` (table `invoice_services`) | **Canonical individual service line** — stores `service_code`, `service_name`, `quantity`, `unit_price`, `total_price`, `notes`, `visit_id`, `department_id`, `invoice_id` | `models/invoice.py` lines 77-104 |
| `Invoice` (table `invoices`) | Parent document for one or more `InvoiceService` lines; holds `total_amount`, `paid_amount`, `status` | `models/invoice.py` lines 10-75 |
| `Visit.total_amount` | Aggregate of all chargeable services for the visit | `models/visit.py` line 25 |
| `Visit.paid_amount` | Aggregate of all payments received for the visit | `models/visit.py` line 26 |
| `Payment` (table `payments`) | Individual payment transaction record, linked to visit or invoice | `models/payment.py` lines 16-80 |
| `Receipt` (table `receipts`) | Receipt document summarizing payment outcome | `models/receipt.py` lines 14-80 |
| `AuditTrail` (table `audit_trails`) | Audit log for service additions, payment events, archive actions | `models/audit_trail.py` lines 11-69 |
| `GatekeeperService.can_archive_visit` | Archive eligibility check using `gl_posted_at`, `financial_locked`, `financial_completed_at` | `services/gatekeeper_service.py` lines 91-118 |

**Decision:** The canonical existing financial service-line structure is **`InvoiceService`** (`models/invoice.py` lines 77-104). It already has all fields needed for an individual reception-selected service line: `service_code`, `service_name`, `quantity`, `unit_price`, `total_price`, `visit_id`, `department_id`, `notes`. It does not require a new model, table, or Enum.

**Design for WP-4 (reception addition to completed visit):**
1. ** Preconditions:** Visit `status=COMPLETED`, `archive_status=ACTIVE`, `financial_locked=False`, `gl_posted_at=None`. Block if archived or financially locked.
2. **Catalog service:** Reception provides `visit_id` + `service_master_id`. Backend validates `ServiceMaster.is_active=True` and that the service belongs to the visit's doctor/department/unit approved catalog (via `api_department_services` logic). Price loaded server-side from `ServiceMaster.base_price` (or `insurance_price` if applicable). No client-side price override permitted.
3. **Custom service:** If service is not in catalog, use the controlled custom-service workflow (WP-2) to create a pending `ServiceMaster`, then add the `InvoiceService` line immediately for current-visit validity.
4. **Financial line creation:** Create or reuse an `Invoice` for the visit (status `DRAFT` or `ISSUED`). Append an `InvoiceService` line with the service details. Increment `Visit.total_amount` by `InvoiceService.total_price`. Update `Visit.payment_status` to `PARTIAL` or `PENDING` if `paid_amount < total_amount`.
5. **No clinical change:** Do not modify `Visit.status`, `completed_by`, `completed_at`, or any queue ticket.
6. **No queue creation/reopening:** Do not create or modify `QueueManagement` records.
7. **Archive/settlement blocking:** `can_archive_visit` must reject if any `InvoiceService` line for the visit has `total_price > 0` and the visit aggregate is not fully paid. Enforce per-service itemization (WP-5).
8. **Audit:** Write `AuditTrail` with `entity_type='visit'`, `entity_id=visit_id`, `action='update'`, `description='Added catalog service X after completion'`.

**This reuses `InvoiceService` as the canonical line structure without inventing a new billing architecture.**

---

### Finding 4: Final MC-014 Five-Work-Package Implementation-Readiness Matrix

| WP | Title | Exact Affected Files/Functions/Models | Existing Structures to Reuse | Confirmed Contradiction or Feature Gap | Smallest Safe Remediation Candidate | Required Tests | Rollback Path | Implementation-Ready |
|--|-------|--------------------------------------|------------------------------|----------------------------------------|-------------------------------------|--------------|---------------|----------------------|
| **1** | Catalog service selection and configured pricing | `routes/reception/api.py` `api_department_services` (line 129); `routes/reception/visits.py` `create_visit` (line 272); `models/service.py` `ServiceMaster`; `models/pricing.py` `DoctorPricing`/`PricingCatalog`; `models/pricing_management.py` `PricingManagement` | `ServiceMaster`, `DoctorPricing`, `PricingCatalog`, `PricingManagement`, `api_department_services` dynamic query | None — existing structure complies with confirmed workflow | N/A (no remediation needed; preserve existing behavior and restrict price override) | `test_reception_sees_dynamic_doctor_service_catalog`; `test_reception_sees_dynamic_department_service_catalog`; `test_reception_cannot_override_configured_service_price` | N/A | **Yes** |
| **2** | Controlled custom-service entry, current-visit validity, manager review, and later promotion to reusable catalog service | `routes/reception/visits.py` `_process_custom_services` (line 208); `routes/manager/pricing.py` `update_service_api` (line 126); `models/service.py` `ServiceMaster`; `models/invoice.py` `InvoiceService`; `models/audit_trail.py` `AuditTrail` | `InvoiceService` for current-visit line storage; `AuditTrail` for audit logging (with `entity_type` workaround); existing manager update API for activation | **Direct workflow contradiction:** `_process_custom_services` creates `ServiceMaster` with `is_active=True` immediately, bypassing manager approval | Two-phase approach: (a) create `ServiceMaster` with `is_active=False` (or with new `pending_approval` flag) and write `InvoiceService` line for current visit; (b) manager reviews and activates via existing update API with `AuditTrail` | `test_custom_service_creates_pending_not_active`; `test_custom_service_not_visible_in_future_visit_catalog`; `test_manager_can_approve_custom_service`; `test_audit_trail_records_custom_service_creation_and_approval`; `test_custom_service_invoice_line_preserved_after_deactivation` | Revert `_process_custom_services` to `is_active=True`; remove new columns if added | **No** — requires minimum structural changes before safe implementation |
| **3** | Strict full initial-payment gate before any normal queue entry | `services/queue_management_service.py` `_check_queue_entry_conditions` (line 246); `models/queue_management.py` `QueueSettings`; `routes/reception/visits.py` `add_patient_to_queue_auto` (line 673); `routes/reception/queue.py` `add_patient_to_queue` (line 92); `routes/reception/appointments.py` (lines 120/197) | `QueueSettings` per-department configuration; existing `PaymentStatus` enum; existing test fixtures in `tests/test_queue_management_service.py` | **Direct workflow contradiction:** `PARTIAL` payment enters normal queues when `allow_partial_payment=True` (default). Owner rule requires full payment before any normal queue entry. | Remove `PARTIAL` branch for normal visits in `_check_queue_entry_conditions`; only `PAID` allows normal queue entry; preserve emergency, force-entry, and explicit debt exceptions | `test_normal_visit_partial_payment_blocked_from_all_queues`; `test_normal_visit_paid_enters_queue`; `test_emergency_partial_payment_allowed`; `test_force_entry_partial_payment_allowed`; `test_debt_with_explicit_allow_blocked_by_default`; `test_debt_with_explicit_allow_allowed_when_enabled` | Revert single branch removal | **Yes** |
| **4** | Reception addition of catalog or controlled custom services to completed-but-active visits without reopening clinical status or queue | `routes/reception/visits.py` `edit_visit` (line 1048); `routes/reception/payments.py` `process_payment` (line 54); `models/invoice.py` `Invoice`/`InvoiceService`; `models/visit.py` `Visit`; `services/gatekeeper_service.py` `can_archive_visit` (line 91) | `InvoiceService` as canonical service line; `Invoice` as parent; `Visit.total_amount` as aggregate; `AuditTrail` for logging | **Feature gap:** No backend path exists for reception to append a service to a `COMPLETED` visit without reopening it | New reception route/service: accept `visit_id` + `service_master_id`, validate `COMPLETED` + `ACTIVE` + `financial_locked=False` + `gl_posted_at=None`, load price server-side from `ServiceMaster`, create `InvoiceService` line, increment `visit.total_amount`, update `payment_status`, write `AuditTrail`; no `visit.status` or queue change | `test_reception_can_add_catalog_service_after_treatment_completion`; `test_post_completed_reception_service_addition_does_not_reopen_visit_or_queue`; `test_completed_visit_service_addition_blocked_when_archived`; `test_completed_visit_service_addition_blocked_when_financial_locked`; `test_completed_visit_service_addition_uses_server_side_price` | Remove new route/service | **Yes** — no new models needed; reuses `InvoiceService` |
| **5** | Service-line financial reconciliation, final settlement, and archive blocking | `services/gatekeeper_service.py` `can_archive_visit` (line 91); `services/gatekeeper_service.py` `archive_visit` (line 316); `models/invoice.py` `InvoiceService`; `models/visit.py` `Visit`; `models/payment.py` `Payment` | `InvoiceService` per-line structure; `Visit.total_amount` aggregate; `Payment` transaction records | **Architectural gap:** `can_archive_visit` checks aggregate `visit.total_amount` vs `visit.paid_amount`, not per-service itemization | Enforce per-service itemization: (a) each reception-selected service must have a matching `InvoiceService` line; (b) `visit.total_amount` must equal sum of `InvoiceService.total_price` for the visit; (c) `visit.paid_amount` must cover the full sum before archive; (d) block new service additions after `gl_posted_at` or `archive_status=ARCHIVED` | `test_archive_blocks_when_reception_catalog_services_are_unsettled`; `test_final_settlement_or_archive_blocks_new_service_additions`; `test_per_service_itemization_matches_visit_total_amount`; `test_archive_allows_when_all_invoice_services_fully_paid` | Revert archive check to aggregate-only | **Yes** — reuses existing `InvoiceService` structure; only logic changes in `can_archive_visit` and `process_payment` |

---

### Finding 5: Minimum Structural Gaps That Cannot Be Solved with Existing Structures

The following gaps **cannot** be closed using existing structures alone. They require schema changes (column additions or constraint expansion). No schema changes are proposed or implemented at this stage.

| Gap | Why Existing Structure Is Insufficient | Minimum Structural Change Required | Affected Work Package |
|-----|----------------------------------------|-----------------------------------|----------------------|
| Distinguish custom service from catalog service | `ServiceMaster` has no `is_custom`, `pending_approval`, `approved_by`, `approved_at`, or `created_by` fields. All active services are structurally identical. | Add to `ServiceMaster`: `is_custom` (bool, default=False), `pending_approval` (bool, default=False), `approved_by` (FK→users, nullable), `approved_at` (datetime, nullable), `created_by` (FK→users, nullable) | WP-2 |
| Link invoice line back to source service record | `InvoiceService` stores only `service_code` and `service_name` as strings; no FK to `ServiceMaster`. This prevents tracing which catalog or custom service generated the line. | Add to `InvoiceService`: `service_master_id` (FK→service_master, nullable) | WP-2, WP-4, WP-5 |
| Record who added a financial service line | `InvoiceService` has no `created_by` field. | Add to `InvoiceService`: `created_by` (FK→users, nullable) | WP-4, WP-5 |
| Clean audit-trail entity type for services | `AuditTrail.chk_entity_type` constraint excludes `'service'`. Using `entity_type='system'` is a workaround that loses specificity and queryability. | Expand `AuditTrail` check constraint `chk_entity_type` to include `'service'` | WP-2, WP-4, WP-5 |

**Note:** WP-3 and WP-4 can be implemented without any schema changes. WP-5 can be partially implemented without schema changes by reusing the existing `InvoiceService` structure, but full traceability (linking each line to its source service and creator) requires the column additions above. WP-2 cannot be safely implemented until the `ServiceMaster` flags are added.

---

## H. Decision Log

| Date | Decision | Reason | Superseded By |
|------|----------|--------|---------------|
| 2026-07-01 | Audit initiated | Comprehensive security and workflow audit requested | N/A |
| 2026-07-01 | No implementation approved | Read-only phase only; explicit approval required per ticket | N/A |
| 2026-07-01 | Doctor financial fields claim rejected | Code trace proved no doctor route writes financial fields | N/A |
| 2026-07-01 | `Visit.query.filter_by()` claim corrected | Query objects DO trigger `before_compile`; risk is defense-in-depth, not complete bypass | N/A |
| 2026-07-01 | SystemConfig ownership: platform-global only | **Product requirement confirmed by owner:** `SystemConfig` remains global; no model or constraint changes | N/A |
| 2026-07-01 | Super admin scope: no blanket role-name exemption | **Product requirement confirmed by owner:** no blanket exempt on normal tenant paths; explicit audited tenant-assumption workflow required for cross-tenant access | N/A |
| 2026-07-01 | Return-to-treatment target behavior confirmed | **Product requirement confirmed by owner:** only explicit "return to treatment" action triggers `COMPLETED → OPEN`; queue ticket recreated as `waiting`; `IN_PROGRESS` only when new doctor starts treatment; state machine must not be bypassed | N/A |
| 2026-07-01 | Post-treatment authority: reception is normal operational authority | **Product requirement confirmed by owner:** reception controls return-to-treatment, reassignment, billing handoff, and archiving; doctors/departments/units must not archive or initiate billing; accountants process but do not own workflow; managers do not silently inherit; super admin is separate audited platform function | N/A |
| 2026-07-01 | Tenant mismatch policy: fail closed with 403 | **Product requirement confirmed by owner:** `current_user.tenant_id != g.tenant_id` must abort 403 for ordinary users; no session precedence as authorization control; no fallback | N/A |
| 2026-07-01 | Lab/radiology access: own performing unit or explicit assignment | **Product requirement confirmed by owner:** restricted to own unit or explicitly assigned request; do not use `Visit.department_id` as universal rule | N/A |
| 2026-07-01 | Package/entitlement source of truth | **Product requirement confirmed by owner:** modern package/subscription/entitlement is contractual source of truth; `TenantModule` is runtime projection; `TenantFeatureFlag` is explicit override only; legacy JSON is compatibility-only | N/A |
| 2026-07-01 | No new structures approved at this stage | Subject to verification of QueueManagement data model, state-machine transition contract, existing route/service intent model, and financial closure rules | N/A |
| 2026-07-01 | Administration catalog, dynamic service lists, and reception-only financial authority confirmed | **Product requirement confirmed by owner:** administration maintains all approved chargeable service catalogs and configured prices; each doctor, department, and unit has a configured service list that reception sees dynamically after selecting that doctor, department, or unit; reception alone selects requested services, adds approved catalog services to the visit, and controls all financial entries; a normal visit cannot enter any queue until its initial reception-selected fees are paid and backend-validated; emergency treatment is not blocked by payment; reception may add approved catalog services before final settlement or archive without reopening the clinical visit or queue; all reception-recorded chargeable services must be financially resolved before final settlement or archive; prescriptions and medications are excluded | N/A |
| 2026-07-01 | MC-014 bounded evidence verification completed | Read-only evidence pass confirmed: administration catalog exists (ServiceMaster, DoctorPricing, PricingCatalog, PricingManagement); dynamic service loading confirmed (`api_department_services`); backend queue-entry payment blocking confirmed (`_check_queue_entry_conditions`); emergency exception confirmed (`can_enqueue_visit`, `can_archive_visit`); no visit-level financial writes in doctor/lab/radiology/emergency/nurse routes; `_process_custom_services` confirmed as existing custom-service entry path; **custom-service gaps recorded:** no manager approval workflow, no `is_custom`/`pending_approval` flag, no audit trail, creator only in free-text `description`; **feature gap found:** no backend path for reception to add catalog/custom services to a COMPLETED visit without reopening; **architectural gap found:** archive check uses aggregate `visit.total_amount`, not per-service itemization | N/A |
| 2026-07-02 | MC-014 WP-3 reclassified: PARTIAL queue entry is a direct workflow contradiction | `_check_queue_entry_conditions` line 262 allows `PARTIAL` payment into normal queues when `allow_partial_payment=True` (default per-department). Owner rule requires full initial payment before any normal queue entry. Previously recorded as "no gap" — corrected. | N/A |
| 2026-07-02 | MC-014 WP-2 reclassified: immediate custom-service activation is a direct workflow contradiction | `_process_custom_services` creates `ServiceMaster` with `is_active=True`, making custom services available to all future visits without manager review. Owner rule requires manager approval before promotion to reusable catalog. Previously recorded as "gap" — elevated to direct contradiction. | N/A |
| 2026-07-02 | Canonical financial service-line structure determined | Evidence trace of `ServiceMaster`, `Invoice`, `InvoiceService`, `Payment`, `Receipt`, `Visit` confirms `InvoiceService` is the canonical existing structure for an individual reception-selected service line. No new billing architecture needed. | N/A |
| 2026-07-02 | Minimum structural gaps for WP-2/WP-4/WP-5 recorded | `ServiceMaster` needs `is_custom`, `pending_approval`, `approved_by`, `approved_at`, `created_by`. `InvoiceService` needs `service_master_id`, `created_by`. `AuditTrail` needs `'service'` in `chk_entity_type`. No schema changes implemented. | N/A |
| 2026-07-02 | MC-014 five ordered work packages and implementation-readiness matrix published | WP-1 (ready), WP-2 (blocked on schema), WP-3 (ready), WP-4 (ready), WP-5 (ready). WP-2 requires minimum structural changes before implementation. | N/A |
| 2026-07-01 | RLS table references: 199 declared, not verified | Exact inventory from 5 migration files (`s1_002`, `s1_004`, `s1_005`, `s1_006`, `s1_007`); runtime enforcement still requires verification | N/A |
| 2026-07-01 | Finding count corrected | Register has 17 items (B-001 through B-017); B-013 rejected; active: 12 Candidate, 1 Verified fail-open, 2 Resolved, 1 Rejected, 1 Awaiting product decision | N/A |
| 2026-07-01 | Evidence labels corrected | "Confirmed by code and isolated runtime evidence" softened to "Confirmed by code; isolated runtime verification pending" where no named test or command was documented | N/A |
| 2026-07-01 | B-014 reclassified as technical verification | No longer requires product-owner decision; requires complete inventory of background tasks per F.3 | N/A |
| 2026-07-01 | Ticket dependencies decoupled | MC-004 no longer depends on MC-002; MC-009 no longer depends on MC-002 or MC-003; dependencies now reflect only true technical blockers | N/A |
| 2026-07-01 | Unresolved decisions expanded | Added 5 authority questions from Authority Matrix with "Default deny until explicitly approved" principle | N/A |
| 2026-07-01 | B-017 added: post-queue service addition | Doctor routes add lab/radiology/prescriptions mid-visit (only `IN_PROGRESS`) but do not update financial totals or archive eligibility | N/A |
| 2026-07-01 | B-003 corrected | Original emergency claim corrected; reclassified as technical hardening candidate, not confirmed cross-tenant vulnerability | N/A |
| 2026-07-01 | B-005 severity refined | Code defect verified but reachability test required before P0 exposure classification | N/A |
| 2026-07-01 | MC-006 refined | Per-endpoint classification required before blanket module guard application | N/A |
| 2026-07-01 | MC-008 corrected | Discovery-first approach; `performing_unit_id` removed from proposal unless audit proves it already exists | N/A |
| 2026-07-01 | MC-009 extended | Clinical record and order integrity checks added (MedicalRecord, prescriptions, lab/radiology requests, diagnoses, completed metadata, state machine safeguards) | N/A |
| 2026-07-01 | RLS verification method corrected | Replaced incorrect `ALTER ROLE ... SET row_level_security = on` with proper 8-point verification (BYPASSRLS, table ownership, relrowsecurity, relforcerowsecurity, row_security_active, two-tenant tests, policy definitions) | N/A |
| 2026-07-01 | Dependencies corrected | MC-005 → None; MC-002 → MC-005; MC-006 → MC-010 or temp rule; MC-007 → platform boundary; MC-008 → field inventory | N/A |

---

## I. Unresolved Decisions Requiring Your Confirmation

The following owner decisions have been **recorded as confirmed product requirements** in this plan update. The remaining items below are those that still genuinely require your explicit input before they can be resolved:

1. **Explicit tenant-assumption workflow for platform users (MC-005 / MC-007 follow-up):** The direction is confirmed (no blanket bypass, explicit audited workflow required), but the actual workflow design — UI, API path, audit fields, approval chain — has not been designed or approved. This is a future design issue, not a code-change blocker.

2. **Audit logging for cross-tenant operations:** Should `AuditTrail` include `from_tenant_id` and `to_tenant_id` for tenant switches? Current `AuditTrail` does not log tenant context. This is a future enhancement decision.

3. **Optional UX enhancement — B-016 / MC-013:** Is a dedicated "completed awaiting closure" reception dashboard/filter required, or is the existing visits list + status filter sufficient? This does not block security or functional fixes.

4. **Initial creation logging (D-GAP-02):** Should `VisitTransferLog` be created on initial visit creation ("created by reception, assigned to Doctor A"), or is transfer-only logging sufficient?

5. **Queue ticket state on transfer (D-GAP-04):** If a queue ticket was `completed` (not `waiting`) at the time of transfer, what is the correct behavior? This depends on whether completed visits retain queue tickets.

6. **Manager visit visibility scope:** Should a manager see all tenant visits or only visits within an approved management scope (e.g., their department, their direct reports)? **Default deny until explicitly approved.**

7. **Platform super admin on normal tenant paths:** Can a platform super admin create, assign, transfer, complete, archive, or bill visits on normal tenant paths (e.g., `/reception/visits`, `/doctor/queue`)? **Default deny until explicitly approved.**

8. **Reception payment processing authority:** May reception process a payment directly, or only initiate a billing handoff to accounting? **Default deny until explicitly approved.**

9. **Doctor historical visit access:** Should doctors have read-only access to their completed historical visits for continuity of care? **Default deny until explicitly approved.**

10. **Emergency staff case scope:** Should emergency staff work on all emergency cases in the tenant, or only assigned emergency unit cases? **Default deny until explicitly approved.**

11. ~~Post-queue service addition and financial settlement (B-017 / MC-014)~~ — **Resolved as confirmed product requirement:** administration maintains all approved chargeable service catalogs and configured prices; each doctor, department, and unit has a configured service list that reception sees dynamically after selecting that doctor, department, or unit; reception alone selects requested services, adds approved catalog services to the visit, and controls all financial entries; a normal visit cannot enter any queue until its initial reception-selected fees are paid and backend-validated; emergency treatment is not blocked by payment; reception may add approved catalog services before final settlement or archive without reopening the clinical visit or queue; all reception-recorded chargeable services must be financially resolved before final settlement or archive; prescriptions and medications are excluded. The remaining technical audit is documented in MC-014 verification tasks.

---

**End of Plan. No implementation approved. Awaiting explicit ticket-by-ticket approval.**

**Change log for this update:**
1. **B-017 added:** Post-queue service addition and financial settlement. Doctor routes add lab/radiology/prescriptions mid-visit (only while `IN_PROGRESS`) but do not update `visit.total_amount`, `InvoiceItem`, `Payment`, or `Receipt` totals. `GatekeeperService.can_archive_visit()` does not recalculate for post-creation services. No services can be added after `COMPLETED`. Finding count updated to 17.
2. **A-06 corrected:** Changed from "Technically verified" to "Partially verified — services are added during visit creation; post-queue service addition and financial settlement behavior require technical verification."
3. **B-003 corrected:** Original claim that emergency routes are completely tenant-unscoped is corrected/disproven when valid tenant context exists. Reclassified as "Technical hardening candidate; isolated runtime verification pending." Not classified as confirmed cross-tenant vulnerability unless two-tenant runtime test proves it.
4. **B-005 severity refined:** Changed from "Confirmed by code; isolated runtime verification pending" to "Verified fail-open code path; runtime reachability and exposure impact pending." Added mandatory reachability test before P0 exposure classification (SaaS mode, protected route, missing tenant context, full middleware chain).
5. **MC-006 refined:** Removed blanket `@require_module(...)` proposal. Added mandatory per-endpoint classification: public auth/bootstrap, platform admin, tenant shared, module-specific read/write, callback/webhook. Only module-specific operations may receive enforcement.
6. **MC-008 corrected:** Removed `performing_unit_id` proposal. Changed to discovery-first: inventory existing fields on `LabRequest`, `RadiologyRequest`, queue, departments, branches, users, assignments; use existing data if possible; only record design gap if no existing boundary exists.
7. **F.3 inventory corrected:** Removed hypothetical `tasks/lab_tasks.py`, `tasks/radiology_tasks.py`. Replaced with "Lab/radiology asynchronous workflow — repository-wide task inventory required." Added explicit treatment-completion notification verification (recipient query, tenant context, cross-tenant risk).
8. **MC-009 extended:** Added 6 clinical record and order integrity checks: MedicalRecord immutability/versioning, clinical record overwrite risk, order linkage after reopening, outstanding/completed order linkage, completion metadata preservation (`completed_by`/`completed_at`), state machine `COMPLETED → OPEN` safeguard.
9. **RLS verification method corrected:** Replaced incorrect `ALTER ROLE ... SET row_level_security = on` with proper 8-point verification: application role and memberships, BYPASSRLS check, table ownership, `relrowsecurity`/`relforcerowsecurity`, `row_security_active()`, two-tenant read/write/delete tests, policy `USING`/`WITH CHECK`, migration state and active policies.
10. **Ticket dependencies corrected:** MC-005 → None (tenant-security foundation). MC-002 → MC-005 (or equivalent verified tenant-context invariant). MC-006 → MC-010 or documented temporary rule. MC-007 → precise platform-path boundary, not merely MC-001. MC-008 → field inventory, not MC-003. MC-009 dependencies unchanged (state-machine, queue, financial, route-intent, clinical-record reviews).
11. **Authority defaults maintained:** All unresolved authority questions continue to use "Default deny until explicitly approved." No permission changes implemented without explicit ticket approval.
13. **B-017 corrected:** Removed prescriptions and medications from financial assumptions. Confirmed owner requirement: clinical departments report services; reception records costs; prescriptions are clinical-only; normal visits require initial payment before queue entry; emergency exempt; post-queue charges must be settled before closure.
14. **MC-014 corrected:** Renamed to "Reception-Controlled Post-Queue Service Charging and Closure Reconciliation." Priority set to P1 — confirmed financial-integrity requirement. Removed prescriptions/pharmacy from scope. Removed B-001 and B-002 as automatic dependencies. Added technical discovery table and 10 verification tasks. Added required tests.
15. **Decision Log updated:** Added "Reception-only financial authority confirmed" as product requirement.
16. **Unresolved Decisions updated:** Removed item 11 (post-queue service addition) as resolved; marked as confirmed product requirement with remaining technical audit in MC-014.
17. **B-017 superseded (Update 5):** Replaced with exact owner requirement: administration predefines approved service catalog and prices; reception selects from catalog at visit entry; departments report clinical services only; reception alone controls costs using approved catalog; normal visits require initial payment before queue entry; emergency not blocked by payment; all reception-recorded charges settled before closure; prescriptions excluded.
18. **MC-014 renamed (Update 5):** "Reception-Controlled Visit Service Charging, Queue-Entry Payment, and Closure Reconciliation." Priority P1 — confirmed financial and workflow integrity requirement. Added administration catalog to scope. Updated discovery table and verification tasks (11 items). Dependencies: only when audited path uses unsafe tenant/ownership access.
19. **A-06 updated (Update 5):** Added administration catalog ownership to confirmed product requirement.
20. **Decision Log updated (Update 5):** Replaced "Reception-only financial authority confirmed" with "Administration catalog and reception-only financial authority confirmed."
21. **B-017 superseded (Update 6):** Exact owner requirement: administration maintains all approved chargeable service catalogs and configured prices; each doctor, department, and unit has a configured service list that reception sees dynamically; reception alone selects requested services, adds approved catalog services, and controls all financial entries; normal visits cannot enter any queue until initial fees are paid and backend-validated; emergency not blocked by payment; reception may add catalog services before final settlement without reopening clinical visit or queue; all reception-recorded charges resolved before final settlement or archive; prescriptions excluded.
22. **MC-014 renamed (Update 6):** "Administration Catalog, Reception Service Selection, Initial Queue Payment, and Final Reconciliation." Priority P1 — confirmed financial and workflow integrity requirement. Updated scope to include dynamic service lists and initial queue-entry payment enforcement. Updated technical discovery table. Replaced verification tasks with 11 exact checks. Replaced tests with 10 exact tests.
23. **A-06 updated (Update 6):** Added administration catalog ownership, dynamic service lists, reception-only service selection, initial queue-entry payment rule, post-completion catalog addition without reopening.
24. **Authority Matrix updated (Update 6):** Added rows for "Select chargeable services from approved catalog," "Enter queue — normal visit," "Enter queue — emergency," and "Add approved catalog service to active or completed visit."
25. **Queue workflow trace updated (Update 6):** Added steps for administration catalog, reception service selection, initial payment validation, emergency bypass, post-completion catalog addition without reopening. Updated gaps and conclusion.
26. **Decision Log updated (Update 6):** Replaced with "Administration catalog, dynamic service lists, and reception-only financial authority confirmed."
27. **Unresolved Decisions updated (Update 6):** Item 11 updated to match exact owner requirement wording.
28. **MC-014 bounded evidence verification completed (Update 7):** Read-only evidence pass confirmed administration catalog (`ServiceMaster`, `DoctorPricing`, `PricingCatalog`, `PricingManagement`); dynamic service loading (`api_department_services`); backend queue-entry payment blocking (`_check_queue_entry_conditions`); emergency exception (`can_enqueue_visit`, `can_archive_visit`); no visit-level financial writes in doctor/lab/radiology/emergency/nurse routes. **Feature gap found:** no backend path for reception to add catalog services to a `COMPLETED` visit without reopening. **Architectural gap found:** archive check uses aggregate `visit.total_amount`, not per-service itemization. Added six-row evidence matrix to plan.
29. **Custom service entry confirmed as approved exception (Update 8):** `_process_custom_services` reclassified from "direct contradiction" to "approved reception-controlled exception for services not yet in catalog." B-017 and A-06 amended to include custom service entry. MC-014 renamed scope to include catalog + custom services. Five work packages defined (WP-1 through WP-5). Bounded technical verification item added for custom-service entry and manager approval/promotion — 8 capabilities inventoried, 4 gaps recorded without proposing new structures. Decision Log updated. Evidence matrix row 2 corrected.
30. **MC-014 WP-3 corrected (Update 9):** `_check_queue_entry_conditions` `PARTIAL` branch reclassified from "no gap" to **direct workflow contradiction**. Evidence: line 262 allows `PARTIAL` + `allow_partial_payment=True` (default per-department) into all normal queues. Owner rule requires full payment before any normal queue entry. Queue-entry paths audited: `add_patient_to_queue_auto` (visit creation), `add_patient_to_queue` (manual), appointment queue entry. Smallest safe change: remove `PARTIAL` branch for normal visits; only `PAID` allows entry. Emergency and force-entry preserved.
31. **MC-014 WP-2 corrected (Update 9):** `_process_custom_services` immediate `is_active=True` reclassified from "gap" to **direct workflow contradiction**. Evidence: line 242 creates `ServiceMaster` with `is_active=True`, making custom service available to all future visits via `api_department_services` without manager review. Owner rule requires manager approval before promotion to reusable catalog. Bounded technical design audit performed: `is_active=False` proven safe for current-visit billing (InvoiceService stores strings) and historical visibility; manager can activate via existing API; but existing models are insufficient to distinguish custom/pending/approved services. Minimum structural changes recorded.
32. **Canonical financial service-line structure determined (Update 9):** Evidence trace of `ServiceMaster` → `Invoice` → `InvoiceService` → `Payment` → `Receipt` → `Visit.total_amount` confirms `InvoiceService` is the canonical existing structure for an individual reception-selected service line. No new billing architecture needed. WP-4 design uses `InvoiceService` for completed-visit service addition.
33. **Minimum structural gaps recorded (Update 9):** `ServiceMaster` needs `is_custom`, `pending_approval`, `approved_by`, `approved_at`, `created_by`. `InvoiceService` needs `service_master_id`, `created_by`. `AuditTrail` `chk_entity_type` needs `'service'`. No schema changes implemented.
34. **MC-014 five ordered work packages published with implementation-readiness matrix (Update 9):** WP-1 (ready, no remediation needed), WP-2 (blocked on schema), WP-3 (ready, single branch removal), WP-4 (ready, reuses `InvoiceService`), WP-5 (ready, logic changes only). Added to section G.2.
