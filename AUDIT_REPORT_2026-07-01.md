# Medical Centre — Comprehensive Security & Workflow Audit Report

**Date:** 2026-07-01  
**Scope:** Visit workflow, tenant isolation, module entitlement, authorization boundaries  
**Method:** Read-only code trace (Models → Enums → Services → Routes → Decorators → Middleware → Database)

---

## A. Executive Verdict

| Major Requirement | Verdict |
|---|---|
| **1. Visit creation by reception** | 🟡 Partially implemented — `tenant_id` is NOT explicitly set; relies on ORM auto-assign hook |
| **2. Transfer to doctor/department** | ✅ Fully implemented — `QueueManagementService.transfer_visit()` with `VisitTransferLog` |
| **3. Restrict visit visibility to assigned doctor/department** | 🟡 Partially implemented — Doctor routes enforce `doctor_id + tenant_id`, but reception/emergency/lab/radiology routes do NOT consistently enforce department/doctor scoping |
| **4. Reception monitoring after assignment** | ✅ Fully implemented — Reception can view all visits via `Visit.query` (no doctor filter), but this also means reception sees cross-tenant visits if tenant filter fails |
| **5. Treatment completion without auto-archive** | ✅ Fully implemented — `VisitStateMachineService` ends at `COMPLETED`; `archive_status` is separate |
| **6. Return to reception workflow** | 🟡 Partially implemented — `transfer_visit` can move visit back, but no dedicated "return to reception" state or workflow exists |
| **7. Doctor/department cannot archive** | ✅ Fully implemented — `can_archive_visits` decorator limits to `reception`, `manager`; doctors are blocked |
| **8. Doctor/department cannot transfer to billing** | ⚠️ Exists but unsafe — No explicit billing-transfer route for doctors; billing is handled by `accountant` role, but the finance route (`routes/finance.py`) does not verify visit ownership before calling `GatekeeperService` |
| **9. Reception authority for reassignment, archive, billing** | 🟡 Partially implemented — Archive/reassignment have role checks, but billing route does not verify visit belongs to current tenant |
| **10. Assignment history and state history** | ✅ Fully implemented — `VisitTransferLog` and `VisitWorkflowEvent` exist and are populated |
| **11. Tenant isolation for visits** | ⚠️ Exists but unsafe — ORM hooks + RLS on 11 tables provide baseline, but many routes bypass with `db.session.get()` |
| **12. Package/module enforcement** | ❌ Not implemented — Only 8 of 52 blueprints use `guard_module`; 44+ blueprints have no module entitlement check |
| **13. Cross-tenant data leakage prevention** | ⚠️ Exists but unsafe — No `current_user.tenant_id == g.tenant_id` validation; `_tenant_filter_bypass` disables all isolation |
| **14. Backend enforcement (not just UI)** | 🟡 Partially implemented — `guard_module` aborts 403 for protected blueprints, but most blueprints lack it |

---

## B. Visit Workflow Audit Table

