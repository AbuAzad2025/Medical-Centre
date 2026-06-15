# خطة تحسين منطق وتجربة استخدام النظام الطبي

**اسم الخطة:** Medical Center Workflow & UX Logic Improvement Plan  
**الإصدار:** v4 - Full-System Ideal Architecture & Component Integration Roadmap  
**التاريخ:** 2026-06-16  
**أُعدت بواسطة:** GPT-5.5 Thinking  
**النطاق:** تحليل وخطة تحسين شاملة لمكونات النظام الطبي كاملة: SaaS, Tenants, Modules, Backend, Frontend, Workflows, Permissions, Clinical, Lab, Radiology, Pharmacy, Billing, Reports, Files, Notifications, AI, Inventory, Patient Portal، بدون تعديل كود تنفيذي في هذه المرحلة.

---

## 0. الهدف التنفيذي

الهدف لم يعد فقط تحسين شاشة زيارة أو طابور، بل الوصول إلى **منصة طبية مثالية قابلة للبيع كوحدات مستقلة أو باقات مركبة**، مع تكامل كامل بين الباكند والفرونتند والأقسام والـ SaaS Tenants.

النظام يجب أن يدعم هذه السيناريوهات بدون كسر منطق العمل:

1. طبيب بعيادة خاصة.
2. عيادة صغيرة باستقبال وطبيب وفوترة.
3. مختبر مستقل فقط.
4. مركز أشعة مستقل فقط.
5. صيدلية مستقلة فقط.
6. مركز طبي كامل بعدة أقسام.
7. مركز يحتوي أقساماً محددة فقط.
8. منصة SaaS متعددة Tenants مع تفعيل/تعطيل وحدات من Owner/Super Admin.
9. نظام standalone غير SaaS عند الحاجة.

المبدأ الحاكم:

```text
كل ميزة يجب أن تكون:
tenant-aware + module-aware + role-aware + workflow-aware + frontend-aware
```

---

## 1. الملفات والمكونات التي تم فحصها

### SaaS / Platform

- `app/core/tenant/models.py`
- `app/core/tenant/middleware.py`
- `app/core/module/models.py`
- `app/core/module/registry.py`
- `app/core/module/validators.py`
- `app/shared/enums.py`
- `app/modules/owner/routes.py`
- `app_factory.py`
- `templates/partials/sidebar.html`

### Core Medical

- `models/patient.py`
- `models/visit.py`
- `models/appointment.py`
- `models/online_booking.py`
- `models/department.py`
- `models/medical_record.py`
- `models/workflow.py`
- `models/request_workflow.py`
- `models/visit_transfer.py`

### Departments

- `models/queue_management.py`
- `models/nurse.py`
- `models/emergency.py`
- `models/lab_request.py`
- `models/lab_quality.py`
- `models/lab_reagent.py`
- `models/radiology_request.py`
- `models/radiology_test.py`
- `models/medication.py`
- `app/modules/workflows/stock_models.py`

### Finance / Billing

- `models/payment.py`
- `models/invoice.py`
- `models/service.py`
- `routes/payment_routes.py`
- `services/gatekeeper_service.py`

### Access / Security / Operations

- `models/user.py`
- `models/permissions.py`
- `models/advanced_permissions.py`
- `models/user_department_access.py`
- `models/file_management.py`
- `models/notification.py`
- `models/reporting.py`
- `models/ai_analytics.py`
- `models/task_management.py`

### Main Routes / Frontend

- `routes/reception.py`
- `routes/doctor.py`
- `routes/nurse_routes.py`
- `routes/lab.py`
- `routes/radiology.py`
- `routes/medication_routes.py`
- `routes/payment_routes.py`
- `templates/reception/create_visit.html`
- `templates/partials/sidebar.html`

---

## 2. التشخيص العام بعد التوسع

النظام يحتوي على عدد كبير من المكونات القوية، لكنه يعاني من 4 مشاكل جذرية:

### 2.1 تكرار نماذج workflow

يوجد أكثر من اتجاه لإدارة سير العمل:

- `Visit.status`
- `QueueManagement.status`
- `WorkflowStep / PatientWorkflow / WorkflowQueue`
- `RequestWorkflow`
- `LabRequest.status`
- `RadiologyRequest.status`
- `Prescription.status`
- `OnlineBooking.status`
- `Payment.status`
- `Invoice.status`

