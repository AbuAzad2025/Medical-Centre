# Phase 3 Gap Audit — Baseline Inspection Report

Date: 2026-08-05

---

## TRACK 1: Pre-Existing Test Failures — RESOLVED

All 5 pre-existing failures have been fixed (commit `c00aa8f`):

| Test | Root Cause | Fix |
|------|-----------|-----|
| `test_create_sale_final_commit_failure` | Mock of `db` broke medication lookup before final commit | Changed to patch `safe_commit` directly |
| `test_void_sale_success` | `PharmacySaleService.void_sale()` did not exist | Implemented `void_sale()` method |
| `test_void_sale_not_found` | Same | Same |
| `test_prescription_status_success` | `PharmacySaleService.get_prescription_status()` did not exist | Implemented `get_prescription_status()` method |
| `test_prescription_status_not_found` | Same | Same |

**Result: 23/23 tests passing in `test_sale_service_chunk3.py`**

---

## TRACK 2: Phase 3 Baseline Inspection

### Area 1: Insurance & Claims Engine

#### Existing Models

| File | Model | Purpose |
|------|-------|---------|
| `models/insurance.py` | `InsuranceCompany` | Insurance company registry (active, used in visits/payments) |
| `models/insurance.py` | `InsuranceClaim` | **Dead model** — defined with `claim_number`, `status`, `total_claim`, `approved_amount` but never referenced by routes, services, or tests |
| `models/invoice.py` | `Invoice` | Invoice lifecycle (DRAFT → ISSUED → PAID → VOID) with line items |
| `models/invoice.py` | `InvoiceService` | Invoice line items |
| `models/payment.py` | `Payment` | Payment with idempotency, cancellation, refund support |
| `models/payment.py` | `PaymentCard` | Stored card vault with encryption |
| `models/receipt.py` | `Receipt` | Receipt issuance with insurance fields (computed, not claim-linked) |
| `models/refund_request.py` | `RefundRequest` | Refund workflow (Request → Approval → Execution) |
| `models/pricing.py` | `InsuranceProvider` | Legacy insurance provider with `coverage_percentage`, `calculate_coverage()` |
| `models/pricing.py` | `PricingCatalog` | Per-service pricing with `insurance_coverage` and `patient_share` |
| `models/pricing_management.py` | `PricingManagement` | Per-service pricing with discounts/taxes |
| `models/pricing_management.py` | `PricingRule` | Dynamic pricing rules |
| `models/visit.py` | `Visit` | Has insurance fields (`insurance_company_id`, `insurance_policy_number`, `insurance_coverage_percentage`, `insurance_amount`, `patient_share`) |

#### Existing Services

| File | Service | Key Methods |
|------|---------|-------------|
| `services/billing_state_service.py` | `BillingStateService` | `get_billing_state()`, `can_checkout()` |
| `services/billing_state_service.py` | `ReceiptService` | `issue_receipt()`, `mark_printed()`, `void_receipt()` |
| `services/billing_state_service.py` | `PaymentAllocationService` | `allocate()` (FIFO) |
| `services/financial_service.py` | `FinancialService` | Dashboard stats, reconciliation, invoice creation, payment recording |
| `services/payment_service.py` | `PaymentService` | Idempotency-aware payment creation |
| `services/refund_service.py` | `RefundService` | `request_refund()`, `approve_refund()`, `reject_refund()`, `execute_refund()` |
| `services/pricing_service.py` | `PricingService` | Pricing lookup, visit cost calculation |
| `services/gatekeeper_service.py` | `GatekeeperService` | `validate_insurance()`, `validate_payment_method()` |

#### Existing Routes

| File | Routes |
|------|--------|
| `routes/payment_routes.py` | Payment processing, refund workflow, POS lookup, pharmacy returns |
| `routes/reception/payments.py` | POS charge, receipt/invoice printing, cash register |
| `routes/finance.py` | Finance dashboard, GL posting, payments/invoices listing |
| `routes/manager/financial.py` | Settlements, budget, financial reports |
| `routes/accountant/financial.py` | Financial reports, daily summary |
| `routes/saas_billing_routes.py` | Stripe webhook and checkout (SaaS only) |