| Requirement | Status | Actual Evidence | File Path / Function / Line | Risk or Missing Part |
|---|---|---|---|---|
| **Visit creation by reception** | 🟡 Partially implemented | `Visit` object created with `patient_id`, `department_id`, `doctor_id`, `status='OPEN'` but **no explicit `tenant_id`** | `routes/reception/visits.py::create_visit()` lines 451-466 | `tenant_id` relies on `before_flush` ORM hook. If hook fails or `g.tenant_id` is None, visit is created with `tenant_id=NULL` |
| **Transfer to specific doctor** | ✅ Implemented | `QueueManagementService.transfer_visit()` updates `visit.doctor_id` and logs to `VisitTransferLog` | `services/queue_management_service.py::transfer_visit()` lines 182-244 | Validates doctor required for `general` departments |
| **Transfer to department/unit** | ✅ Implemented | Same `transfer_visit()` updates `visit.department_id` | `services/queue_management_service.py::transfer_visit()` lines 218-221 | Validates department existence via `get_tenant_record` |
| **Restrict visit visibility to assigned doctor** | 🟡 Partially implemented | Doctor routes filter by `Visit.doctor_id == current_user.id AND Visit.tenant_id == g.tenant_id` | `routes/doctor/__init__.py` and all doctor visit routes | Consistent for doctor routes. BUT reception, emergency, lab FHIR, and payment routes do NOT enforce doctor scoping |
| **Restrict visit visibility to assigned department** | ❌ Not implemented | No route checks `visit.department_id == current_user.department_id` for department-scoped access | N/A — not found in any route | A lab tech can access any lab request from any department within the same tenant |
| **Reception monitoring after assignment** | ✅ Implemented | Reception `visits` list uses `Visit.query.order_by(...)` without doctor filter | `routes/reception/visits.py::visits()` line ~37 | **Also a risk:** if tenant filter fails, reception sees cross-tenant visits |
| **Treatment completion (doctor end-treatment)** | ✅ Implemented | Doctor `end_treatment` calls `VisitStateMachineService.ensure_completed()` and updates queue ticket | `routes/doctor/patient_queue.py::end_treatment()` | Validates `visit.doctor_id == current_user.id` |
| **Return to reception without auto-archive** | ✅ Implemented | `COMPLETED` is terminal clinical state; `archive_status` remains `ACTIVE` | `services/visit_state_machine_service.py` lines 35-44 | Archive is a separate administrative action |
| **Doctor cannot archive** | ✅ Implemented | `can_archive_visits` decorator allows only `['reception', 'manager']` | `utils/decorators.py::can_archive_visits()` lines 306-323 | Doctors receive 403 |
| **Doctor cannot transfer to billing** | ⚠️ Exists but unsafe | No explicit "transfer to billing" route for doctors exists; billing is handled by `accountant` role | `routes/finance.py`, `routes/payment_routes.py` | However, doctors can set `payment_method` and `total_amount` during visit creation/editing |
| **Reception can reassign** | ✅ Implemented | `transfer_visit` route allows reception to change doctor/department | `routes/reception/visits.py::transfer_visit()` lines 187-206 | No check that visit is currently assigned to the same tenant (mitigated by `get_tenant_record` in service) |
| **Reception can archive** | ✅ Implemented | `archive_visit` route with role check | `routes/reception/visits.py::archive_visit()` lines 87-107 | Calls `GatekeeperService.archive_visit()` which validates financial completion |
| **Reception can send to billing** | 🟡 Partially implemented | `process_payment` route exists for reception/accountant | `routes/reception/payments.py`, `routes/payment_routes.py` | **IDOR risk:** uses `db.session.get(Visit, visit_id)` without tenant filter |
| **Assignment history** | ✅ Implemented | `VisitTransferLog` records `from_department_id`, `to_department_id`, `from_doctor_id`, `to_doctor_id`, `transferred_by`, `source` | `models/visit_transfer.py::VisitTransferLog` | Populated by `transfer_visit()` |
| **State transition history** | ✅ Implemented | `VisitWorkflowEvent` records `from_status`, `to_status`, `performed_by`, `notes` | `models/workflow.py::VisitWorkflowEvent` lines 299-313 | Populated by `VisitStateMachineService.transition()` |
| **Tenant isolation during visit access** | ⚠️ Exists but unsafe | `TenantMixin` + `tenant_filter.py` ORM hooks provide baseline, but many routes use `db.session.get(Visit, id)` which bypasses the auto-filter | `app/shared/tenant_filter.py` lines 99-139 | **P0:** `db.session.get()` does not trigger `before_compile`; 20+ routes in reception, emergency, lab, radiology, and billing use naked `db.session.get(Visit, id)` |

---

## C. SaaS, Tenant, Package, and Module Audit Table

