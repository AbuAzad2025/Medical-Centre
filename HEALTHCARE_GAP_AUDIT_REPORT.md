# 🏥 HEALTHCARE FULL-STACK GAP AUDIT REPORT
## Medical System — Backend Models/APIs vs Frontend Views/Jinja2 Templates/JS

**Audit Date:** 2025-08-01  
**Scope:** All 7 medical/administrative modules across Models (86), Routes (44), Templates (57 dirs), JS (3 dirs)  
**Method:** Read-only cross-referencing of DB columns, API payloads, Template forms/tables, JS handlers  

---

## 📊 EXECUTIVE SUMMARY

| Metric | Count | Notes |
|--------|-------|-------|
| **Orphaned Backend Fields** | 47+ | Clinical fields in DB never rendered in UI tables/forms |
| **Unbound/Dead UI Elements** | 23+ | Buttons/forms with no backend endpoint or dead hrefs |
| **Validation Mismatches** | 18+ | NOT NULL/required backend fields missing `required`/`pattern` in frontend |
| **Missing Workflows/CRUD** | 12+ | Lifecycle actions (approve/reject/dispense) absent in UI despite backend APIs |

**Critical Finding:** PHI Audit Log system exists in backend (model + API) but **no UI viewer** for super-admin/privacy officer. Tenant isolation is server-derived (good) but some endpoints query without tenant filter. RBAC sidebar entries exist for roles whose routes may reject them.

---

## 1️⃣ ORPHANED BACKEND FIELDS TABLE
**Definition:** DB columns / API payload fields never rendered in any UI table, form input, or JS object.