#### Structural Gaps

1. **`InsuranceClaim` is a dead model** — completely unimplemented with zero routes, services, or tests
2. **No claim submission workflow** — no service or route to create, submit, or track insurance claims
3. **No insurance claim status tracking on invoices** — `Invoice` has no link to `InsuranceClaim`
4. **No insurance payout/reconciliation model** — no model for tracking insurer payouts or claim adjustments
5. **`InsuranceProvider` is a legacy duplicate** of `InsuranceCompany` — separate model with no FK relationship, not integrated with claim/payment workflow
6. **No pre-authorization workflow** — `InsuranceProvider.requires_authorization` field exists but no workflow implements it
7. **No claim adjustment/denial management** — no support for partial claims, adjustments, appeals, or resubmission
8. **No EOB (Explanation of Benefits) model** — no model for insurer response data
9. **No insurance-specific billing reports** — financial reports show insurance as a payment method category but lack claims-level reporting
10. **No external insurance API integration** — no service for 270/271 inquiries, 837 claims, or 835 ERA processing
11. **`Invoice.status` lacks insurance-specific states** — no "insurance pending" or "insurance partially paid" states
12. **`Payment.method = INSURANCE` is a single catch-all** — no differentiation between insurers, policies, or claim numbers
13. **No deductible/co-pay/co-insurance tracking** — receipt insurance fields are simple percentage calculations
14. **No aging/accounts receivable** — no model or service for unpaid invoice or claim aging
15. **`PricingCatalog` insurance fields are per-service, not per-plan** — no insurance contract/plan concept
16. **No batch claim submission** — no capability for clearinghouse batch uploads
17. **No claim attachment/document management** — no way to attach supporting documents to claims
18. **No claim reversal workflow** — `RefundService` handles payment refunds but not claim reversals
19. **Insurance payments allocated via FIFO** — should be allocated to specific claims, not oldest invoices first
20. **No tests for insurance claim functionality**

#### Proposed Extension Points (existing files only)

- **`models/insurance.py`**: Activate `InsuranceClaim` model; add `InsuranceClaimLine` for claim line items; add `InsurancePayout` model for insurer payments; add `EOB` model for Explanation of Benefits
- **`services/`**: Add `InsuranceClaimService` in a new file or extend `financial_service.py`; add claim submission, status tracking, and reconciliation methods
- **`routes/`**: Add claim CRUD routes to `routes/payment_routes.py` or a new `routes/insurance.py`; add insurance-specific report routes to `routes/manager/financial.py`
- **`app/shared/enums.py`**: Extend `InsuranceClaimStatus` with additional states; add `ClaimAdjustmentReason` enum

---

### Area 2: Lab & Radiology Orders

#### Existing Models

| File | Model | Purpose |
|------|-------|---------|
| `models/lab_request.py` | `LabRequest` | Lab order with status (REQUESTED→COLLECTED→RECEIVED→ANALYZING→REVIEWED→APPROVED→IN_PROGRESS→DONE→CANCELLED) |
| `models/lab_request.py` | `LabResult` | Individual test result with value, unit, reference range, status (PENDING→READY→VALIDATED) |
| `models/lab_test_catalog.py` | `LabTestCatalog` | Catalog of available lab tests |
| `models/lab_reagent.py` | `LabReagent` | Lab reagent inventory |
| `models/lab_quality.py` | `LabQualityControlEntry` | QC entries for lab quality control |
| `models/radiology_request.py` | `RadiologyRequest` | Radiology order with status (REQUESTED→IN_PROGRESS→DONE→CANCELLED), modality (XRay|CT|MRI|US) |
| `models/radiology_result.py` | `RadiologyResult` | Radiology result entries |

#### Existing Services