| Requirement | Status | Actual Evidence | File Path / Function / Line | Risk or Missing Part |
|---|---|---|---|---|
| **Tenant isolation (application-level)** | 🟡 Partially implemented | `TenantFilter` event listeners inject `tenant_id` into every `SELECT/UPDATE/DELETE` on `TenantMixin` models | `app/shared/tenant_filter.py::before_compile()` lines 99-139 | **Single point of failure.** If listener fails or `_tenant_filter_bypass` is set, queries leak across tenants |
| **Tenant isolation (database-level RLS)** | 🟡 Partially implemented | PostgreSQL RLS policies exist on 11 tables only | `migrations/versions/s1_002_tenant_rls_policies.py` lines 14-38 | 40+ tenant-scoped tables have NO RLS policy |
| **Package/subscription structure** | ✅ Implemented (dual system) | Legacy: `SubscriptionPlan.modules_included` (JSON); Modern: `PackageVersion` → `SubscriptionLine` → `EntitlementGrant` → `TenantEntitlement` | `app/core/tenant/models.py` lines 123-141, `app/core/saas/models.py` lines 71-593 | Two sources of truth increase drift risk |
| **Module entitlement structure** | ✅ Implemented | `TenantModule` table links tenants to enabled modules; `FeatureGateService.module_enabled()` queries it | `app/core/saas/models.py::TenantModule` | **Not automatically synced** with subscription changes |
| **Link package → tenant modules** | 🟡 Partially implemented | `LegacyEntitlementAdapter` bridges legacy `SubscriptionPlan` to `TenantModule`; modern `EntitlementResolver` is read-only projection | `app/core/saas/legacy_adapter.py` | Changes to `SubscriptionLine` do NOT auto-update `TenantModule` rows |
| **Route-level module protection** | ❌ Not implemented (majority) | Only 8 of 52 blueprints register `guard_module`; 44+ have no module check | `routes/*/__init__.py` files | A tenant on "independent clinic" plan can access lab, radiology, emergency, AI imaging, OR management, etc. if they have a user with the right role |
| **Service-level module protection** | ❌ Not implemented | No service method checks `FeatureGateService.module_enabled()` before executing | All service files checked | Services assume the route already gated; no defense-in-depth |
| **API-level module protection** | ❌ Not implemented | API blueprints (FHIR, HL7) have no `guard_module` | `routes/lab/fhir.py`, `routes/radiology/fhir.py` | Any authenticated user can hit FHIR endpoints for disabled modules |
| **UI-level visibility control** | 🟡 Partially implemented | Templates use `module_active()` checks for menu items | `templates/*/base.html` | **Not security — pure UX.** Backend must block, not just hide buttons |
| **Direct URL bypass prevention** | ❌ Not implemented (majority) | 44+ blueprints lack `guard_module`; role checks alone do not enforce licensing | `routes/manager/__init__.py`, `routes/ai_imaging_routes.py`, etc. | Tenant can access any route by URL if they create a user with a matching role |
| **API bypass prevention** | ❌ Not implemented | Same gap — API endpoints in unguarded blueprints | `routes/patient_portal.py`, `routes/telemedicine_routes.py` | No module gate |
| **Cross-tenant data leakage prevention** | ⚠️ Exists but unsafe | `current_user.tenant_id` is **never validated against `g.tenant_id`** | Entire codebase — no match found for `current_user.tenant_id == g.tenant_id` | A user from Tenant A could (in theory) manipulate session to access `/t/tenant-b/...` |
| **Separation of Role, Department, Module, Tenant** | ❌ Not implemented | Role hierarchy (`ROLE_HIERARCHY` in decorators) is the primary access control. No orthogonal check for department assignment or module entitlement | `utils/decorators.py::ROLE_HIERARCHY` lines 72-78 | A doctor in Department A (cardiology) can access visits assigned to Department B (orthopedics) if both are "general" type, because routes only check `role == 'doctor'` |

---

## D. Current Real Execution Flow