هذا ليس خطأ برمجي بسيط، بل سبب مباشر للتناقض المنطقي. يجب توحيدها تحت محرك أعلى اسمه:

```text
Workflow Orchestrator
```

ويبقي النماذج الحالية كجداول تنفيذية أو history، لا كمصادر قرار مستقلة.

### 2.2 SaaS Modules موجودة لكن ليست مكتملة المنتج

يوجد `Tenant`, `SubscriptionPlan`, `TenantModule`, `MODULE_REGISTRY`, وguards لبعض الوحدات. لكن:

- بعض modules المتقدمة مسجلة كـ blueprints بدون module guard شامل.
- `MODULE_REGISTRY` يفرض reception على lab/radiology/pharmacy، وهذا يمنع standalone sales.
- الـ sidebar يخفي الروابط لكنه لا يكفي للحماية.
- لا يوجد Product Profile واضح للـ Tenant.

### 2.3 الصلاحيات موجودة لكنها غير موحدة مع modules الحديثة

يوجد:

- Role permissions.
- ModulePermission.
- DepartmentPermission.
- UserDepartmentAccess.
- AccessControlService.
- decorators.

لكن `ModulePermission` يستخدم قائمة modules قديمة مثل `accounting` ولا تغطي بشكل كامل `pharmacy`, `billing`, `nursing`, `appointments`, `inventory`, `portal`, `dicom`, `ai_imaging`, وغيرها. لذلك يجب بناء Authorization Matrix موحدة.

### 2.4 البيانات التشغيلية لا تزال تحتاج tenant scoping صارم

وجود `User.tenant_id` ليس كافياً. يجب أن تكون كل الجداول التشغيلية المهمة tenant-scoped أو مرتبطة بكيان tenant-scoped بشكل مضمون.

---

## 3. Product Profiles النهائية

بدلاً من بيع النظام كوحدة واحدة، يجب التعامل معه كباقات منتج.

| Profile | الهدف | Modules الأساسية | Modules اختيارية | Dashboard |
|---|---|---|---|---|
| `PRIVATE_DOCTOR_CLINIC` | طبيب منفرد | doctor, clinic_intake | appointments, billing, prescription_print | `/doctor/dashboard` |
| `SMALL_CLINIC` | عيادة صغيرة | reception, doctor | appointments, billing, reporting | `/reception/dashboard` |
| `STANDALONE_LAB` | مختبر فقط | lab, lab_intake | billing, inventory, reporting, portal | `/lab/worklist` |
| `STANDALONE_RADIOLOGY` | أشعة فقط | radiology, radiology_intake | dicom, ai_imaging, billing, reporting | `/radiology/worklist` |
| `STANDALONE_PHARMACY` | صيدلية فقط | pharmacy, pharmacy_pos, inventory | billing, reporting | `/pharmacy/pos` |
| `MULTI_DEPARTMENT_CENTER` | مركز كامل | reception, doctor, nursing, billing, queue | lab, radiology, pharmacy, emergency, appointments | `/reception/dashboard` أو `/manager/dashboard` |
| `CUSTOM` | حسب الطلب | حسب التفعيل | حسب التفعيل | يحدد من إعدادات Tenant |

---

## 4. Module Registry المثالي

### 4.1 المشكلة الحالية

`MODULE_REGISTRY` الحالي يعرف modules لكنه يستخدم `required_modules` فقط. هذا لا يكفي لمنصة ديناميكية.

### 4.2 الشكل المقترح

```python
@dataclass(frozen=True)
class ModuleMeta:
    name: str
    name_ar: str
    category: str
    required_modules: tuple[str, ...]
    required_any_of: tuple[tuple[str, ...], ...]
    capabilities: tuple[str, ...]
    standalone_allowed: bool
    default_route: str
    route_prefixes: tuple[str, ...]
    feature_flags: tuple[str, ...]
    description_ar: str
```

### 4.3 مثال lab

```python
"lab": ModuleMeta(
    name="lab",
    name_ar="المختبر",
    category="clinical",
    required_modules=(),
    required_any_of=(("reception", "lab_intake", "standalone_intake"),),
    capabilities=("patient_lookup", "lab_order", "sample_collection", "result_entry", "result_validation", "report_delivery"),
    standalone_allowed=True,
    default_route="/lab/worklist",
    route_prefixes=("/lab",),
    feature_flags=("allow_walkin_lab", "requires_payment_before_sample", "enable_lab_qc"),
    description_ar="طلبات التحاليل والعينات والنتائج والجودة"
)
```