| File | Service | Key Methods |
|------|---------|-------------|
| `services/lab_service.py` | `LabService` | `create_request()`, `get_worklist()`, `get_request_counts()`, `get_request_by_id()`, `get_results_by_request()`, `create_results_from_form()`, `validate_lab_results()`, `finalize_results()`, QC management, reagent management, notifications |
| `services/radiology_service.py` | `RadiologyService` | Radiology order and result management (details not fully explored) |

#### Existing Routes

| File | Routes |
|------|--------|
| `routes/lab/worklist.py` | Lab worklist views |
| `routes/lab/test_catalog.py` | Test catalog management |
| `routes/lab/reports.py` | Lab report views |
| `routes/lab/reagents.py` | Reagent management |
| `routes/lab/quality.py` | QC management |
| `routes/lab/fhir.py` | FHIR integration for lab |
| `routes/lab/dashboard.py` | Lab dashboard |
| `routes/lab/barcode.py` | Barcode generation |
| `routes/radiology/worklist.py` | Radiology worklist |
| `routes/radiology/requests.py` | Radiology request management |
| `routes/radiology/reports.py` | Radiology report views |
| `routes/radiology/templates.py` | Radiology templates |
| `routes/radiology/quality.py` | Radiology QC |
| `routes/radiology/images.py` | DICOM image management |
| `routes/radiology/fhir.py` | FHIR integration for radiology |
| `routes/radiology/dashboard.py` | Radiology dashboard |

#### Structural Gaps

1. **No lab order status transitions via state machine** — `LabRequest.status` is a free-form string; no service validates or enforces valid transitions (e.g., cannot go from REQUESTED directly to DONE)
2. **No radiology order status transitions via state machine** — same issue as lab
3. **No lab order result validation service** — `LabService.validate_lab_results()` is basic (only checks test name and unit presence); no range validation, critical value alerts, or auto-flagging
4. **No critical value notification workflow** — `LabResult.is_critical` field exists but no service or route triggers alerts for critical values
5. **No lab order cancellation workflow** — `LabRequest.status` supports CANCELLED but no service method to cancel an order
6. **No radiology order cancellation workflow** — same gap
7. **No result amendment/history tracking** — `LabResult` has no audit trail for value changes; no versioning
8. **No lab order priority/urgency field** — no way to flag urgent lab orders
9. **No radiology order priority/urgency field** — same gap
10. **No specimen tracking model** — no model for tracking specimen collection, labeling, or chain of custody
11. **No instrument integration service** — no service for receiving results from lab instruments (interface with lab analyzers)
12. **No lab order auto-creation from visit** — no service to auto-generate lab orders based on diagnosis or visit type
13. **No radiology order auto-creation from visit** — same gap
14. **No lab/radiology order linking** — no way to link a lab order to a radiology order (e.g., for contrast studies requiring lab work first)
15. **No pending results notification service** — `LabService.notify_results_ready()` exists but is basic; no push notification, SMS, or email integration
16. **No lab/radiology reporting service** — no service for generating lab/radiology reports (e.g., turnaround time, volume metrics)
17. **`LabService.finalize_results()` uses `safe_commit` without `reraise=True`** — errors are silently swallowed
18. **No test coverage for lab/radiology services** — no unit tests found for `LabService` or `RadiologyService`

#### Proposed Extension Points (existing files only)

- **`models/lab_request.py`**: Add `priority` field, `cancelled_by`, `cancelled_at`, `cancellation_reason` fields to `LabRequest`; add `amended_by`, `amended_at` fields to `LabResult`; add `Specimen` model
- **`models/radiology_request.py`**: Add `priority` field, cancellation fields to `RadiologyRequest`
- **`services/lab_service.py`**: Add `cancel_request()`, `amend_result()`, `validate_critical_values()`, `get_turnaround_time_report()` methods
- **`services/radiology_service.py`**: Add `cancel_request()`, `validate_critical_values()` methods
- **`routes/lab/worklist.py`**: Add priority filtering, cancellation endpoints
- **`routes/radiology/requests.py`**: Add priority filtering, cancellation endpoints
- **`app/shared/enums.py`**: Add `LabRequestStatus` and `RadiologyRequestStatus` enums with validated transitions