### D1. Reception Creates a Visit
1. **Route:** `POST /reception/visits/create` → `routes/reception/visits.py::create_visit()` (line 272)
2. **Authorization:** `@login_required` + `@can_create_visits` (checks `current_user.role == 'reception'`)
3. **Service:** No service layer; route builds `Visit` object directly
4. **Model:** `Visit(patient_id=..., department_id=..., doctor_id=..., status='OPEN', created_by=current_user.id)` — **no `tenant_id` explicitly set** (line 451-466)
5. **Database:** `before_flush` hook in `tenant_filter.py` auto-assigns `tenant_id = g.tenant_id` if NULL
6. **Result:** Visit created. If hook fails, `tenant_id = NULL` → globally visible

### D2. Reception Transfers Visit to Doctor/Department
1. **Route:** `POST /reception/visits/<id>/transfer` → `routes/reception/visits.py::transfer_visit()` (line 190)
2. **Authorization:** Manual role check `current_user.role in ['reception', 'super_admin']`
3. **Service:** `QueueManagementService().transfer_visit(visit_id, new_department_id, new_doctor_id)` (line 196)
4. **Model:** Updates `visit.department_id` and `visit.doctor_id`; creates `VisitTransferLog` record
5. **Database:** `get_tenant_record(Visit, visit_id)` ensures visit exists in current tenant
6. **Result:** Visit reassigned. Queue ticket updated if status is `waiting`.

### D3. Doctor Accesses Visit
1. **Route:** `GET /doctor/patient-details/<visit_id>` → `routes/doctor/patient_queue.py::patient_details()`
2. **Authorization:** `@login_required` + `@role_required('doctor','admin','manager')`
3. **Service:** None directly; route queries visit
4. **Model:** `Visit.query.filter(Visit.id == visit_id, Visit.tenant_id == g.tenant_id, Visit.doctor_id == current_user.id).first_or_404()`
5. **Result:** **Blocked if visit is not assigned to this doctor.** This is the most secure path.

### D4. Doctor Completes Treatment
1. **Route:** `POST /doctor/end-treatment/<visit_id>` → `routes/doctor/patient_queue.py::end_treatment()`
2. **Authorization:** `@role_required('doctor','admin','manager')`
3. **Service:** `VisitStateMachineService.ensure_completed(visit)` + queue ticket completion
4. **Model:** `visit.status` transitions to `COMPLETED` via VSM (validated)
5. **Result:** Visit clinically complete. `archive_status` remains `ACTIVE`.

### D5. Reception Archives Visit
1. **Route:** `POST /reception/visits/<id>/archive` → `routes/reception/visits.py::archive_visit()` (line 89)
2. **Authorization:** Manual role check `current_user.role in ['reception', 'super_admin']`
3. **Service:** `GatekeeperService.archive_visit(visit_id, current_user.id)` (line 98)
4. **Model:** Validates `gl_posted_at`, `financial_locked`, then sets `archive_status = 'ARCHIVED'`
5. **Database:** `get_tenant_record(Visit, visit_id)` inside service
6. **Result:** Visit archived. **Route itself does NOT tenant-scope the initial lookup.**

### D6. Accountant Processes Billing
1. **Route:** `POST /finance/post` or `POST /payment/process/<visit_id>`
2. **Authorization:** `@role_required('accountant')` or manual role check
3. **Service:** `GatekeeperService.post_gl()` or `GatekeeperService.create_system_receipt()`
4. **Model:** Updates `visit.gl_posted_at` or `visit.receipt_printed`
5. **Result:** **No visit ownership validation before service call.** Any accountant can archive/bill any visit by ID.

---

## E. Security and Workflow Risks

### P0 — Critical (Cross-tenant leakage, unauthorized access, bypass)