### 4.4 قواعد التفعيل

- لا تفرض reception على module standalone.
- إذا Tenant profile = full center، reception/front_desk إلزامية.
- إذا module يتطلب capability، يكفي وجود وحدة توفر هذا capability.
- billing يجب أن يكون optional في workflow، لا hard dependency.
- كل تفعيل/تعطيل module يجب أن يسجل `PlatformAuditLog`.

---

## 5. Component Map شامل

### 5.1 Patient & Identity

الموجود:

- `Patient`
- `PatientAllergy`
- `PatientAccount`

المطلوب:

- `tenant_id` واضح.
- emergency contact.
- chronic conditions.
- current medications.
- blood type optional.
- consent records.
- patient merge/deduplication workflow.
- global patient search داخل Tenant فقط.

### 5.2 Appointments & Online Booking

الموجود:

- `Appointment`
- `OnlineBooking`
- `PaymentTransaction`

المشكلة:

- `Appointment` بسيط جداً.
- `OnlineBooking` لديه status/payment status منفصلة عن Payment/Billing.
- يجب وجود check-in service يحول online booking إلى appointment/visit بدون تكرار مريض.

المطلوب:

```text
Booking -> Appointment -> Check-in -> Visit/Order/Sale حسب profile
```

خدمة مقترحة:

```text
AppointmentCheckinService
OnlineBookingConversionService
```

### 5.3 Reception / Intake

بدلاً من reception واحدة ضخمة:

- `full_reception` للمراكز.
- `clinic_intake` للطبيب.
- `lab_intake` للمختبر.
- `radiology_intake` للأشعة.
- `pharmacy_customer_intake` للصيدلية.

كل intake يستخدم Patient Registry لكن بواجهة مختلفة.

### 5.4 Visit / Encounter

الموجود:

- `Visit` يحمل إداري + مالي + سريري.
- `MedicalRecord` عام.

المطلوب:

- `Visit` يبقى shell إداري.
- `ClinicalEncounter` للتوثيق السريري.
- `TriageAssessment` للتمريض.
- `VisitWorkflowEvent` للحالة.
- `ClinicalOrder` للطلبات.

### 5.5 Workflow & Queue

الموجود:

- `QueueManagement`
- `WorkflowStep`
- `PatientWorkflow`
- `WorkflowQueue`
- `RequestWorkflow`

المطلوب:

لا تحذف القديم فوراً. استخدم strategy:

1. اجعل `WorkflowOrchestrator` يقرأ ويكتب events.
2. اربط `QueueManagement` بالمحطات operational station.
3. استخدم `PatientWorkflow` كـ configuration/template أو legacy history بعد مراجعة الاستخدام.
4. وحد statuses.

محرك مقترح:

```text
WorkflowOrchestrator
  - create_case()
  - transition()
  - next_actions()
  - current_owner()
  - required_fields()
  - emit_event()
```

### 5.6 Doctor / Clinical Workbench

المطلوب:

- شاشة طبيب موحدة: Patient Context + Timeline + Current Encounter + Orders + Prescription.
- لا يظهر زر طلب مختبر/أشعة إلا إذا module enabled أو external referral enabled.
- SOAP note structured.
- diagnosis coding optional.
- e-signature/doctor signature.
- clinical close action.

### 5.7 Nursing / Triage / eMAR

الموجود:

- `VitalSigns` بدون `visit_id`.
- eMAR routes موجودة كـ blueprint.

المطلوب:

- `TriageAssessment.visit_id`.
- abnormal vitals alerts.
- nursing task queue.
- eMAR لا يظهر إلا إذا nursing + pharmacy + inpatient/center profile.

### 5.8 Lab

الموجود:

- LabRequest/LabResult.
- Lab QC.
- Lab Reagents.

المطلوب:

- standalone lab intake.
- lab order/order items.
- sample barcode.
- sample collected/received/rejected.
- QC linked to result validation.
- reagent consumption linked to lab tests.
- critical result notification to doctor or patient/referrer.
- report delivery portal.

### 5.9 Radiology

المطلوب:

- standalone radiology intake.
- modality/body part/protocol.
- DICOM optional module.
- AI imaging optional module.
- report draft/validate/sign.
- external referrer support.
- image/file attachments through FileService.

### 5.10 Pharmacy

الموجود:

- Medication.
- Prescription.
- PrescriptionItem.
- Dispense log.
- StockMovement للأدوية.