---

### Area 3: Discharge & Transfer Workflows

#### Existing Models

| File | Model | Purpose |
|------|-------|---------|
| `models/visit.py` | `Visit` | Core visit record with status (OPEN→CHECKED_IN→IN_PROGRESS→COMPLETED→CANCELLED); has no inpatient-specific fields |
| `models/bed_management.py` | `Admission` | Core ADT record with `status` (ADMITTED→DISCHARGED→TRANSFERRED→DECEASED), `discharge_type`, `discharge_diagnosis`, `discharge_datetime` |
| `models/bed_management.py` | `BedTransfer` | Transfer between beds/wards with `transfer_type` (INTERNAL|INTER_WARD|ICU|DISCHARGE) |
| `models/bed_management.py` | `Ward` | Hospital ward (GENERAL, ICU, NICU, PICU, MATERNITY, SURGERY, ISOLATION) |
| `models/bed_management.py` | `Room` | Room within a ward |
| `models/bed_management.py` | `Bed` | Individual bed (AVAILABLE→OCCUPIED→RESERVED→CLEANING→OUT_OF_ORDER) |
| `models/visit_transfer.py` | `VisitTransferLog` | Department/doctor transfer log (no status, no approval workflow) |
| `models/emergency_status_history.py` | `EmergencyStatusHistory` | Audit trail for emergency case status changes |
| `models/workflow.py` | `PatientWorkflow`, `WorkflowStep`, `WorkflowTransfer`, `WorkflowQueue`, `VisitWorkflowEvent` | Generic workflow engine |
| `models/clinical_pathway.py` | `PatientCarePlan` | Care plans linked to visit/admission |

#### Existing Services

| File | Service | Key Methods |
|------|---------|-------------|
| `services/visit_state_machine_service.py` | `VisitStateMachineService` | `transition()`, `can_transition()`, `ensure_in_progress()`, `ensure_completed()`, `return_to_treatment()` |
| `services/visit_workflow_validator.py` | `VisitWorkflowValidator` | `can_transition()`, `get_available_transitions()`, `validate_and_transition()` (writes directly to `visit.status`, bypasses VSM) |
| `services/queue_management_service.py` | `QueueManagementService` | `transfer_visit()` (department transfer only, not bed/ward transfer) |
| `services/nursing_service.py` | `NursingService` | Vitals, notes, care plans, tasks (no discharge-specific workflows) |
| `services/gatekeeper_service.py` | `GatekeeperService` | `can_archive_visit()`, `archive_visit()` (financial checks, not discharge-specific) |
| `services/emergency_service.py` | `EmergencyService` | Emergency case management with `TRANSFERRED` status |

#### Existing Routes

| File | Routes |
|------|--------|
| `routes/bed_management_routes.py` | Read-only: dashboard, wards, rooms, admissions, available beds, bed status |
| `routes/doctor/visits.py` | `start-treatment`, `end-treatment`, patient details, visit summary |
| `routes/emergency/cases.py` | Case management, resolve, convert (department transfer) |
| `routes/nursing_assessment_routes.py` | Nursing assessments (Braden, Glasgow, Fall Risk, Pain, Norton) |
| `routes/reception/visits.py` | Visit management |
| `routes/nurse_routes/wards.py` | Ward management for nurses |

#### Structural Gaps