| # | Issue | Evidence | Impact | Confirmed/Suspected |
|---|---|---|---|---|
| **P0-001** | `db.session.get(Visit, id)` in 20+ routes bypasses tenant filter | `routes/reception/visits.py` lines 93, 116; `routes/emergency/*.py` multiple locations; `routes/reception/payments.py`; `routes/payment_routes.py` | Any authenticated user with a valid role can access/modify any visit across all tenants by changing the numeric ID | **Confirmed** |
| **P0-002** | `SystemConfig` table is skipped by tenant filter | `app/shared/tenant_filter.py` lines 60-67; `models/system_config.py` line 17 | Any tenant can read any system config (including templates, pricing rules, notification settings) belonging to other tenants | **Confirmed** |
| **P0-003** | No `current_user.tenant_id == g.tenant_id` validation anywhere | Entire codebase — grep returns zero matches | Session hijacking or slug manipulation could allow cross-tenant access | **Confirmed** |
| **P0-004** | `guard_module` silently passes if `g.current_tenant` is missing | `services/feature_gate_service.py` lines 68-70 | Internal redirects or bypass paths could expose guarded blueprints | **Suspected** |
| **P0-005** | Visit created without explicit `tenant_id` | `routes/reception/visits.py::create_visit()` lines 451-466 | If `before_flush` hook fails, visit is created with `tenant_id=NULL` and becomes globally visible | **Confirmed** |

### P1 — High (Incorrect authority, workflow violation)

| # | Issue | Evidence | Impact | Confirmed/Suspected |
|---|---|---|---|---|
| **P1-001** | Reception `archive_visit` and `end_visit` routes do not tenant-scope visit lookup | `routes/reception/visits.py` lines 93, 116 | Reception in Tenant A can archive a visit from Tenant B if they guess the ID | **Confirmed** |
| **P1-002** | Emergency routes do not enforce doctor/department scoping | `routes/emergency/*.py` — all visit lookups use `Visit.query.filter_by(id=visit_id).first()` | Emergency staff can access any emergency visit regardless of department assignment | **Confirmed** |
| **P1-003** | Lab/Radiology FHIR endpoints accept arbitrary `visit_id` without ownership validation | `routes/lab/fhir.py`, `routes/radiology/fhir.py` | Lab tech can create lab requests for visits not assigned to their department | **Confirmed** |
| **P1-004** | `_is_user_allowed_for_department` does not validate that the visit belongs to the department | `services/queue_management_service.py` lines 56-82 | A doctor from Dept A can start treatment on a ticket whose visit is assigned to Dept B if they share the same role | **Suspected** |
| **P1-005** | `can_archive_visits` decorator allows `reception` role, but the route also allows `super_admin` — no role hierarchy check for archive | `utils/decorators.py::can_archive_visits()` lines 316-317 vs `routes/reception/visits.py::archive_visit()` lines 90-91 | Inconsistent authorization logic between decorator and route | **Confirmed** |

### P2 — Medium (Incomplete workflow, missing audit)

| # | Issue | Evidence | Impact | Confirmed/Suspected |
|---|---|---|---|---|
| **P2-001** | No dedicated "return to reception" workflow state | `VisitStateMachineService.TRANSITIONS` — `COMPLETED` has no outgoing transitions | After doctor completes treatment, reception must manually transfer the visit back; no automatic queue notification | **Confirmed** |
| **P2-002** | `VisitWorkflowEvent` logs state transitions but does NOT log transfers | `models/workflow.py::VisitWorkflowEvent` — only `from_status`, `to_status` | `VisitTransferLog` records transfers, but there is no unified timeline combining state + transfer + billing events | **Confirmed** |
| **P2-003** | Doctor `call_patient` uses `db.session.get(Visit, id)` before doctor check | `routes/doctor/patient_queue.py::call_patient()` | Doctor could trigger `db.session.get` on cross-tenant visit (mitigated by subsequent `doctor_id` check, but still leaks existence) | **Confirmed** |
| **P2-004** | `Patient.query.all()` used in reception visit creation | `routes/reception/visits.py::create_visit()` | Patient dropdown is not tenant-scoped (ORM hook mitigates, but explicit filtering is missing) | **Confirmed** |

### P3 — Low (UI, usability, non-security)