المطلوب:

- standalone pharmacy POS.
- sale without visit.
- prescription from internal doctor or external upload.
- stock ledger mandatory for every dispense/sale/return/adjustment.
- batch/expiry alerts.
- substitutions.
- controlled medication permissions if needed.

نماذج مقترحة:

```text
PharmacySale
PharmacySaleItem
PharmacyReturn
MedicationSubstitution
```

### 5.11 Billing / Finance

الموجود:

- Payment.
- Invoice.
- InvoiceService.
- GatekeeperService.
- OnlineBooking PaymentTransaction.

المشكلة:

- حالات الدفع موزعة.
- `receipt_number` لا يعني بالضرورة receipt printed.
- billing قد يكون module disabled.

المطلوب:

```text
BillingStateService
ReceiptService
InvoiceServiceLayer
PaymentAllocationService
```

قواعد:

- workflow لا يكسر عند عدم تفعيل billing.
- payment state موحد بين visit/payment/invoice/booking.
- debt/force/waiver لها approvals واضحة.
- receipt issued/printed/voided منفصلة.

### 5.12 Files / Attachments

الموجود:

- FileUpload.
- FilePermission.
- FileCategory.

المشاكل:

- hash يستخدم MD5.
- `file_path` مخزن محلياً.
- لا يظهر tenant_id.
- related_entity_type محدود.

المطلوب:

- SHA-256.
- tenant-aware storage path.
- StorageProvider: local/cloud/hybrid.
- malware scan hook.
- signed download URLs.
- attachment policies لكل module.
- audit عند view/download.

### 5.13 Notifications

الموجود:

- Notification.
- NotificationTemplate.
- NotificationQueue.
- WhatsAppMessage.

المطلوب:

- Event-driven notifications.
- Tenant notification settings.
- Templates per tenant/profile.
- Triggers:
  - appointment confirmed.
  - lab result ready.
  - radiology report ready.
  - payment due.
  - low stock.
  - critical result.
  - subscription expiring.

### 5.14 Reporting / Analytics

الموجود:

- Report.
- ReportExecution.
- ReportTemplate.
- AIRecommendation.
- PerformanceAnalytics.
- PatientInsight.

المطلوب:

- report scope by tenant/module/role.
- no cross-tenant reports except owner platform analytics.
- report datasets defined centrally.
- background execution for heavy reports.
- export audit.
- dashboards per product profile.
- separate clinical analytics from financial analytics.

### 5.15 Tasks / Projects

الموجود:

- Task.
- TaskComment.
- TaskAttachment.
- Project.

المطلوب:

- tasks linked to workflow events.
- auto-create tasks for pending approvals, critical lab, follow-up, low stock.
- tenant-scoped tasks.
- role-based task inbox.

### 5.16 AI / Decision Support

الموجود:

- AIRecommendation.
- DiseasePattern.
- PatientInsight.

المطلوب:

- AI must be advisory only.
- doctor acceptance/rejection audit.
- source_data must be structured and tenant-safe.
- no AI recommendations without sufficient context.
- feature flag per tenant.
- clinical disclaimers and validation.

---

## 6. Ideal Cross-System Architecture

### 6.1 Core layers

```text
Presentation Layer
  Templates / JS / Dynamic sidebar / Profile dashboards

Application Services
  VisitWorkflowService
  WorkflowOrchestrator
  FeatureGate
  TenantScope
  BillingStateService
  OrderService
  QueueService
  NotificationService
  ReportingService
  FileService

Domain Models
  Patient, Visit, Encounter, Orders, Payments, Inventory, Reports

Infrastructure
  DB, Storage, Email/SMS/WhatsApp, DICOM, FHIR, Audit, Background Jobs
```

### 6.2 كل request يجب أن يحمل

```text
g.current_tenant
g.tenant_id
g.enabled_modules
g.product_profile
g.feature_flags
g.user_scope
```

### 6.3 كل شاشة يجب أن تسأل

```text
هل module مفعلة؟
هل feature مفعلة؟
هل الدور مسموح؟
هل workflow يسمح بهذا action؟
ما data context المطلوبة؟
```

---

## 7. Corrective Action Plan للوصول لنظام مثالي

### Phase 0 — Full Route/Module Inventory

الهدف: لا يبقى أي route بلا module أو core classification.

Deliverables:

```text
docs/route-module-inventory.md
core/module_route_map.py
```

كل route يصنف:

- core
- owner
- auth
- reception
- doctor
- lab
- radiology
- pharmacy
- billing
- reporting
- inventory
- portal
- integration
- admin

### Phase 1 — Unified FeatureGate

إنشاء:

```text
services/feature_gate_service.py
```

وظائف:

```python
module_enabled(tenant_id, module)
feature_enabled(tenant_id, feature)
require_module(module)
require_feature(feature)
can_use(user, action)
```

وتوفير Jinja helpers:

```text
module_active()
feature_enabled()
can_use()
```

### Phase 2 — Product Profiles

إضافة:

```text
Tenant.product_profile_code
TenantModuleSetting
TenantFeatureFlag
```

وتحديث Owner UI:

- عند إنشاء tenant يختار profile.
- تظهر modules الافتراضية.
- يظهر تحذير dependencies.
- لا يسمح بتفعيل تركيبة غير منطقية.

### Phase 3 — Tenant Scope Hardening

- إضافة tenant_id للجداول التشغيلية الناقصة.
- تطبيق query scope.
- منع cross-tenant access.
- Owner فقط يستطيع analytics متعددة tenants.

### Phase 4 — Workflow Orchestrator

- لا تعتمد على route لتقرير الحالة.
- كل transition يسجل event.
- ربط Queue/Visit/Order/Billing بالـ orchestrator.

### Phase 5 — Billing Consistency

- توحيد Payment/Invoice/Visit/Booking status.
- Receipt service.
- Debt/waiver/force approvals.
- Billing optional mode.

### Phase 6 — Orders Service

- Unified clinical orders.
- منع تكرار lab/radiology.
- external referrals.
- module-aware order creation.

### Phase 7 — Department Workbenches

- Reception wizard.
- Doctor workbench.
- Nurse triage workbench.
- Lab worklist.
- Radiology worklist.
- Pharmacy POS/worklist.
- Accountant dashboard.

### Phase 8 — Portal / Booking / Notifications

- Convert booking to patient/appointment/visit/order based on profile.
- Patient portal scope.
- Notification triggers.

### Phase 9 — Files / Reports / Analytics

- FileService with tenant storage policy.
- Report scope engine.
- Module dashboards.
- AI governance.

### Phase 10 — Quality & Inventory

- Lab QC integration.
- Reagent stock movements.
- Medication stock ledger completeness.
- Low stock alerts.

---

## 8. تحسينات تفصيلية لكل Profile

### 8.1 Private Doctor Clinic

- شاشة واحدة للطبيب: اليوم، المواعيد، المرضى، كشف جديد.
- لا طابور معقد إذا الطبيب وحده.
- billing optional.
- prescription print حتى بدون pharmacy module.
- external lab/radiology referral print.

### 8.2 Standalone Lab

- `Lab Intake` بديل reception.
- إنشاء مريض سريع أو external patient.
- طلب تحاليل بدون زيارة طبيب.
- barcode sample.
- QC before validation.
- report delivery by portal/WhatsApp/PDF.
- billing optional.

### 8.3 Standalone Radiology

- radiology intake.
- external referring doctor.
- scheduling by modality.
- DICOM optional.
- AI imaging optional.
- report signed and delivered.

### 8.4 Standalone Pharmacy

- pharmacy POS.
- stock ledger mandatory.
- sale without visit.
- external prescription upload.
- batch/expiry.
- return/refund.
- low stock and reorder.

### 8.5 Full Center

- reception controls patient entry.
- triage configurable.
- doctor orders internal departments.
- departments return results.
- doctor review.
- pharmacy/checkout.
- archive.

---

## 9. Frontend مثالي

### 9.1 Dynamic Shell

- Sidebar بحسب modules.
- Topbar يعرض tenant/profile.
- Empty state عند module disabled.
- Upgrade CTA للـ owner/super_admin فقط.

### 9.2 Shared Components

```text
_patient_context_panel.html
_module_empty_state.html
_workflow_next_actions.html
_billing_status_badge.html
_order_status_badge.html
_attachment_panel.html
_audit_timeline.html
```

### 9.3 كل صفحة يجب أن تحتوي

- breadcrumb واضح.
- patient/tenant context إذا متعلق بمريض.
- next actions لا أزرار عشوائية.
- validation قبل submit.
- loading state.
- empty state.
- audit/info section للأحداث المهمة.

---

## 10. Backend Services النهائية المقترحة