1. **No Admission Service Layer** — `Admission` model exists but no service to create admissions, process discharges, or manage transfers
2. **No Discharge/Transfer Routes** — `bed_management_routes.py` has only read-only GET routes; no POST/PUT for admit, discharge, or transfer
3. **Dual/Unsynchronized State Systems** — `Visit.status` (VisitState) and `Admission.status` (AdmissionStatus) are not integrated; a patient can be `Visit.status=COMPLETED` while `Admission.status=ADMITTED`
4. **Visit Model Has No Inpatient Concept** — `Visit` lacks `is_inpatient`, `admission_date`, `discharge_date`, `bed_id`, `ward_id` fields
5. **No Bed Occupancy Service** — `Bed` has `current_patient_id` and `status` but no service to assign/release beds
6. **No Length-of-Stay Calculation** — `Admission.length_of_stay` is defined but never populated
7. **No Discharge Type Validation** — `Admission.discharge_type` is free-form `String(50)` with no enum validation (values: HOME, TRANSFER, DEATH, AGAINST_ADVICE)
8. **No Discharge Summary Model** — no structured discharge summary; `discharge_diagnosis` is free text only
9. **No Transfer Workflow Service** — `BedTransfer` and `VisitTransferLog` exist but no service to orchestrate transfers (request, approve, execute, log)
10. **No Inpatient-Specific Workflow** — missing admission orders, transfer orders, discharge planning, bed assignment logic, ward transfer coordination
11. **No Emergency-to-Inpatient Admission Flow** — emergency cases can be `TRANSFERRED` but no workflow to convert to inpatient admission
12. **No Against-Advice Discharge Workflow** — `AGAINST_ADVICE` discharge type has no form, route, or service
13. **No Death Discharge Workflow** — `DECEASED` status has no workflow (death certificate, autopsy, next-of-kin notification)
14. **No Readmission Tracking** — `READMISSION` admission type has no detection, flagging, or tracking logic
15. **No Financial Discharge Integration** — discharge has no connection to final billing, insurance claim submission, or patient financial clearance
16. **No Nursing Discharge Checklist** — no discharge readiness assessment, patient education documentation, or medication reconciliation at discharge
17. **No Admission-Discharge-Transfer Event Audit Trail** — emergency cases have `EmergencyStatusHistory` but no equivalent for admission/discharge/transfer events on `Admission`
18. **FHIR Inconsistency** — `fhir_service.py` checks `visit.status == 'DISCHARGED'` but `Visit.status` never uses `'DISCHARGED'` (uses `'COMPLETED'` instead)
19. **`VisitWorkflowValidator` bypasses `VisitStateMachineService`** — writes directly to `visit.status`, creating an architectural inconsistency
20. **No Arabic labels for `AdmissionStatus`** values in `enum_labels.py`
21. **No test coverage for admission/discharge/transfer workflows**

#### Proposed Extension Points (existing files only)

- **`models/bed_management.py`**: Add `DischargeSummary` model; add `discharge_type` enum validation; add `length_of_stay` auto-calculation; add `readmission_flag` and `readmission_reason` fields to `Admission`
- **`models/visit.py`**: Add `is_inpatient`, `admission_date`, `discharge_date`, `bed_id`, `ward_id` fields
- **`services/`**: Add `AdmissionService` with `create_admission()`, `process_discharge()`, `process_transfer()`, `calculate_length_of_stay()`, `validate_discharge_type()` methods; add `BedOccupancyService` with `assign_bed()`, `release_bed()`, `check_availability()` methods
- **`routes/bed_management_routes.py`**: Add POST routes for admit, discharge, transfer; add PUT routes for bed status changes
- **`routes/doctor/visits.py`**: Add discharge-related routes (discharge summary, against-advice discharge, death discharge)
- **`routes/nurse_routes/`**: Add discharge checklist, discharge planning routes
- **`app/shared/enums.py`**: Add `DischargeType` enum (HOME, TRANSFER, DEATH, AGAINST_ADVICE); add `AdmissionStatus` labels; add `VisitState` ADT states (ADMITTED, DISCHARGED, TRANSFERRED)
- **`services/visit_state_machine_service.py`**: Extend `VisitStateMachineService` to support ADT states and integrate with `Admission` status changes
- **`services/visit_workflow_validator.py`**: Integrate with `VisitStateMachineService` instead of bypassing it