| # | Issue | Evidence | Impact | Confirmed/Suspected |
|---|---|---|---|---|
| **P3-001** | 44+ blueprints lack `guard_module` — no backend module enforcement | Grep of `__init__.py` files | Tenant on basic plan can access advanced modules by direct URL if they have a user with matching role | **Confirmed** |
| **P3-002** | `require_entitlement` decorator exists but is used in only 1 route | `app/core/saas/decorators.py` lines 27-56; only used in `routes/lab/dashboard.py` line 38 | Modern entitlement system is largely unenforced at route level | **Confirmed** |
| **P3-003** | `ROLE_HIERARCHY` conflates managerial access with clinical access | `utils/decorators.py` lines 72-78 | `manager` inherits `reception` and `accountant`, but not `doctor` or `lab` — partially correct but not granular enough for department-level separation | **Confirmed** |

---

## F. Proposed Implementation Plan — No Execution Yet

### Ticket F-001: Uniform Tenant-Scoped Visit Lookup (P0)
**Priority:** P0  
**Issue:** `db.session.get(Visit, id)` and `Visit.query.filter_by(id=id)` bypass tenant filters in 20+ routes.  
**Current implementation:** Doctor routes already use `Visit.query.filter(Visit.id == id, Visit.tenant_id == g.tenant_id, Visit.doctor_id == current_user.id).first_or_404()`.  
**Why insufficient:** Reception, emergency, billing, lab FHIR, and payment routes use naked lookups.  
**New Model/State/Route needed?** No.  
**Smallest safe change:** Replace all naked visit lookups with `get_tenant_record(Visit, visit_id)` or `Visit.query.filter(Visit.id == visit_id, Visit.tenant_id == g.tenant_id).first_or_404()`.  
**Affected files:** `routes/reception/visits.py`, `routes/reception/payments.py`, `routes/reception/api.py`, `routes/emergency/*.py`, `routes/payment_routes.py`, `routes/finance.py`, `routes/lab/fhir.py`, `routes/radiology/fhir.py`, `routes/doctor/patient_queue.py::call_patient()`.  
**Database impact:** None.  
**Backward compatibility:** Fully backward-compatible.  
**Rollback:** Revert the specific line changes.  
**Tests:** Verify `test_tenant_route_isolation.py` and add tests for each patched route.  
**Commit boundary:** One commit per route file, or one commit for all reception routes.

### Ticket F-002: Explicit `tenant_id` on Visit Creation (P0)
**Priority:** P0  
**Issue:** `create_visit()` and `create_emergency_case()` do not set `tenant_id` on the `Visit` model.  
**Current implementation:** Relies on `before_flush` hook in `tenant_filter.py`.  
**Why insufficient:** If hook fails or `g.tenant_id` is None, visit gets `tenant_id=NULL`.  
**New Model/State/Route needed?** No.  
**Smallest safe change:** Add `tenant_id=getattr(current_user, 'tenant_id', None) or getattr(g, 'tenant_id', None)` to `Visit(...)` constructor in both routes.  
**Affected files:** `routes/reception/visits.py::create_visit()`, `routes/emergency/cases.py::create_emergency_case()`.  
**Database impact:** None (column already exists).  
**Backward compatibility:** Fully compatible.  
**Rollback:** Remove the explicit parameter.  
**Tests:** Add test that created visit has correct `tenant_id`.  
**Commit boundary:** One commit.

### Ticket F-003: Add `guard_module` to All Blueprints (P1)
**Priority:** P1  
**Issue:** Only 8 of 52 blueprints enforce module entitlement. 44+ expose full route trees regardless of tenant plan.  
**Current implementation:** `guard_module('module_name')` registered as `@bp.before_request` in some blueprints.  
**Why insufficient:** Most blueprints skip it entirely.  
**New Model/State/Route needed?** No.  
**Smallest safe change:** Register `guard_module(ModuleName.XYZ)` in every blueprint `__init__.py` that corresponds to a SaaS module.  
**Affected files:** `routes/manager/__init__.py`, `routes/ai_imaging_routes.py`, `routes/patient_portal.py`, `routes/or_management_routes.py`, `routes/telemedicine_routes.py`, `routes/emar_routes.py`, `routes/barcode_routes.py`, `routes/bed_management_routes.py`, and all others.  
**Database impact:** None.  
**Backward compatibility:** May break existing tenants on limited plans if they were inadvertently using disabled modules. This is **desired security behavior** — but must be communicated.  
**Rollback:** Remove the `guard_module` registration.  
**Tests:** Add test for each blueprint verifying 403 when module is disabled.  
**Commit boundary:** One commit per blueprint group (e.g., all medical modules, all admin modules).

