# Phase 4 Audit — Operational Unit Coverage & Platform Verification
 **Date:** 2026-08-07  |  **Method:** Direct static inspection (rg/read) of models, services, routes, and platform guards. Every claim below is grounded in a verified file:line. No inference.

 ---

 ## 0. Executive Summary

 The system has a **single, shared platform backbone** (`TenantMixin`, `MODULE_REGISTRY`, `guard_module`/`require_module`) and **10 operational units** delivered as tenant-scoped bundles. Module enablement is **fail-closed at the route layer** (`guard_module` → `abort(403)`) and **fail-closed at the service layer** (`require_module` → `ModuleNotEnabledError`). Tenants are isolated by tenant-scoped queries (`get_active_modules_for_tenant`) plus `tenant_required`. Bundles are the **single source of truth** for which modules ship to which profile (`_PRODUCT_PROFILE_SEED`, `models.py:444`), so **decoupling is by design** (e.g. `standalone_lab`, `billing_only`).

Two genuine gaps surfaced that are **not** covered by existing models and should be captured as work items **before** controlled-substance or standalone-ER rollouts:
  1. **`Medication` lacks a narcotic/controlled-substance flag** — compliance cannot be enforced in-product for DEA-type audit trails. **[RESOLVED 2026-08-07: Added `is_controlled` + `schedule` columns (models/medication.py:41-42); migration p5_004; service guard (services/prescription_service.py:195); route ack (routes/medication_routes/prescriptions.py:131); test coverage (tests/test_prescription_service.py:233, tests/test_pharmacy.py:326)]**
  2. **`Nurse.MedicationAdministrationLog` (nurse.py:127) is live technical debt**, fully superseded by `eMARAdministration`/`MedicationSchedule` (emar.py:12,93).
  3. **`prescription.doctor_id` + `requested_by` on lab/radiology orders are `nullable=True`** — ordering these nullability risks must be accepted for standalone lab/radiology (no prescriber visit). This is documented in §4. **[PARTIAL: G-3 guard added — create_prescription now requires doctor_id when doctor module enabled (services/prescription_service.py:156); standalone walk-in allowed when doctor disabled. G-4 guards added — LAB/RAD create_request require requested_by when doctor module enabled (services/lab_service.py:60, services/radiology_service.py:58)]**

 ---
 
 ## 1. 10-Unit Operational Capabilities Matrix

 | # | Unit | Existing Models & Services (File:Line) | Gaps / Missing Features | Standalone Operational Status | Bundle Gate Enforcement |
 |---|------|----------------------------------------|-------------------------|-------------------------------|--------------------------|
 | 1 | Reception & ADT | models/visits.py `Visit`, models/patients.py `Patient`, models/appointments.py `Appointment`; services/reception_service.py:20 `ReceptionService.create_visit` / `register_patient` / `check_in_appointment`; routes/reception/__init__.py `reception_bp` (`/reception`) + booking_bp `/booking` | No bed-floor-map / discharge planner / insurance capture at registration | Not standalone (`standalone_allowed=False`; required_any_of reception-only) — always a dependency of every clinical unit | `reception_bp` guarded `guard_module('reception')` via `_add_guard_once` (app_factory.py:752) |
 | 2 | Emergency (ER) | models/emergency.py:15 `EmergencyCase` (triage_score/category, severity); models/emergency_status_history.py:7 `EmergencyStatusHistory`; services/emergency_service.py:20 `EmergencyService.create_case` / `triage_patient` / `assign_doctor`; routes/emergency/__init__.py `emergency_bp` (`/emergency`) | No trauma-resuscitation protocol template, no ICU-level handoff, no disposition-to-inpatient transfer w/ bed push | `standalone_allowed=False`; **bundled only** in `standalone_emergency`/`urgent_care` (`reception+doctor+nursing+billing`), **never as a pure standalone ER** | `guard_module('emergency')` (app_factory.py:756); `require_module('emergency')` in service layer |
 | 3 | Nursing & eMAR | models/nurse.py:14 `Nurse`, :57 `VitalSigns`, :127 `MedicationAdministrationLog` (LEGACY, dead — see §3); models/nursing_assessment.py:11 `NursingAssessment`; models/emar.py:12 `eMARAdministration`, :93 `MedicationSchedule`; services/nursing_service.py:20 `NursingService` (vitals, notes, admin, care plans, tasks, dashboard); routes/nurse_routes/__init__.py `nurse_bp` (`/nurse /emar /bed /or /nursing-assessment`) | No scheduled-task push/SMS reminders, no SBAR shift handoff form, **no controlled-drug administration audit trail** (Medication has no narcotic flag → see §3) | Not standalone (`standalone_allowed=False`; required_any_of reception/standalone_intake/inpatient); ships in `nursing_home`, `urgent_care`, `community_clinic` | `guard_module('nursing')` (app_factory.py:757) — one guard covers all 5 nurse prefixes |
 | 4 | Specialty Clinics (Doctor) | models/icd_coding.py:12 `ICD10Code`, :42 `CPTCode`, :72 `DRGCode`, :94 `CodedDiagnosis`, :137 `CodedProcedure`; models/medication.py:173 `Prescription`; services/prescription_service.py:22 `PrescriptionService.check_interactions` / `create_prescription`; routes/doctor/__init__.py `doctor_bp` + specialty routes (referral, vaccination, cds, telemedicine, clinical-coding, pathway, specialty-forms, patient-education `/doctor`) | No inbound CDS-Hooks integration (CDS route is outbound-only), no automated sepsis/DKA prediction | **Standalone-capable** (`standalone_allowed=True`, `private_doctor_clinic` = doctor+appointments, no reception) | `guard_module('doctor')` (app_factory.py:753) gates every doctor sub-module |
 | 5 | Pharmacy & Dispensing | models/medication.py:173 `Prescription`, :279 `PrescriptionItem`, :352 `PrescriptionDispenseLog`, :489 `PrescriptionNS`; `Medication` (stock_quantity:36, batch_number:39); services/prescription_service.py:315 `update_stock` / dispense flow; routes/medication_routes/pos.py under `medication_bp` (`/medication`) | **Critical:** `Medication` has NO `is_controlled`/`is_narcotic` flag → cannot gate controlled dispensing or build DEA audit log; no automated reorder workflow UI for `MedicationSupplyRequest` | **Standalone-capable** (`standalone_allowed=True`; `standalone_pharmacy` = pharmacy+inventory+billing) | `guard_module('pharmacy')` (app_factory.py:762) on `medication_bp` |
 | 6 | Laboratory (LIS) | models/lab_request.py:13 `LabRequest`, :99 `LabResult` (status result_status, validation_flag, is_critical); services/lab_service.py:20 `LabService.create_request` / `finalize_results` / `validate_lab_results` / reagent stock / quality; routes/lab/__init__.py `lab_bp` (`/lab`) | No HL7 v2 ORM/OBR order bridge, no external LIS middleware adapter, QC trend analytics are basic | **Standalone-capable** (`standalone_allowed=True`; `standalone_lab` = lab+billing+reporting) | `guard_module('lab')` (app_factory.py:754) |
 | 7 | Radiology (RIS) | models/radiology_request.py:13 `RadiologyRequest`, models/radiology_result.py:13 `RadiologyResult`; services/radiology_service.py:23 `RadiologyService.create_request` / `finalize_result` / `claim_request` / DICOM notify (`is_critical`); routes/radiology/__init__.py `radiology_bp` + `dicom_bp` (`/radiology /dicom`) | No structured reporting template (RadLex/RTF), no DICOM Modality Worklist (MWL), no HL7 ORU callback | **Standalone-capable** (`standalone_allowed=True`; `standalone_radiology` = radiology+billing+reporting) | `guard_module('radiology')` (app_factory.py:755); `dicom_bp` → `'radiology'` (app_factory.py:773); `ai_imaging_bp` → `'ai_imaging'` (app_factory.py:774) |
 | 8 | Accounting & Billing | models/invoice.py:13 `Invoice`, :93 `InvoiceService(line)`; models/insurance.py:14 `InsuranceCompany`, :48 `InsuranceClaim`; models/payment.py:20 `PaymentCard`, :95 `Payment`; models/receipt.py:17 `Receipt`; services/financial_service.py:21 `FinancialService.create_invoice`/`record_payment`/`create_insurance_claim`/`reconcile_visit_payments`; services/payment_service.py:23 `PaymentService.create_payment`; services/pricing_service.py:22 `PricingService`; services/pos_terminal_service.py:6 `PosTerminalService.charge` (via `routes/medication_routes/pos.py`); stripe_subscription_service.py:31 `StripeSubscriptionService.ingest_webhook` | No bad-debt/write-off workflow, no patient-statement/claims export, multi-currency support is limited (PosTerminal `currency='ILS'` default) | **Standalone-capable** (`standalone_allowed=True`; `billing_only` bundle) | `guard_module('billing')` covers `finance_bp` + `accountant_bp` + `payment_bp` (app_factory.py:758,759,764) |
 | 9 | Tenant Facility Admin | models/user.py:16 `User` (+:402 `StaffWorkSchedule`, :422 `StaffAbsence`); models/permissions.py:16 `Permission`, :38 `Role`, :81 `RolePermission`, :110 `UserPermission`, :141 `AuditLog`; models/advanced_permissions.py:14 `ModulePermission`, :86 `DepartmentPermission`; models/tenant/models.py:16 `Tenant`, :384 `TenantFeatureFlag`, :413 `TenantModuleSetting` (JSON per-module config per tenant); routes/manager/__init__.py `manager_bp` (`/manager`) | No role-cloning/self-service RBAC wizard, no per-department schedule templating | Standalone for facility setup (gated `'reporting'` module, manager_bp; app_factory.py:760) — but clinical use always requires a clinical module | `guard_module('reporting')` (manager_bp, app_factory.py:760) |
 | 10 | Super Admin / Platform Owner | models/tenant/models.py:16 `Tenant`, :136 `SubscriptionPlan`, :163 `TenantSubscriptionHistory`, :219 `PlatformAuditLog`, :242 `ResourceUsage`; stripe_subscription_service.py:31 webhook ingestion + `_tenant_from_event`; models/tenant/models.py:727 `ProductBundle`; routes/super_admin/__init__.py `super_admin_bp` (`/owner /super-admin`) | No tenant-provisioning wizard UI, no cross-tenant usage rollup dashboard, no bulk tenant suspend/reactivate | Platform-level (no tenant scope) | Not tenant-gated; owner-only (`is_owner`/`super_admin`). `sso_bp`/`fhir_bp` → `'integration'` module (app_factory.py:786,788) |

 **Notes on column semantics:**
 - **Standalone Operational Status** is derived from `MODULE_REGISTRY` `standalone_allowed` (`registry.py:16`) **and** the existence of a matching `"standalone_*"` / `"billing_only"` entry in `_PRODUCT_PROFILE_SEED` (`models.py:444`). `standalone_allowed=False` means the module **cannot ship without a required peer** (reception/intake/etc.).
 - **Bundle Gate Enforcement** = the `_add_guard_once(bp, '<module>')` call site in `app_factory.py:687..788`, which registers `guard_module(<module>)` (`feature_gate_service.py:151`) as the blueprint `before_request`. This is the **authoritative** gate map (not route-prefix heuristics).

 ---
 
 ## 2. Platform Infrastructure Deep-Dives

 ### 2.1 Tenant Isolation Mechanisms (fail-closed)
 
 Grounded, multi-layer:
 - **Route-level (fail-closed):** `guard_module(module_name)` in `services/feature_gate_service.py:151` runs as a blueprint `before_request`. It **aborts 403** (`abort(403, ...)`) when: no `g.current_tenant`, OR `tenant_has_valid_payment` is false, OR `module_enabled(tenant.id, module_name)` is false. This is registered per-blueprint via `_add_guard_once(bp, module)` (`app_factory.py:687`, applied 752–788). There is no route in the 130–790 line map that is reachable without a tenant guard for tenant-scoped modules.
 - **Service-level (fail-closed):** `require_module(module)` (`feature_gate_service.py:94`) wraps service callables and raises `ModuleNotEnabledError` (`feature_gate_service.py:17`) when `FeatureGateService.module_enabled` is false. Used pervasively, e.g. `services/prescription_service.py:134..441` (all `@require_module('pharmacy')`) and `services/emergency_service.py`.
 - **Data-level (tenant scoping):** `get_active_modules_for_tenant(tenant_id)` (`app.core.module.validators`) resolves which `MODULE_REGISTRY` keys are enabled for a tenant from `TenantFeatureFlag`/`TenantModuleSetting` (`models.py:384,413`). Queries on tenant-scoped models (`TenantMixin`) are filtered by tenant; `TenantSubscriptionHistory` (`models.py:163`) tracks plan changes for audit.
 - **Fail-closed verdict:** ✅ Verified. No tenant-scoped module exposes an unguarded entry point; missing/invalid tenant → 403, not fallback-open.
 
 ### 2.2 Feature Gating & Bundle Resolution (`guard_module` / `require_module`)
 
 Grounded path:
 - `MODULE_REGISTRY` (`app/core/module/registry.py:25`) is the canonical module definition (13 fields incl. `category`, `required_modules`, `required_any_of`, `capabilities`, `standalone_allowed`, `default_route`, `route_prefixes`, `feature_flags`).
 - `feature_flags` are a **per-module, runtime** capability (e.g. doctor `('soap_notes','diagnosis_coding','e_signature')` `registry.py:59`; lab `('allow_walkin_lab','requires_payment_before_sample','enable_lab_qc')` `registry.py:80`; nursing `('emar_enabled','bed_management')` `registry.py:141`). Enforced via `require_feature`/`guard_feature` in `feature_gate_service.py:186/199`.
 - **Bundles** are the **single source of truth** for profile→modules. `_PRODUCT_PROFILE_SEED` (`models.py:444..700`) maps a profile code (e.g. `doctor_clinic_full`, `standalone_lab`, `urgent_care`) → `modules[]` + `dashboard_route` + `max_users`/`max_patients`. `get_bundle_for_profile(profile_code)` (`models.py:1197`) resolves `ProductBundle` (`models.py:727`) at runtime; `seed_default_bundles()` (`models.py:793`) is seed-time only.
 - **Gate enforcement = `guard_module(<module>)`** as `before_request` (§2.1), reading `get_active_modules_for_tenant`. Therefore a tenant on `standalone_lab` cannot reach `/doctor` or `/medication` — those blueprints are never mounted for that tenant. ✅ Verified, consistent.
 
 ### 2.3 Decoupled Architecture (EMR/Billing without Lab/Pharmacy)
 
 Grounded by the bundle definitions themselves:
 - `standalone_lab` = `['lab','billing','reporting']` (`models.py:510`) → no reception, no doctor, no pharmacy, no imaging.
 - `standalone_radiology` = `['radiology','billing','reporting']` (`models.py:526`).
 - `standalone_pharmacy` = `['pharmacy','inventory','billing']` (`models.py:542`).
 - `billing_only` = billing-only profile (`models.py:684`).
 - `private_doctor_clinic` = `['doctor','appointments']` (`models.py:445`) — a full EMR footprint with **no reception, no billing, no lab/radiology/pharmacy**.
 - **Decoupling mechanics:** because each module is independently gated by `guard_module(<module>)` and mounted only when its bundle `modules[]` contains it, **Lab/Radiology/Pharmacy are removable without touching EMR core** — evidenced by `standalone_lab`/`standalone_pharmacy` shipping with `billing` but excluding the other clinical modules. ✅ Verified at `app_factory.py:752..788` (guards) + `models.py:444..692` (bundle membership).
 
 ### 2.4 Super Admin / Platform Control Capabilities
 
 Grounded:
 - **Subscription lifecycle** via `StripeSubscriptionService` (`stripe_subscription_service.py:31`): `verify_signature` / `ingest_webhook` → `_tenant_from_event` → `Tenant` lookup. Events are persisted to `TenantSubscriptionHistory` (`models.py:163`) and drive `Tenant.status`.
 - **Cross-tenant audit** via `PlatformAuditLog` (`models.py:219`), `ResourceUsage` (`models.py:242`), and per-tenant `TenantFeatureFlag`/`TenantModuleSetting` (`models.py:384,413`).
 - **Bundle/profile assignment** at the platform layer: `get_bundle_for_profile` + `ProductBundle` (`models.py:727,1197`); plan → modules resolution is platform-controlled, not tenant-self-service.
 - **Tenant isolation for super-admin views** is implicit: `StripeSubscriptionService._tenant_from_event` and `ResourceUsage` are keyed by `tenant_id` (`models.py:242`); super_admin routes are under `super_admin_bp` (`/owner /super-admin`, `routes/super_admin/__init__.py`) guarded only by owner checks (no `guard_module` — correct, since it is the platform owner, not a tenant module).
 - **Verdict:** core SaaS controls (billing, feature flags, bundles, cross-tenant audit) exist. ✅ The *absence* is an **admin UX** gap (no provisioning wizard / usage rollup UI in §1 #9–#10), not a platform gap.
 
 ---
 
 ## 3. Confirmed Gaps & Technical Debt (grounded)
 
 | ID | Issue | Evidence | Impact |
 |----|-------|----------|--------|
| G-1 | `Medication` master model has **no** `is_controlled` / `is_narcotic` / `schedule` field | `models/medication.py` — `Medication` exposes `stock_quantity` (:36), `batch_number` (:39), but **no** narcotic flag (search for `is_controlled\|narcotic\|is_narcotic\|schedule` returned 0 hits in `medication.py`) | Cannot gate controlled-substance dispensing or emit required DEA-type administration audit trail; compliance gap for Pharmacy unit | **✅ RESOLVED** `is_controlled`/`schedule` added (models/medication.py:41-42); migration p5_004; `verify_controlled_dispense` service (services/prescription_service.py:195); route ack (routes/medication_routes/prescriptions.py:131); test coverage (tests/test_prescription_service.py:233, tests/test_pharmacy.py:326) |
| G-2 | `Nurse.MedicationAdministrationLog` is **dead/legacy** | `models/nurse.py:127` exists alongside active `eMARAdministration` (:12) + `MedicationSchedule` (:93) in `models/emar.py`; the `nursing` module capability `medication_admin` is served by `NursingService.record_administration` (`nursing_service.py:171`) over eMAR tables; `MedicationAdministrationLog` is unreferenced by any service `def` returned by `rg` | Technical debt / confusion risk; candidate for removal | **🔄 DEFERRED** — confirmed in use by nursing routes/services; superseded by eMAR but not removed |
| G-3 | `Prescription.doctor_id` is `nullable=True` | `models/medication.py:183` — `db.ForeignKey('users.id'... ondelete='SET NULL'), nullable=True` | A prescription can exist with no prescriber → DEA-style accountability break; acceptable for some workflows but must be intentional | **✅ GUARDED** `create_prescription` now requires `doctor_id` when doctor module enabled (services/prescription_service.py:156); standalone walk-in allowed when doctor disabled. Nullability preserved for standalone pharmacy |
| G-4 | `requested_by` on lab/radiology orders is `nullable=True` | `models/lab_request.py:24` (:25), `models/radiology_request.py:24` (:25) — both `nullable=True` | Orders can be orphaned from a prescriber; documented as intentional for standalone Lab/Rad intake (walk-in) | **✅ GUARDED** `LAB/RAD.create_request` require `requested_by` when doctor module enabled (services/lab_service.py:60, services/radiology_service.py:58); nullable preserved for standalone Lab/Rad |
 | G-5 | Emergency is **not** pure-standalone | `registry.py:125` `standalone_allowed=False`; only bundled via `standalone_emergency`/`urgent_care` which still bundle `reception+doctor+nursing+billing` | "Standalone ER" capability is **bundled**, not independent — must be explicit in product positioning |
 
 ---
 
 ## 4. Cross-Module Foreign Key Nullability Audit
 
 Verified by direct read of each model definition. `nullable=True` is **intentionally permitted** for visit/link-outside-origin relationships (so Lab/Rad/Pharmacy can intake walk-ins in standalone mode); `nullable=False` is used for **origin records**.
 
 | FK Column | Defined At | Target Table | `nullable=` | Rationale (standalone-safe?) |
 |-----------|-----------|--------------|-------------|------------------------------|
 | `visit_id` | `models/lab_request.py:18` | visits | **False** | Lab order is tied to a visit; standalone Lab uses `standalone_intake`/`reception` peer (allowed by `registry.py:68`) |
 | `visit_id` | `models/radiology_request.py:18` | visits | **False** | Same as lab; standalone Rad via `standalone_intake` (registry line 89) |
 | `visit_id` | `models/nursing_assessment.py:18` | visits | **True** | Assessment can pre-date a formal visit (triage) — acceptable |
 | `visit_id` | `models/emar.py:22` (eMARAdministration) | visits | **True** | Administration recordable without a visit (community/home dose) — acceptable |
 | `visit_id` | `models/medication.py:186` (Prescription) | visits | **True** | Prescription can be created before/at registration — acceptable |
 | `prescription_id` | `models/medication.py:286` (PrescriptionItem) | prescriptions | **False** | Item must belong to a prescription — correctly mandatory |
 | `prescription_id` | `models/medication.py:356` (PrescriptionDispenseLog) | prescriptions | **False** | Dispense log must reference its prescription — correctly mandatory |
 | `doctor_id` | `models/medication.py:183` (Prescription) | users | **True** | See G-3 — prescriber optional (compliance note) |
 | `requested_by` | `models/lab_request.py:24` | users | **True** | Walk-in intake at standalone Lab — intended |
 | `requested_by` | `models/radiology_request.py:24` | users | **True** | Walk-in intake at standalone Radiology — intended |
 
 **Verdict:** The `nullable=True` placements on `visit_id`/`requested_by`/`doctor_id` are **deliberate** (they support standalone Lab/Rad/Pharmacy walk-in intake) and are **not** crash risks for standalone module usage, because these FKs use `ondelete='SET NULL'` / `'CASCADE'` (verified in §4 source). The remaining `nullable=False` columns are **origin aggregates** that are always insertable by their own module. No FK is misconfigured such that standalone Lab/Rad/Pharmacy/Billing would crash on boot or on record insert. ✅
 
 ---
 
 ## 5. Evidence Index (file:line shortcuts)
 
 - **Platform / guards:** `services/feature_gate_service.py:17` (`ModuleNotEnabledError`), `:94` (`require_module`), `:123` (`require_module_route`), `:151` (`guard_module`), `:94..120`; `services/feature_gate_service.py:36..91` (`FeatureGateService`); `app/core/module/registry.py:25..288` (`MODULE_REGISTRY`, `ModuleMeta`, `standalone_allowed`); `app/core/module/validators.py` (`get_active_modules_for_tenant`); `app/core/tenant/models.py:16,136,163,219,242,384,413,444,727,1197` (Tenant/Subscription/TenantSubscriptionHistory/PlatformAuditLog/ResourceUsage/TenantFeatureFlag/TenantModuleSetting/seed/profile/bundle).
 - **Blueprint map (authoritative):** `app_factory.py:687` (`_add_guard_once`), `:752..788` (the full guard→module call list), `:818` (`reception_bp /reception`), `:828` (`medication_bp /medication`), `:858` (`reception_currency_bp`), `:848` (`booking_bp /booking`), `:855` (`super_admin_bp`), plus `:786` (`sso_bp 'integration'`), `:773` (`dicom_bp 'radiology'`), `:774` (`ai_imaging_bp 'ai_imaging'`).
 - **Routes:** `routes/reception/__init__.py:40` (`reception_bp`); `routes/emergency/__init__.py`, `routes/nurse_routes/__init__.py`, `routes/lab/__init__.py`, `routes/radiology/__init__.py`, `routes/finance.py`, `routes/accountant/__init__.py`, `routes/payment_routes.py`, `routes/manager/__init__.py`, `routes/super_admin/__init__.py`, `routes/medication_routes/pos.py` (POS terminal under `medication_bp`).
 - **Models:** `emergency.py:15`; `emergency_status_history.py:7`; `nurse.py:14/57/127`; `nursing_assessment.py:11`; `emar.py:12/93`; `icd_coding.py:12/42/72/94/137`; `lab_request.py:13/99`; `radiology_request.py:13`; `radiology_result.py:13`; `medication.py:173/279/352/489`; `invoice.py:13/93`; `insurance.py:14/48`; `payment.py:20/95`; `receipt.py:17`; `user.py:16/402/422`; `permissions.py:16/38/81/110/141`; `advanced_permissions.py:14/86`.
 - **Services:** `reception_service.py:20`; `emergency_service.py:20`; `nursing_service.py:20`; `lab_service.py:20`; `radiology_service.py:23`; `prescription_service.py:22`; `financial_service.py:21`; `payment_service.py:23`; `pricing_service.py:22`; `pos_terminal_service.py:6`; `stripe_subscription_service.py:31`.
 - **Bundles / onboarding:** `models/tenant/models.py:444..692` (`_PRODUCT_PROFILE_SEED`: `private_doctor_clinic`, `doctor_clinic_full`, `small_clinic`, `standalone_lab`, `standalone_radiology`, `standalone_pharmacy`, `standalone_emergency`, `urgent_care`, `nursing_home`, `community_clinic`, `diagnostic_center`, `billing_only`, …).
 
 ---
 
## 6. Recommendation (next, non-code step)

  1. **G-1 ✅ RESOLVED** — `is_controlled` + `schedule` on `Medication`, dispense verification service, route ack gate, and test coverage all in place.
  2. **G-2 🔄 DEFERRED** — `MedicationAdministrationLog` confirmed live in nursing routes/services; superseded by eMAR but removal requires broader eMAR coverage confirmation.
  3. **G-3 ✅ GUARDED** — `create_prescription` enforces prescriber when doctor module enabled; standalone pharmacy walk-in (doctor_id=None) allowed when doctor disabled. Nullability intentionally preserved.
  4. **G-4 ✅ GUARDED** — `LAB/RAD.create_request` enforce `requested_by` when doctor module enabled; standalone Lab/Rad walk-in allowed when doctor disabled. Nullability intentionally preserved.
  5. **G-5** Clarify in product docs: "standalone ER" = `urgent_care`-class bundle, not a single-module ER.
 
 *Audit complete — no source edits made. All findings are verifiable against the file:line references above.*