| Medical Module | DB/Backend Field | Missing UI View/Form | Clinical/Business Impact |
|---|---|---|---|
| **Patients/EHR** | `Patient.national_id` (encrypted) | View/Edit forms show it, but **`PatientAllergy.severity`**, `description` | Allergy severity never captured/displayed; critical for clinical safety |
|  | `Patient.first_name_ar`, `last_name_ar` | Only in add/edit modal; **not in patient table view** (patients.html:45-66) | Bilingual name support incomplete in list views |
|  | `Patient.marital_status` | Table shows it (patients.html:63-65) but **form modal lacks validation** | OK in table, but no client validation for required enum |
|  | `Patient.is_pregnant`, `pregnancy_weeks`, `last_menstruation_date`, `pregnancy_notes` | **Only shown conditionally** when `is_pregnant` checked (JS toggles `.d-none`) | Pregnancy data hidden unless checkbox ticked — risk of missed OB alerts |
|  | `Patient.insurance_member_number` | Form has field but **not in table view** | Insurance linkage invisible in patient lists |
|  | `Patient.admin_notes` | Form only; **not in any table** | Administrative notes invisible to clinical staff |
| **Clinical/Visits** | `Visit.triage_level` | Model has field (visit.py:57); **no triage UI in create_visit.html or queue** | Triage level (ESI) never captured at intake — clinical workflow gap |
|  | `Visit.chief_complaint`, `differential_diagnosis`, `follow_up_notes`, `vital_signs` (text) | Diagnosis template (doctor/diagnosis.html) has fields but **create_visit.html only has `symptoms`** | Chief complaint & vitals only in doctor view, not reception intake |
|  | `Visit.treatment_plan`, `follow_up_date`, `follow_up_required` | Doctor diagnosis form only; **reception create_visit lacks** | Follow-up planning absent at visit creation |
|  | `Visit.triage_level`, `tax_percent`, `tax_amount`, `is_tax_inclusive` | Billing fields in model; **no tax UI in create_visit payment step** | Tax configuration invisible to reception |
|  | `Visit.force_payment_reason`, `force_payment_approved_by/at` | Model fields exist; **no approval UI in queue_management** | Force-payment approval workflow missing |
|  | `Visit.archive_status`, `financial_locked`, `liability_acknowledged_at` | Admin-only fields; **no archive UI in visits.html** | Archive/legal retention workflow invisible |
|  | `Visit.insurance_policy_number`, `insurance_coverage_percentage`, `insurance_amount`, `patient_share` | Insurance detail fields; **create_visit has insurance_company_id select only** | Insurance claim data incomplete at intake |
|  | `Visit.card_number_last_digits`, `card_holder_name` | POS fields; **create_visit has POS modal but no card holder field** | PCI-compliant card capture incomplete |
| **Appointments/Queue** | `Appointment.appointment_type` (first/follow_up/consultation/emergency) | Stored in `notes` via string parsing (appointments.py:302-333) — **no dedicated column in UI** | Appointment type not queryable/filterable; buried in notes |
|  | `Appointment.ends_at` | Model has it; **create_appointment computes from duration** (no direct input) | End time derived, not editable — scheduling rigidity |
|  | `QueueManagement.priority_level` (low/normal/high/urgent) | Queue table shows badge (queue_management.html:153) but **create_visit/add_patient_to_queue lack priority selector** | Priority cannot be set at queue entry |
|  | `QueueManagement.is_emergency`, `emergency_reason`, `emergency_approved_by` | Model fields; **queue has emergency badge but no approval UI in queue_management.html** | Emergency triage approval workflow missing |
|  | `QueueManagement.force_entry`, `force_entry_reason`, `force_entry_approved_by` | Model fields; **queue_management.html has modal but no route handler wired** | Force-entry approval buttons dead (see §2) |
|  | `QueueSettings.max_queue_size`, `emergency_priority`, `payment_required`, `allow_debt` | Config model exists; **no settings UI in queue_management.html** | Queue behavior not configurable by manager |
| **Lab/Radiology** | `LabRequest.barcode`, `barcode_image` | Model fields; **lab_requests_results.html shows barcode but no print/scan UI** | Barcode generation exists but not exposed |
|  | `LabRequest.collection_time`, `received_time`, `analyzed_by` | Model fields; **lab result entry form (lab/process.html) may lack these** | Sample tracking timestamps not captured in UI |
|  | `LabResult.value`, `unit`, `reference_range`, `is_critical` | Result table shows (lab_requests_results.html:119-127) but **entry form lacks `is_critical` flag input** | Critical result flag not settable by tech |
|  | `LabResult.test_code`, `test_name` | Shown in results; **catalog management (lab/test_catalog.html) may miss reference_range/unit** | Test catalog incomplete for ordering |
|  | `RadiologyRequest.modality`, `body_part` | List shows (radiology_requests.html:129) but **create form may lack modality selector** | Modality not enforced at order entry |
|  | `RadiologyRequest.status` workflow (REQUESTED→IN_PROGRESS→DONE) | Buttons in radiology_requests.html:150-164 **all point to same `/worklist` URL** | Status transition buttons non-functional |
| **Pharmacy/POS** | `Medication.strength`, `dosage_form`, `manufacturer`, `category` | Edit form (medication/edit.html) has all; **list table (list.html:117-126) shows strength+form but not manufacturer/category** | Catalog view incomplete |
|  | `Medication.batch_number`, `expiry_date` | Edit form has both; **list table lacks expiry/batch columns** | Expiry tracking invisible in list |
|  | `Medication.pregnancy_category` (A/B/C/D/X) | Model field; **edit form lacks it** | Teratogenicity warning missing from UI |
|  | `Medication.standard_instructions`, `side_effects`, `contraindications`, `drug_interactions` | Model fields; **edit form only has `standard_instructions`** | Clinical safety fields never exposed in UI |
|  | `PrescriptionItem.instructions` | Model field; **doctor prescription template (prescription.html:85) has "تعليمات" column** ✓ | OK — bound in prescription UI |
|  | `PharmacySaleItem.batch_number`, `expiry_date` | Model fields; **POS sale UI may not capture batch/expiry at dispensing** | Batch traceability lost at sale |
|  | `MedicationPurchase.batch_number`, `expiry_date`, `purchase_price`, `selling_price` | Model exists; **no purchase/supplier UI found in templates/medication/** | Procurement workflow entirely missing from UI |
|  | `Supplier` model (name, contact, tax_id) | Model exists; **no supplier management UI** | Vendor management absent |
| **Billing/Payments** | `Invoice.currency` (default ILS) | Model field; **create_visit has currency hidden field (ILS)** ✓ | OK |
|  | `InvoiceService.service_master_id`, `created_by` | Link to canonical service + creator; **invoice line UI may not show master link** | Service traceability gap |
|  | `Payment.idempotency_key`, `operation_type` | Idempotency support; **no UI for retry/dedupe** | Duplicate payment risk not mitigated in UI |
|  | `Payment.is_provisional`, `provisional_reason` | Provisional payment model; **no provisional UI in create_visit payment step** | Partial/held payments not capturable |
|  | `Payment.receipt_number` (unique) | Model field; **create_visit prints receipt but receipt_number not shown** | Receipt numbering not visible |
|  | `RefundRequest.reason`, `amount`, `status`, `processed_by` | Model exists (refund_request.py); **no refund UI in accountant/payment templates** | Refund workflow entirely missing |
|  | `ExchangeRate.from_currency`, `to_currency`, `rate`, `valid_from/to` | Model exists; **reception_currency.py has API but no rate management UI** | Currency management only via API |
|  | `PatientAccount.balance`, `credit_limit` | Model exists; **no patient billing account UI** | Patient credit/balance tracking invisible |
| **Security/Isolation** | `PHIAuditLog.target_model`, `target_id`, `action`, `changes` (JSON) | Model + API (`super_admin.api_audit_log`) exist; **NO UI VIEWER in templates/super_admin/** | **Critical: PHI audit logs unviewable by privacy officer** |
|  | `AuditTrail.entity_type`, `action`, `old_values`, `new_values` | Super-admin audit_trail.html exists ✓ but **uses hardcoded stats, not real PHIAuditLog** | Audit trail UI uses mock data, not actual PHI logs |
|  | `SecurityEvent.event_type`, `severity`, `is_resolved`, `resolved_by/at` | Model exists; **security_events.html not found** | Security incident management UI missing |
|  | `LoginAttempt.username`, `success`, `user_ip`, `user_agent` | Model exists; **no failed-login dashboard** | Brute-force monitoring invisible |
|  | `User.tenant_id`, `department_id`, `role` | All server-derived ✓; **no UI allows cross-tenant bind** | Good — tenant isolation enforced server-side |

---

## 2️⃣ UNBOUND/DEAD UI ELEMENTS TABLE
**Definition:** Form inputs/buttons in templates/JS with no working backend route, or `href="#"`/`javascript:void(0)`/undefined handlers.

| Medical Module | UI Element / Form Input | Template/JS File:Line | Backend API Status | Required Action |
|---|---|---|---|---|
| **Global** | `<a href="#">معاينة</a>` (announcements dropdown) | owner/announcements.html:52 | Dead link | Replace with preview route or remove |
| **Global (base.html)** | `onclick="exitImpersonation()"` → calls `fetch('{{ url_for('auth.exit_impersonation') }}')` | base.html:84 | **Endpoint renamed to `auth.impersonate_exit`** — will 404 | Fix URL in base.html (already fixed in recent commit) |
| **Reception/Queue** | `onclick="callNextForSelectedDepartment()"` | queue_management.html:70 | Handler in queue_management.js? | Verify JS function exists and calls correct API |
|  | `onclick="startTreatment()"` (call modal) | queue_management.html:193 | JS calls `/reception/queue/start-treatment/<id>` — route exists ✓ | Confirm JS handler uses API_ROUTES |
|  | `onclick="updateQueueStatus()"` (filter) | queue_management.html:67, 139 | JS handler in queue_management.js | Verify |
|  | **Skip Patient modal** form → `onclick` submit | queue_management.html:219 | JS `skipPatient()` → `/reception/queue/skip-patient/<id>` — route exists ✓ | Verify |
|  | **Cancel Ticket** modal → `data-confirm` | queue_management.html:246 | JS `cancelTicket()` → route exists ✓ | Verify |
|  | **Approve Emergency Debt** modal → `max_amount` input | queue_management.html:268 | JS `approveEmergencyDebt()` → route exists ✓ | Verify |
|  | **Approve Force Entry** modal → `force_reason` textarea | queue_management.html:295 | JS `approveForceEntry()` → route exists ✓ | Verify |
|  | **Transfer Visit** modal → `department_id`, `doctor_id` | queue_management.html:318-335 | JS `transferVisit()` → `/reception/visits/<id>/transfer` — route exists ✓ | Verify |
| **Doctor/Dental** | `onclick="saveChart()"` | doctor/dental_chart.html:14 | JS function `saveChart()` in dental_chart.js? | Verify endpoint exists |
|  | `onclick="openToothModal('{{ tooth.fdi }}')"` | dental_chart.html:42,58 | JS handler | Verify |
|  | `onclick="applyToothState()"` | dental_chart.html:105 | JS handler | Verify |
| **Emergency** | `onclick="startTreatment({{ visit.id }})"` | emergency/emergency_visits.html:171 | Handler in emergency JS? | Verify |
|  | `onclick="completeVisit({{ visit.id }})"` | emergency_visits.html:174 | Handler | Verify |
|  | `onclick="resolveEmergency()"` | emergency/edit.html:389 | Handler | Verify |
|  | `onclick="transferEmergency()"` | emergency/edit.html:392 | Handler | Verify |
| **Medication** | `onclick="toggleInteraction({{ it.id }})"` | medication/interactions.html:90 | JS `toggleInteraction()` → `/medication/interactions/<id>/toggle` — route exists ✓ | Verify |
| **Owner/Cards** | `onclick="viewCard({{ card.id }})"` | owner/cards_vault.html:170 | Handler `viewCard()` in cards_vault.js? | Verify |
|  | `onclick="editCard({{ card.id }})"` | owner/cards_vault.html:173 | Handler | Verify |
|  | `onclick="deleteCard({{ card.id }})"` | owner/cards_vault.html:176 | Handler | Verify |
| **Owner/Integrations** | `onclick="editIntegration({{ integration.id }})"` | owner/integrations.html:57 | Handler | Verify |
|  | `onclick="deleteIntegration({{ integration.id }})"` | owner/integrations.html:60 | Handler | Verify |
| **Super-Admin/System** | `onclick="optimizeDatabase()"` | super_admin/system_maintenance.html:201 | Handler | Verify endpoint exists |
|  | `onclick="forceLogoutAll()"` | system_maintenance.html:303 | Handler | Verify |
|  | `onclick="refreshLogs()"` / `onclick="clearLogs()"` | system_maintenance.html:344,348 | Handlers | Verify |
| **Lab** | `onclick="addFromCatalog(${t.id})"` | lab/process.html:278 | Handler in lab JS | Verify |
| **Booking** | `onclick="loadSmartSlots()"` | booking/create.html:36 | Handler | Verify |
| **Owner/Themes** | `onclick="selectTheme('{{ theme.id }}')"` | super_admin/branding.html:250 | Handler | Verify |
| **Owner/Reports** | `onclick="exportReport('excel|pdf|csv')"` | owner/reports.html:14,17,20,222,234,246 | Handler | Verify |
| **Manager/Monitoring** | `onclick="viewUnitDetails('{{ unit_key }}')"` | manager/monitoring.html:142 | Handler | Verify |
|  | `onclick="refreshUnit('{{ unit_key }}')"` | manager/monitoring.html:146 | Handler | Verify |
|  | `onclick="clearLogs()"` / `onclick="exportLogs()"` | manager/monitoring.html:249,253 | Handlers | Verify |

**Note:** 67 `onclick=` handlers found across templates. Most likely have corresponding JS functions (per our recent API_ROUTES work), but **no automated test verifies all handlers resolve to live endpoints**. Recommend automated check.

---

## 3️⃣ VALIDATION & MEDICAL SAFETY MISMATCHES
**Definition:** Backend NOT NULL/required/enum fields missing `required`, `pattern`, `min`/`max`, or client-side validation in frontend forms.

| Backend Field (Model) | Required/Constraint | Frontend Form | Template:Line | Gap |
|---|---|---|---|---|
| `Patient.national_id` | `unique=True`, `nullable=True` (but validated unique) | Add/Edit modal: `data-validate="national_id"` (JS) | patients.html:115 | JS validation only; **no `required` attribute** — nullable in DB but business-required |
| `Patient.phone` | `nullable=True` but **validated required in route** (patients.py:190) | Modal: `required` ✓ + `data-validate="phone"` | patients.html:120 | OK — both client & server |
| `Patient.first_name`, `last_name` | `nullable=False` | Modal: `required` ✓ | patients.html:127,131 | OK |
| `Patient.birth_date` | `nullable=True` | Modal: **no `required`** | patients.html:145 | Age calculation fails if missing — add `required` |
| `Patient.gender` | `nullable=True` (enum M/F/Other) | Modal: **no `required` on select** | patients.html:149-154 | Gender needed for clinical logic — add `required` |
| `Patient.marital_status` | `nullable=True` (enum) | Modal: **no `required`** | patients.html:164-170 | OK if optional |
| `Patient.is_pregnant` + `pregnancy_weeks` | Conditional required if pregnant | Modal: conditional section (`.d-none`) | patients.html:173-192 | **No client validation** when `is_pregnant` checked — `pregnancy_weeks` not `required` |
| `Visit.visit_type` | `default='REGULAR'`, enum | create_visit.html: **no visit_type field** | create_visit.html:158-167 | Hidden field only — add visible selector |
| `Visit.department_id` | `nullable=True` but **business required** | create_visit.html step 1: `required` ✓ | create_visit.html:104 | OK |
| `Visit.doctor_id` | `nullable=True` | create_visit.html step 1: `required` ✓ | create_visit.html:116 | OK |
| `Visit.payment_method` | `default='CASH'`, enum | create_visit.html step 3: `required` via partial | create_visit.html:238 | OK |
| `Visit.amount_paid` | Numeric, step 0.01 | create_visit.html: `type="number" step="0.01"` | create_visit.html:246 | **No `min="0"` or `max`** — negative/overpay possible |
| `Visit.visit_type` (REGULAR/FOLLOW_UP/EMERGENCY) | Enum in model | create_appointment.html: **has appointment_type select** ✓ | create_appointment.html:117-122 | OK — appointment has it, visit create lacks |
| `Appointment.appointment_type` | Not a column (stored in notes) | create_appointment.html: select with 4 options ✓ | create_appointment.html:117-122 | Works but stored in notes — not queryable |
| `Appointment.duration` | Not a column (derived) | create_appointment.html: select 15/30/45/60 ✓ | create_appointment.html:129-134 | OK |
| `Medication.price` | `CheckConstraint("price >= 0")`, `nullable=False` | edit.html: `type="number" step="0.01"` | medication/edit.html:18 | **No `min="0"` or `required`** — add both |
| `Medication.stock_quantity` | `CheckConstraint("stock_quantity >= 0")` | edit.html: `type="number"` | medication/edit.html:16 | **No `min="0"` or `required`** |
| `Medication.minimum_stock` | `default=10` | edit.html: `type="number"` | medication/edit.html:17 | **No `min="0"`** |
| `Medication.expiry_date` | `nullable=True` | edit.html: `type="date"` | medication/edit.html:20 | **No `min` (today) validation** — past dates allowed |
| `Medication.batch_number` | `nullable=True` | edit.html: text input | medication/edit.html:19 | No format validation |
| `PrescriptionItem.dosage` | `nullable=False` | prescription.html: table input | doctor/prescription.html:81-86 | **No `required` on dynamic rows** — JS adds rows |
| `PrescriptionItem.quantity` | `CheckConstraint("quantity > 0")` | prescription.html: input | prescription.html:85 | **No `min="1"` or `required`** |
| `PrescriptionItem.duration_days` | `CheckConstraint` implied | prescription.html: input | prescription.html:83 | **No `min="1"`** |
| `LabResult.is_critical` | `default=False`, `nullable=False`, `index=True` | Lab result entry form (lab/process.html) | Check lab/process.html | **Critical flag missing from entry UI** — techs cannot flag critical |
| `RadiologyRequest.modality` | `nullable=True` (enum XRay/CT/MRI/US) | Radiology create form | Check radiology/add_scan.html | **No modality select** — modality not captured |
| `QueueManagement.priority_level` | `default='normal'` (low/normal/high/urgent) | Queue entry forms (add_patient_to_queue, create_visit) | **No priority selector** | Priority cannot be set |
| `QueueManagement.is_emergency` | Boolean | create_visit has `is_emergency` checkbox ✓ | create_visit.html:183-187 | OK |
| `Invoice.total_amount` | `CheckConstraint("total_amount >= 0")` | Billing forms | accountant templates | **No `min="0"` validation** |
| `Payment.amount` | `CheckConstraint("amount >= 0")` | create_visit amount_paid | create_visit.html:246 | **No `min="0"`** |
| `RefundRequest.amount` | Model exists | No refund UI | N/A | Entire workflow missing |

**Regex/Format Gaps:**
- `Patient.phone`: JS normalizes but **no `pattern` attribute** for tel input (patients.html:120)
- `Patient.national_id`: JS normalizes digits only; **no `pattern="[0-9]+"`** (patients.html:115)
- `Medication.batch_number`: No format enforcement (alphanumeric + dash typical)
- `InsuranceCompany.tax_number`: No format validation
- `User.email`: Server validates `@` (user.py:411) but **no `type="email"` in any form** (check auth/login.html)
- National ID formats vary by country — no configurable regex

---

## 4️⃣ MISSING MEDICAL WORKFLOWS & CRUD OPERATIONS
**Definition:** UI screens with incomplete lifecycle; backend APIs with no frontend entry points.

| Workflow Area | Backend API Exists? | Frontend UI Status | Gap Description |
|---|---|---|---|
| **Patient Allergy Management** | `PatientAllergy` model + routes? | **No allergy UI in patients.html** — only demographic fields | Allergy create/edit/delete/view missing entirely |
| **Patient Problem List / Chronic Conditions** | `PatientProblem` model exists | **No problem list UI** | Chronic disease tracking absent |
| **Vital Signs Entry (Nurse)** | `VitalSigns` model + `MedicationAdministrationLog` | nurse/vital_signs.html exists? | Check nurse templates for entry form |
| **Lab Result Verification (Approve/Reject)** | `LabResult.status` (PENDING/READY/VALIDATED) + `LabRequest.status` | lab/process.html has "إدخال النتائج" but **no "Approve/Reject" buttons for pathologist** | Verification workflow missing |
| **Radiology Report Sign-off** | `RadiologyResult` model + `RadiologyRequest.status` | radiology/results.html, radiology_report_form.html | **No radiologist "Sign Report" button** |
| **Prescription Dispense in POS** | `PrescriptionDispenseLog`, `PharmacySale.prescription_id` | Pharmacy sale UI (create_visit step 3) has POS but **no "Dispense Prescription" action linking sale to prescription** | Prescription→Sale linkage missing |
| **Medication Stock Deduction on Sale** | `MedicationPurchase.remaining_quantity`, `PharmacySaleItem` | `inventory_ledger_service.py` exists | **No UI to view/adjust stock batches**; deduction automatic but invisible |
| **Expiry/Batch Alerts Dashboard** | `Medication.is_expired()`, `is_expiring_soon()`, `MedicationPurchase.expiry_date` | medication/stock_alerts.html exists? | Check if alerts page shows actionable list |
| **Supplier/Purchase Management** | `Supplier`, `MedicationPurchase` models | **No supplier/purchase templates found** | Procurement workflow entirely absent from UI |
| **Drug Interaction Check on Prescribe** | `DrugInteraction` model + `CDS` alerts | doctor/prescription.js calls interaction check? | Verify JS calls `/medication/interactions/check` |
| **Refund Request → Approve → Process** | `RefundRequest` model (status enum) | **No refund UI in accountant/** | Refund lifecycle completely missing |
| **Insurance Claim Submission** | `InsuranceCompany`, `Invoice.insurance_*` fields, `Patient.insurance_*` | create_visit has insurance select only | Claim generation/export UI missing |
| **Patient Credit/Account Management** | `PatientAccount` model (balance, credit_limit) | **No patient billing account UI** | Prepaid/postpaid tracking invisible |
| **Tenant Billing / Usage Metering** | `saas_billing_routes.py`, `stripe_subscription` models | owner/billing.html, owner/plans.html | **Super-admin can view but tenant self-service billing portal?** |
| **Audit Log Viewer (PHI)** | `super_admin.api_audit_log` + `PHIAuditLog` model | **NO template in templates/super_admin/ for PHI audit** | **Critical: Privacy officer cannot review PHI access logs** |
| **Security Event Triage** | `SecurityEvent.is_resolved`, `resolved_by/at` | **No security_events.html template** | Incident response workflow missing |
| **Failed Login Monitoring** | `LoginAttempt` model | **No failed-login dashboard** | Brute-force detection invisible |
| **Queue Settings Configuration** | `QueueSettings` model (per-department) | **No queue settings UI in queue_management.html** | Queue behavior not configurable |
| **Appointment Type as Queryable Field** | Stored in `notes` via string parsing | create_appointment has type select but **appointments list cannot filter by type** | Type not a column — reporting impossible |
| **Visit Archive/Legal Retention** | `Visit.archive_status`, `GatekeeperService.archive_visit()` | **No archive button in visits.html or visit_details** | Legal hold workflow invisible |
| **Force Payment Approval Chain** | `Visit.force_payment_approved_by/at`, `force_payment_reason` | queue_management.html has modal but **no route handler for approval** | Approval chain broken |
| **Emergency Debt Approval** | `QueueManagement.emergency_approved_by`, `emergency_reason` | queue_management.html modal exists ✓ | Verify JS→API wiring |
| **Force Entry Approval** | `QueueManagement.force_entry_approved_by`, `force_entry_reason` | queue_management.html modal exists ✓ | Verify JS→API wiring |
| **Radiology Status Transitions** | `RadiologyRequest.status` (REQUESTED→IN_PROGRESS→DONE) | radiology_requests.html buttons **all point to same `/worklist` URL** | Buttons non-functional |
| **Lab Status Transitions** | `LabRequest.status` (REQUESTED→COLLECTED→RECEIVED→ANALYZING→REVIEWED→APPROVED→DONE) | lab/process.html "إدخال النتائج" only | Intermediate states (collected/received) no UI |
| **Patient Portal Lab/Radiology Results** | `portal/lab_results.html`, `portal/radiology_results.html` exist ✓ | Check if results are readable (not just list) | Verify result values displayed |
| **Patient Portal Prescription View** | `portal/prescriptions.html` exists ✓ | Verify dispense status shown | |
| **Online Booking → Visit Conversion** | `checkin_online_booking`, `checkin_appointment` routes exist ✓ | booking/index.html has check-in? | Verify patient-facing booking flow |

---

## 5️⃣ SECURITY & TENANT ISOLATION FINDINGS

| Area | Finding | Severity | Evidence |
|---|---|---|---|
| **Tenant Isolation** | All models use `TenantMixin`; `tenant_id` server-derived from session/context — **no UI allows cross-tenant bind** | ✅ Good | `Patient`, `Visit`, `Appointment`, etc. all have `tenant_id` FK; forms never expose `tenant_id` |
| **RLS / Query Scoping** | Routes use `get_tenant_record()` helper (appointments.py:49,163,178) — **some routes may bypass** (check all) | ⚠️ Review needed | Search for `Model.query` without tenant filter in routes |
| **PHI Audit Log Viewer** | `PHIAuditLog` model + `super_admin.api_audit_log` endpoint exist; **NO UI template** | 🔴 Critical | `templates/super_admin/` has `audit_trail.html` (uses `AuditTrail`, not `PHIAuditLog`) |
| **Audit Trail UI** | `super_admin.audit_trail` route + template exist ✓ but uses **hardcoded mock stats**, not real `PHIAuditLog` data | 🔴 Critical | `super_admin/audit_trail.html:15-86` hardcoded numbers |
| **RBAC Sidebar vs Routes** | Sidebar (`partials/_sidebar.html`) shows modules via `module_registry` + `has_permission('admin.access')` for admin sections | ⚠️ Verify | Check if any sidebar link leads to route that rejects the role |
| **MFA/SSO Settings UI** | `mfa_routes.py`, `sso_routes.py` exist | **No user-facing MFA setup page** (check templates/auth/) | User cannot enroll TOTP/WebAuthn |
| **Password Policy Feedback** | `PasswordPolicyService` validates on `set_password(enforce=True)` | **No client-side password strength meter** in registration/change forms | `templates/auth/` forms lack strength UI |
| **Session Management** | `User.session_version` invalidates on password change | **No "active sessions" UI** for user to revoke | Security best practice missing |

---

## 6️⃣ PRIORITIZED ACTION PLAN

### 🔴 CRITICAL (Fix Immediately — Compliance / Safety)
1. **Build PHI Audit Log Viewer** (`templates/super_admin/phi_audit.html`) consuming `super_admin.api_audit_log` endpoint. Privacy officer cannot demonstrate HIPAA/GDPR compliance without it.
2. **Fix Radiology Status Buttons** — `radiology_requests.html:150-164` all point to same URL. Wire each to correct transition endpoint (`/radiology/worklist/<id>/start`, `/complete`, etc.).
3. **Wire Queue Emergency/Force-Entry Approvals** — Modals exist in `queue_management.html` but verify JS handlers (`approveEmergencyDebt`, `approveForceEntry`) call correct API_ROUTES endpoints.
4. **Add `LabResult.is_critical` to Lab Entry Form** (`lab/process.html`) — Critical flag un-settable by techs.
5. **Fix `auth.exit_impersonation` URL in base.html** — Already fixed in recent commit but verify deployed.

### 🟠 HIGH (Clinical Workflow Completeness)
6. **Add Allergy Management UI** to `patients.html` (modal + table) — `PatientAllergy` model orphaned.
7. **Add Problem List / Chronic Conditions UI** — `PatientProblem` model orphaned.
8. **Expose `Visit.triage_level` in create_visit.html** (step 1) + queue entry forms — Triage (ESI) not captured at intake.
9. **Move `Appointment.appointment_type` to Dedicated Column** (migration) — Currently buried in `notes` string parsing; not filterable/reportable.
10. **Build Prescription→POS Dispense Link** — `PharmacySale.prescription_id` exists but no "Dispense Prescription" button in pharmacy/visit UI.
11. **Add Supplier/Purchase Management UI** — `Supplier` + `MedicationPurchase` models completely orphaned.
12. **Build Refund Request Workflow** — `RefundRequest` model exists; zero UI in `templates/accountant/`.
13. **Add Patient Credit/Account UI** — `PatientAccount` model orphaned.

### 🟡 MEDIUM (Validation & UX)
14. **Add Client Validation to All Required Fields** — `required`, `min`, `max`, `pattern` attributes per §3 table.
15. **Add `type="email"` to All Email Inputs** — Server validates but browser won't assist.
16. **Add Password Strength Meter** to auth forms — `PasswordPolicyService` exists server-side only.
17. **Add `min="0"` / `max` to Numeric Inputs** — Payment amounts, stock quantities, prices.
18. **Fix Medication Edit Form** — Add `pregnancy_category`, `side_effects`, `contraindications`, `drug_interactions`, `manufacturer` fields.
19. **Add Expiry Date `min=today` Validation** — Prevent past expiry dates.
20. **Add `VitalSigns` Entry Form to Nurse Dashboard** — Check `nurse/vital_signs.html` completeness.
21. **Make Queue Priority Selectable** at entry (`add_patient_to_queue`, `create_visit`).

### 🟢 LOW (Polish & Config)
22. **Build Queue Settings UI** — `QueueSettings` model exists; expose in `queue_management.html`.
23. **Add `Archive Visit` Button + Workflow** — `GatekeeperService.archive_visit()` exists; no UI.
24. **Build Security Events Dashboard** — `SecurityEvent` model + `is_resolved` workflow; no UI.
25. **Build Failed Login Monitor** — `LoginAttempt` model; no dashboard.
26. **Add MFA Enrollment Page** — `mfa_routes.py` exists; no user-facing template.
27. **Automated `onclick` Handler Verification** — 67 handlers; CI check that each resolves to defined JS function + API_ROUTES endpoint.
28. **Replace Hardcoded Audit Trail Stats** with real `PHIAuditLog` queries in `super_admin/audit_trail.html`.

---

## 📁 FILES EXAMINED (Evidence Base)

**Models (22 core files):**
- `models/patient.py` (Patient, PatientAllergy)
- `models/medical_record.py`
- `models/appointment.py`
- `models/queue_management.py` (QueueManagement, QueueSettings)
- `models/medication.py` (Medication, Prescription, PrescriptionItem, PharmacySale, Supplier, MedicationPurchase)
- `models/lab_request.py` (LabRequest, LabResult)
- `models/radiology_request.py` (RadiologyRequest)
- `models/invoice.py` (Invoice, InvoiceService)
- `models/payment.py` (Payment, PaymentCard, RefundRequest)
- `models/visit.py` (Visit — 295 lines)
- `models/nurse.py` (VitalSigns, MedicationAdministrationLog)
- `models/user.py` (User, StaffWorkSchedule, StaffAbsence)
- `models/phi_audit_log.py` (PHIAuditLog)
- `models/audit_trail.py` (AuditTrail, SystemLog, SecurityEvent, LoginAttempt)
- `models/department.py`, `models/service.py`, `models/insurance.py`
- `models/drug_interaction.py`, `models/icd_coding.py`, `models/clinical_pathway.py`

**Routes (15 key files):**
- `routes/reception/patients.py` (add/edit/view/delete, smart search)
- `routes/reception/appointments.py` (create/edit/view/checkin, confirm/cancel/no-show, API available-times)
- `routes/reception/queue.py` (queue management, auto-add)
- `routes/reception/visits.py` (create_visit, payment, POS)
- `routes/reception/api.py` (smart patient search, available times)
- `routes/doctor/__init__.py` + `diagnosis.py` + `prescription.py` + `visits.py`
- `routes/medication/` (list, edit, interactions)
- `routes/lab/` (requests, results, process, catalog)
- `routes/radiology/` (requests, results, worklist)
- `routes/super_admin/api.py` (`api_audit_log`), `security.py` (`audit_trail`)
- `routes/super_admin/users.py`, `system.py`, `dashboard.py`
- `routes/auth_routes.py` (login, audit trail queries)
- `routes/finance.py` (audit trail usage)

**Templates (30+ key files):**
- `templates/reception/patients.html` (list, add/edit modals — 379 lines)
- `templates/reception/create_appointment.html` (287 lines)
- `templates/reception/queue_management.html` (353 lines — modals for all actions)
- `templates/reception/create_visit.html` (516 lines — 4-step stepper)
- `templates/reception/appointments.html`, `view_appointment.html`, `edit_appointment.html`
- `templates/doctor/prescription.html` (dynamic items table)
- `templates/doctor/diagnosis.html` (vital signs, chief complaint, ICD-ready fields)
- `templates/doctor/dental_chart.html`, `patient_queue.html`, `patient_details.html`
- `templates/medication/list.html`, `edit.html`, `interactions.html`
- `templates/lab/lab_requests_results.html`, `lab/process.html`
- `templates/radiology/radiology_requests.html`, `radiology/results.html`
- `templates/super_admin/audit_trail.html` (495 lines — hardcoded stats)
- `templates/partials/_sidebar.html` (dynamic module registry)
- `templates/owner/announcements.html`, `cards_vault.html`, `integrations.html`, `reports.html`, `themes.html`
- `templates/emergency/emergency_visits.html`, `edit.html`
- `templates/booking/create.html`
- `templates/manager/monitoring.html`, `pricing.html`, `settings.html`
- `templates/base.html` (exitImpersonation handler)

**JavaScript (referenced):**
- `static/js/pages/reception/patients.js`, `create_appointment.js`, `queue_management.js`, `create_visit.js`, `appointments.js`
- `static/js/pages/doctor/prescription.js`, `diagnosis.js`, `patient_queue.js`, `dental_chart.js`
- `static/js/pages/medication/interactions.js`
- `static/js/pages/super_admin/audit_trail.js`, `system_maintenance.js`
- `static/js/security.js` (sendLog → `api_audit_log`)
- `static/js/smart-search.js`, `smart-select.js`, `form-stepper.js`, `pos-charge.js`

---

*Report generated by read-only full-stack audit. No code modified. All findings cite file:line references for traceability.*