### Ticket F-004: Validate `current_user.tenant_id == g.tenant_id` (P0)
**Priority:** P0  
**Issue:** No code validates that the authenticated user belongs to the resolved tenant context.  
**Current implementation:** `g.tenant_id` is resolved from session/URL/subdomain; `current_user.tenant_id` is set at login.  
**Why insufficient:** Session manipulation or slug hopping could allow cross-tenant access.  
**New Model/State/Route needed?** No.  
**Smallest safe change:** Add a middleware check after `set_tenant_context()` that asserts `current_user.tenant_id == g.tenant_id` (with exemptions for `super_admin`, `owner` roles).  
**Affected files:** `app/core/tenant/middleware.py`.  
**Database impact:** None.  
**Backward compatibility:** Fully compatible for regular users. Super admins and owners need exemption.  
**Rollback:** Remove the assertion.  
**Tests:** Add test that user from Tenant A cannot access `/t/tenant-b/...`.  
**Commit boundary:** One commit.

### Ticket F-005: Department-Scoped Visit Access for Lab/Radiology/Emergency (P1)
**Priority:** P1  
**Issue:** Lab, radiology, and emergency routes do not verify that the visit is assigned to the user's department.  
**Current implementation:** Lab routes check `LabRequest.tenant_id == g.tenant_id` but not `Visit.department_id == current_user.department_id`.  
**Why insufficient:** A lab tech in the biochemistry lab can access lab requests for the hematology lab.  
**New Model/State/Route needed?** No.  
**Smallest safe change:** Add `visit.department_id == current_user.department_id` filter (or `_is_user_allowed_for_department` check) to lab, radiology, and emergency visit lookups.  
**Affected files:** `routes/lab/*.py`, `routes/radiology/*.py`, `routes/emergency/*.py`.  
**Database impact:** None.  
**Backward compatibility:** May break workflows where cross-department collaboration is expected. Needs review of actual department structure.  
**Rollback:** Remove the department filter.  
**Tests:** Add test that lab tech in Dept A cannot open lab request for Dept B.  
**Commit boundary:** One commit per department type.

### Ticket F-006: Billing Route Visit Ownership Validation (P1)
**Priority:** P1  
**Issue:** Billing routes (`routes/finance.py`, `routes/payment_routes.py`) do not verify visit ownership before calling `GatekeeperService`.  
**Current implementation:** Routes accept `visit_id` and pass it directly to service.  
**Why insufficient:** Any accountant can archive/bill any visit by ID.  
**Smallest safe change:** Add `get_tenant_record(Visit, visit_id)` in the route before service call.  
**Affected files:** `routes/finance.py`, `routes/payment_routes.py`.  
**Database impact:** None.  
**Backward compatibility:** Fully compatible.  
**Rollback:** Remove the lookup.  
**Tests:** Add test that accountant cannot bill visit from another tenant.  
**Commit boundary:** One commit.

### Ticket F-007: Unified Visit Timeline Audit (P2)
**Priority:** P2  
**Issue:** State transitions, transfers, billing events, and archive events are in separate tables.  
**Current implementation:** `VisitWorkflowEvent` (state), `VisitTransferLog` (transfer), `AuditTrail` (generic).  
**Why insufficient:** No unified view of visit lifecycle for reception monitoring.  
**New Model/State/Route needed?** No new model needed — can query and union existing tables.  
**Smallest safe change:** Create a service method `get_visit_timeline(visit_id)` that queries and unions `VisitWorkflowEvent`, `VisitTransferLog`, and relevant `AuditTrail` rows, ordered by timestamp.  
**Affected files:** New service method; potentially new API endpoint and template snippet.  
**Database impact:** None.  
**Backward compatibility:** Fully compatible.  
**Rollback:** Remove the service method.  
**Tests:** Add test that timeline includes state change, transfer, and archive events.  
**Commit boundary:** One commit.