```text
FeatureGateService
TenantScopeService
ProductProfileService
ModuleActivationService
WorkflowOrchestrator
VisitWorkflowService
QueueService
OrderService
BillingStateService
ReceiptService
ClinicalContextService
PermissionScopeService
AppointmentCheckinService
OnlineBookingConversionService
FileService
NotificationService
ReportScopeService
InventoryLedgerService
LabQualityService
PharmacySaleService
RadiologyWorkflowService
AIRecommendationGovernanceService
AuditEventService
```

---

## 11. Database / Model Corrections

### Must add or verify `tenant_id`

```text
patients
visits
appointments
online_bookings
payments
invoices
invoice_services
lab_requests
lab_results
radiology_requests
radiology_results
prescriptions
prescription_items
medications
stock_movements
queue_management
workflow_steps
patient_workflows
tasks
reports
file_uploads
notifications
service_master
departments
```

### Must normalize statuses

```text
VisitState
QueueState
OrderState
BillingState
AppointmentState
BookingState
PrescriptionState
ReportExecutionState
NotificationState
TaskState
```

### Must avoid generic strings where possible

- `related_entity_type` should be enum-like constants.
- `module_name` must match `MODULE_REGISTRY` exactly.
- `department_type` should replace name inference.

---

## 12. Security / Privacy / Compliance

- No clinical details in finance dashboards.
- No all-patient access for lab/radiology/pharmacy unless needed.
- File download audit.
- Report export audit.
- AI recommendation acceptance audit.
- Tenant isolation mandatory.
- Module disabled routes return 403, not hidden only.
- Sensitive settings encrypted.
- API keys must not be stored as plain JSON in SystemConfig long term.

---

## 13. Final Ideal-System Checklist

### SaaS

- [ ] Tenant profile exists.
- [ ] Modules active per tenant.
- [ ] Feature flags active per tenant.
- [ ] Every route mapped to module/core.
- [ ] Every module route guarded.
- [ ] Sidebar and buttons match backend permissions.

### Workflow

- [ ] One orchestrator controls transitions.
- [ ] No duplicate status logic in routes.
- [ ] Every transition has event.
- [ ] Queue station known.
- [ ] Next action clear in UI.

### Clinical

- [ ] Encounter structured.
- [ ] Vitals linked to visit.
- [ ] Allergies visible.
- [ ] Orders module-aware.
- [ ] Results review workflow clear.

### Finance

- [ ] Billing optional where allowed.
- [ ] Receipt states clear.
- [ ] Payment/Invoice/Visit states reconciled.
- [ ] Debt/waiver approvals audited.

### Standalone Modules

- [ ] Lab works without doctor/reception full.
- [ ] Radiology works without doctor/reception full.
- [ ] Pharmacy works without visit.
- [ ] Private doctor works without lab/radiology/nursing.

### Operations

- [ ] Files tenant-scoped and secure.
- [ ] Notifications event-driven.
- [ ] Reports scoped by tenant/role/module.
- [ ] Inventory ledgers complete.
- [ ] QC integrated.
- [ ] AI advisory and audited.

---

## 14. الترتيب النهائي للتنفيذ

ابدأ بهذا الترتيب، لأنه يمنع التكسير:

1. Route/module inventory.
2. FeatureGate + module route guards.
3. Product profiles + Tenant feature flags.
4. Tenant scoping hardening.
5. Status constants normalization.
6. Billing state consistency.
7. OrderService deduplication.
8. WorkflowOrchestrator initial version.
9. Standalone intake adapters.
10. Reception/Doctor/Lab/Radiology/Pharmacy workbenches.
11. Files/Notifications/Reports integration.
12. Inventory/QC/AI governance.

---

## 15. ملاحظة تنفيذية

هذه الوثيقة خطة تحليل وتحسين. لا تتضمن أي تعديل كود تنفيذي. التنفيذ يجب أن يتم بمراحل صغيرة، وكل مرحلة commit منفصل، مع عدم لمس `tests/*` أو `logs/*` إلا بقرار واضح ومنفصل.

اقتراح أسماء commits لاحقة:

```text
docs: add route-module inventory
feat(core): add feature gate service
feat(saas): add tenant product profiles
feat(saas): enforce module guards across blueprints
feat(workflow): add workflow orchestrator skeleton
feat(billing): reconcile billing and receipt states
feat(orders): centralize clinical order creation
feat(lab): add standalone lab intake workflow
feat(pharmacy): add standalone pharmacy sale workflow
```