---

## G. Required Tests to Add Later

Do not write these yet. They must be added after each ticket is approved and implemented.

1. **Tenant-scoped visit lookup:** A user in Tenant A cannot see or open a visit from Tenant B via direct URL (`/reception/visits/<id>`, `/doctor/patient-details/<id>`, `/emergency/treatment/<id>`).
2. **Doctor isolation:** A doctor cannot open another doctor's assigned visit through direct URL or API.
3. **Reception monitoring:** Reception can monitor a visit after assigning it to a doctor (verify list includes the visit).
4. **Treatment completion non-archive:** Completing treatment sets `status=COMPLETED` but `archive_status` remains `ACTIVE`.
5. **Return to reception:** After `transfer_visit` back to reception, `visit.department_id` and `visit.doctor_id` are cleared or set to reception defaults.
6. **Doctor cannot archive:** A doctor role user receives 403 on `POST /reception/visits/<id>/archive`.
7. **Doctor cannot bill:** A doctor role user receives 403 on billing endpoints.
8. **Reception can archive:** Reception role can archive a completed, paid visit.
9. **Cross-tenant patient isolation:** Tenant A cannot view patients from Tenant B.
10. **Cross-tenant invoice isolation:** Tenant A cannot view invoices from Tenant B.
11. **Module entitlement enforcement:** A tenant with lab disabled receives 403 on all `/lab/*` routes.
12. **Module entitlement API bypass:** A tenant with radiology disabled receives 403 on `/api/fhir/servicerequest` even with valid authentication.
13. **Backend > UI:** Verify that removing a module from `TenantModule` blocks backend access even if UI menu items are still rendered.
14. **Background job tenant context:** Celery tasks processing visits preserve `tenant_id` in queries.

---

## H. Approval Required Before Implementation

### Proposed Ticket Execution Order

| Order | Ticket | Priority | P0 Blocker? |
|---|---|---|---|
| 1 | F-002: Explicit `tenant_id` on Visit Creation | P0 | **Yes** |
| 2 | F-004: Validate `current_user.tenant_id == g.tenant_id` | P0 | **Yes** |
| 3 | F-001: Uniform Tenant-Scoped Visit Lookup | P0 | **Yes** |
| 4 | F-006: Billing Route Visit Ownership Validation | P1 | No |
| 5 | F-005: Department-Scoped Visit Access | P1 | No |
| 6 | F-003: Add `guard_module` to All Blueprints | P1 | No |
| 7 | F-007: Unified Visit Timeline Audit | P2 | No |

### P0 Blockers
Tickets **F-001, F-002, and F-004** are P0 blockers. They address cross-tenant data leakage and unauthorized visit access. These must be completed before any P1 or P2 tickets.

### Assumptions Requiring Confirmation

1. **Department-level isolation is required:** The audit assumes that a lab tech in Department A should not access visits assigned to Department B within the same tenant. Confirm if this is the intended security model, or if cross-department access within a tenant is acceptable.
2. **Module entitlement should block backend access:** The audit assumes that disabling a module for a tenant should return 403 on all corresponding routes. Confirm if some modules should remain "read-only" when disabled.
3. **Super admin cross-tenant access is acceptable:** The audit exempts `super_admin` from tenant validation. Confirm if this is correct, or if super admins should also be scoped to a single tenant when browsing regular URLs.
4. **`db.session.get()` should be eliminated for tenant-scoped models:** The audit recommends replacing all `db.session.get(Model, id)` with tenant-filtered queries. Confirm if any edge cases require global lookups (e.g., super admin dashboards).

---

**STOP — No implementation will begin until explicit approval is provided.**

Please review this report and confirm:
1. Which tickets to approve (all P0, or subset)?
2. Whether the assumptions above are correct.
3. Any additional constraints or priorities.

Once approved, work will proceed on one ticket at a time, with relevant tests run and status reported before moving to the next.
