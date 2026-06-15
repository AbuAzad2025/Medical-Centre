# خطة تحسين منطق وتجربة استخدام النظام الطبي

**اسم الخطة:** Medical Center Workflow & UX Logic Improvement Plan  
**الإصدار:** v3 - SaaS Tenant Modules & Cross-Module Integration Review  
**التاريخ:** 2026-06-16  
**أُعدت بواسطة:** GPT-5.5 Thinking  
**النطاق:** تحليل وخطة تحسين منطقية/تشغيلية/UX للنظام الطبي كمنصة SaaS ديناميكية متعددة المستأجرين، تدعم بيع وحدات مستقلة أو باقات مركبة، بدون تعديل كود تنفيذي في هذه المرحلة.

---

## 0. الهدف التنفيذي

الهدف من هذه الخطة هو تحويل النظام من مجموعة شاشات ووحدات منفصلة إلى منصة طبية SaaS ديناميكية، قابلة للبيع والتفعيل بأكثر من شكل:

- طبيب بعيادة خاصة.
- عيادة صغيرة مع استقبال وطبيب وفوترة.
- مختبر مستقل فقط.
- مركز أشعة مستقل فقط.
- صيدلية مستقلة فقط.
- مركز طبي كامل بعدة أقسام.
- مركز يحتوي بعض الأقسام فقط.
- نظام كبير متعدد المستخدمين والأدوار تحت Tenant واحد.
- منصة Cloud SaaS متعددة Tenants، مع تفعيل/تعطيل وحدات من لوحة مالك المنصة أو Super Admin.

المبدأ التشغيلي العام: **كل Tenant يجب أن يرى فقط الوحدات المفعلة له، وكل وحدة يجب أن تعمل في وضعين عند الحاجة: وضع مستقل standalone ووضع مدمج داخل مركز طبي كامل.**

---

## 1. الملفات التي بُني عليها التحليل

تم بناء الخطة على قراءة وفحص ملفات فعلية من الريبو، منها:

### SaaS / Tenant / Modules

- `app/core/tenant/models.py`
- `app/core/tenant/middleware.py`
- `app/core/module/models.py`
- `app/core/module/registry.py`
- `app/core/module/validators.py`
- `app/shared/enums.py`
- `app/modules/owner/routes.py`
- `app_factory.py`
- `templates/partials/sidebar.html`

### Backend / Models

- `models/patient.py`
- `models/visit.py`
- `models/appointment.py`
- `models/department.py`
- `models/queue_management.py`
- `models/request_workflow.py`
- `models/lab_request.py`
- `models/radiology_request.py`
- `models/nurse.py`
- `models/emergency.py`
- `models/medical_record.py`
- `models/medication.py`
- `models/payment.py`
- `models/invoice.py`
- `models/service.py`
- `models/user.py`
- `models/visit_transfer.py`

### Backend / Routes

- `routes/reception.py`
- `routes/doctor.py`
- `routes/nurse_routes.py`
- `routes/lab.py`
- `routes/radiology.py`
- `routes/medication_routes.py`
- `routes/payment_routes.py`

### Services & Security

- `services/queue_management_service.py`
- `services/access_control_service.py`
- `services/gatekeeper_service.py`
- `utils/decorators.py`

### Frontend / Templates

- `templates/reception/create_visit.html`
- `templates/partials/sidebar.html`

---

## 2. فهم الهدف التجاري الصحيح

النظام ليس منتجاً واحداً ثابتاً لمركز طبي كامل فقط. النظام يجب أن يكون **منصة منتجات طبية قابلة للتركيب**.

يعني:

```text
Platform Owner / Super Admin
  -> creates Tenant
  -> selects plan / subscription
  -> activates modules
  -> tenant sees only activated modules
  -> tenant workflows adapt to active module combination
```

الأهم: لا يجوز أن تكون كل وحدة مفترضة أن كل الوحدات الأخرى موجودة. ولا يجوز أن يؤدي تعطيل وحدة إلى كسر وحدة أخرى. يجب أن يكون هناك تعريف واضح:

- ما الوحدة؟
- ما قدراتها؟
- ما اعتمادياتها؟
- هل تعمل standalone؟
- ما الشاشة الافتتاحية لها؟
- ما الحد الأدنى للبيانات؟
- هل تحتاج patient؟ visit؟ invoice؟ queue؟
- هل تحتاج reception كاملة أم intake بسيط؟

---

## 3. الوضع الحالي لمنظومة SaaS والModules

### 3.1 الموجود حالياً

يوجد أساس مهم وجيد:

- `Tenant` يمثل العميل/المؤسسة.
- `SubscriptionPlan` يمثل خطة الاشتراك.
- `TenantModule` يحدد الوحدات النشطة لكل Tenant.
- `MODULE_REGISTRY` مصدر مركزي لتعريف أسماء الوحدات ووصفها واعتمادياتها.
- `get_active_modules_for_tenant()` يجلب الوحدات النشطة.
- `app_factory.py` يضيف module guards قبل تسجيل بعض blueprints.
- `templates/partials/sidebar.html` يعرض الروابط حسب `enabled_modules` والدور.
- `owner/routes.py` يحتوي API لتفعيل وحدات Tenant.

### 3.2 المشكلة الحالية

رغم وجود الأساس، يوجد نقص تكاملي:

1. `MODULE_REGISTRY` الحالي يجعل معظم الوحدات السريرية تتطلب `reception`، مثل doctor/lab/radiology/pharmacy/emergency/nursing/billing/appointments.
2. هذا يخالف حالات بيع مختبر مستقل، أشعة مستقلة، أو صيدلية مستقلة.
3. `app_factory.py` يضيف guards لبعض الوحدات فقط:
   - reception
   - doctor
   - lab
   - radiology
   - emergency
   - nursing
   - billing
   - reporting
   - appointments
   - pharmacy
4. لكنه يسجل blueprints أخرى كثيرة بدون guard واضح:
   - bed
   - OR
   - eMAR
   - vaccination
   - referral
   - pathway
   - CDS
   - barcode
   - FHIR
   - DICOM
   - portal
   - population health
   - report builder
   - security
   - MFA
   - nursing assessment
   - patient education
   - backup restore
   - telemedicine
   - SSO
   - AI imaging
   - biometric
   - data warehouse
   - what-if
   - quality
5. الـ sidebar يخفي روابط حسب modules، لكن إخفاء الرابط لا يكفي. يجب منع الوصول backend أيضاً.
6. بعض المسارات الجذرية مثل `/patients`, `/visits`, `/medications` تعمل redirects عامة ويجب أن تكون module-aware.

### 3.3 الاستنتاج

النظام لديه بذرة SaaS Modules جيدة، لكنها تحتاج طبقة أقوى اسمها:

```text
Product Profile + Module Capability + Workflow Adapter
```

بدون هذه الطبقة سيبقى السؤال: هل المختبر المستقل يحتاج reception؟ هل الصيدلية تحتاج patient visit؟ هل عيادة الطبيب تحتاج nurse؟ هل billing إجباري؟

---

## 4. Product Profiles المقترحة

بدلاً من تفعيل modules عشوائياً فقط، يجب تعريف باقات تشغيلية جاهزة. كل باقة تحدد الوحدات، الـ default dashboards، الـ workflows، والصلاحيات.

### 4.1 `PRIVATE_DOCTOR_CLINIC`

عيادة طبيب خاصة.

Modules:

```text
reception_core أو clinic_intake
doctor
appointments optional
billing optional
pharmacy optional
reporting basic
```

Workflow:

```text
Patient -> Clinic Intake -> Doctor -> Prescription/Follow-up -> Billing optional -> Completed
```

ملاحظات:

- لا يحتاج nurse إجبارياً.
- لا يحتاج lab/radiology داخلياً.
- الطبيب يستطيع إنشاء طلب خارجي lab/radiology كـ referral/order print فقط.
- واجهة الاستقبال تكون مختصرة جداً.

### 4.2 `SMALL_CLINIC`

عيادة صغيرة بعدة أطباء أو استقبال.

Modules:

```text
reception
doctor
appointments
billing
reporting
```

Workflow:

```text
Reception -> Payment/Check-in -> Doctor -> Checkout
```

ملاحظات:

- nurse اختياري.
- lab/radiology اختياري كطلبات خارجية أو داخلية.

### 4.3 `STANDALONE_LAB`

مختبر مستقل فقط.

Modules:

```text
lab
lab_intake أو reception_lite
billing optional
reporting basic
inventory optional
```

Workflow:

```text
Lab Intake -> Sample Collection -> Analysis -> Validation -> Report Delivery -> Billing optional
```

ملاحظات مهمة:

- لا يجب إجبار `reception` الكامل.
- يجب توفير شاشة `lab_intake` لإدخال مريض/طلب بدون زيارة طبيب.
- يجب دعم walk-in lab order.
- يمكن إنشاء `Patient` و`LabRequest` بدون Doctor Visit كامل.
- إذا lab جزء من مركز، الطلب يأتي من doctor/reception.
- إذا lab standalone، الطلب يأتي من lab intake أو إحالة خارجية.

### 4.4 `STANDALONE_RADIOLOGY`

مركز أشعة مستقل.

Modules:

```text
radiology
radiology_intake أو reception_lite
billing optional
reporting basic
DICOM optional
AI imaging optional
```

Workflow:

```text
Radiology Intake -> Imaging Queue -> Image Upload/DICOM -> Report -> Validation -> Delivery
```

ملاحظات:

- لا يجب إجبار reception الكامل.
- يجب دعم طلب خارجي من طبيب خارج النظام.
- يجب وجود referring_doctor_name/referral_source.
- DICOM/AI imaging يجب أن تكون modules مستقلة مربوطة بالأشعة.

### 4.5 `STANDALONE_PHARMACY`

صيدلية مستقلة فقط.

Modules:

```text
pharmacy
inventory
billing/POS optional
reporting basic
```

Workflow:

```text
Walk-in Sale / Prescription Upload -> Dispense -> Stock Ledger -> Receipt
```

ملاحظات:

- لا تحتاج reception.
- لا تحتاج Visit إجباري.
- تحتاج `PharmacySale` أو `POSInvoice` مستقل.
- `Prescription` يمكن أن يكون داخلياً أو خارجياً.
- يجب دعم البيع المباشر، المرتجع، البدائل، batch/expiry، stock ledger.

### 4.6 `MULTI_DEPARTMENT_CENTER`

مركز طبي كامل.

Modules:

```text
reception
doctor
nursing
lab
radiology
pharmacy
billing
appointments
emergency optional
reporting
inventory
```

Workflow:

```text
Reception -> Billing/Eligibility -> Triage -> Doctor -> Orders -> Departments -> Doctor Review -> Pharmacy/Checkout -> Archive
```

هنا reception إلزامية، لأنها نقطة تنظيم بين أكثر من وحدة سريرية.

### 4.7 `CUSTOM_CENTER`

Tenant يختار وحدات محددة.

قواعد:

- إذا أكثر من وحدة سريرية مفعلة داخل نفس Tenant، يُفضّل تفعيل `reception` أو `front_desk`.
- إذا وحدة واحدة مستقلة فقط، لا تُفرض reception الكاملة.
- إذا billing غير مفعلة، لا يجوز أن تكسر الطابور أو إنشاء الطلبات.
- إذا appointments غير مفعلة، تختفي كل flows الخاصة بالمواعيد.
- إذا doctor غير مفعلة، lab/radiology لا تنتظر doctor review داخلي بل تعتمد delivery workflow.

---

## 5. التصحيح المقترح لمنظومة Modules

### 5.1 المشكلة في `required_modules`

حالياً `MODULE_REGISTRY` يجعل lab/radiology/pharmacy تعتمد على reception. هذا مناسب لمركز كامل لكنه غير مناسب لبيع standalone.

### 5.2 الحل: فصل Module عن Capability

بدلاً من:

```text
lab requires reception
```

نستخدم:

```text
lab requires one of:
  - reception
  - lab_intake
  - standalone_intake
```

وبدلاً من أن تكون reception وحدة ضخمة، نفصل capability:

```text
patient_registry
front_desk
appointments
billing
queue
clinical_orders
```

### 5.3 إضافة ProductProfile

نموذج مقترح:

```text
ProductProfile
  id
  code
  name
  name_ar
  description
  default_modules_json
  required_capabilities_json
  default_dashboard
  is_active
```

أمثلة:

```text
PRIVATE_DOCTOR_CLINIC
STANDALONE_LAB
STANDALONE_RADIOLOGY
STANDALONE_PHARMACY
SMALL_CLINIC
MULTI_DEPARTMENT_CENTER
CUSTOM
```

### 5.4 إضافة TenantProductProfile

يمكن أن يكون داخل Tenant مباشرة:

```text
Tenant.product_profile_code
```

أو جدول مستقل للتاريخ:

```text
TenantProductProfileHistory
  tenant_id
  old_profile
  new_profile
  changed_by
  changed_at
```

### 5.5 تعديل ModuleMeta

بدل `required_modules` فقط:

```python
@dataclass(frozen=True)
class ModuleMeta:
    name: str
    name_ar: str
    category: str
    required_modules: tuple
    required_any_of: tuple[tuple[str, ...], ...]
    capabilities: tuple[str, ...]
    standalone_allowed: bool
    default_route: str
    description_ar: str
```

مثال:

```python
"lab": ModuleMeta(
    name="lab",
    required_modules=(),
    required_any_of=(("reception", "lab_intake", "standalone_intake"),),
    capabilities=("patient_lookup", "lab_order", "lab_result", "report_delivery"),
    standalone_allowed=True,
    default_route="/lab/dashboard",
)
```

### 5.6 تعديل validator

بدل قاعدة واحدة:

```text
If more than 2 clinical modules -> reception required
```

تصبح:

```text
If product_profile == MULTI_DEPARTMENT_CENTER -> reception/front_desk required
If standalone module -> standalone_intake allowed
If module has required_any_of -> at least one capability provider required
If billing disabled -> module must use no-charge / external billing / local receipt mode
```

---

## 6. Frontend + Backend Integration المطلوب

### 6.1 Backend guard لا يكفي للـ sidebar

يجب أن تكون الحماية في 3 طبقات:

1. Route guard: يمنع الوصول لوحدة غير مفعلة.
2. Template visibility: يخفي الروابط والأزرار غير المفعلة.
3. Workflow guard: يمنع إنشاء خطوات تعتمد على وحدة غير مفعلة.

مثال:

إذا `lab` غير مفعلة:

- لا يظهر زر طلب مختبر للطبيب.
- لا يظهر tab المختبر في patient context.
- لا يقبل backend إنشاء LabRequest.
- لا تظهر إحصائيات lab في dashboard.

### 6.2 كل زر Action يجب أن يمر عبر `FeatureGate`

مقترح:

```python
FeatureGate.is_enabled(tenant_id, "lab")
FeatureGate.can_use(user, "lab.create_request")
FeatureGate.require("pharmacy.dispense")
```

وفي Jinja:

```jinja2
{% if feature_enabled('lab') and can_use('lab.create_request') %}
  <button>طلب تحليل</button>
{% endif %}
```

### 6.3 Route registration

حالياً يمكن إبقاء كل blueprints مسجلة، لكن يجب أن يكون كل blueprint guarded أو كل route guarded.

خطة أفضل:

- `core` routes دائماً تعمل: auth, health, owner, super_admin, tenant select.
- module routes تسجل مع guard موحد:

```python
register_module_blueprint(app, lab_bp, module="lab", prefix="/lab")
```

ويطبق:

- tenant required إذا SaaS.
- module active.
- role allowed.
- tenant subscription active.

---

## 7. Tenant Isolation المطلوب

### 7.1 الموجود

`User` يحتوي `tenant_id`. و`Tenant` لديه علاقة users. لكن كثير من النماذج التشغيلية مثل Patient/Visit/Payment/LabRequest/RadiologyRequest يجب أن تكون tenant-scoped بوضوح.

### 7.2 المطلوب

كل جدول تشغيلي يجب أن يحتوي `tenant_id` أو يكون مرتبطاً بكيان يحتوي tenant_id بشكل مضمون.

جداول يجب فحصها وإضافة tenant_id عند الحاجة:

```text
patients
visits
appointments
payments
invoices
lab_requests
lab_results
radiology_requests
radiology_results
prescriptions
prescription_items
medications
queue_management
service_master
departments
nurses
vital_signs
emergency_cases
medical_records
file_uploads
```

### 7.3 قاعدة ذهبية

لا يكفي أن يكون المستخدم له tenant_id. يجب أن تكون البيانات نفسها tenant-scoped.

كل query يجب أن تمر عبر:

```python
TenantScope.query(Model)
```

أو global SQLAlchemy filter في SaaS mode.

### 7.4 Tenant-aware context

يجب أن يكون في كل request:

```text
g.current_tenant
g.tenant_id
g.enabled_modules
g.product_profile
```

ويجب أن تظهر في Jinja:

```text
current_tenant
enabled_modules
product_profile
feature_flags
```

---

## 8. Module Dependency Matrix المقترحة

| Module | Standalone? | Requires in center mode | Requires in standalone mode | Notes |
|---|---:|---|---|---|
| reception | نعم | none | none | full front desk |
| doctor | نعم جزئياً | reception/front_desk | clinic_intake | private doctor clinic |
| lab | نعم | reception أو doctor orders | lab_intake | standalone lab must work |
| radiology | نعم | reception أو doctor orders | radiology_intake | DICOM optional |
| pharmacy | نعم | doctor prescription أو billing | pharmacy_pos | standalone pharmacy does not need visit |
| nursing | لا غالباً | reception + doctor/emergency | not standalone | can be disabled in small clinic |
| emergency | لا غالباً | reception/front_desk + triage | emergency_intake | standalone emergency rare |
| billing | نعم | service lines | POS/invoice | must support disabled mode |
| appointments | نعم | reception/doctor | clinic scheduling | optional |
| reporting | نعم | any module | any module | report scope depends modules |
| inventory | نعم | pharmacy/lab/radiology | stock-only | useful for pharmacy-only |
| DICOM | لا | radiology | radiology | dependent on radiology |
| AI imaging | لا | radiology | radiology | dependent on radiology |
| eMAR | لا | nursing + pharmacy | none | inpatient/center only |
| bed/OR | لا | center/hospital profile | none | not for small clinic by default |
| FHIR/API | نعم | tenant subscription | tenant subscription | integration module |

---

## 9. Workflow Adapters حسب الباقة

### 9.1 Center mode adapter

```text
Reception creates Visit
Visit enters Queue
Nurse triage optional/required
Doctor sees patient
Orders go to internal Lab/Radiology/Pharmacy
Billing closes visit
```

### 9.2 Standalone Lab adapter

```text
Lab Intake creates Patient if needed
Creates LabRequest directly
Optional invoice/payment
Sample collection queue
Result entry
Validation
Report delivery
```

لا ينتظر doctor داخلي. الطبيب المحيل يمكن أن يكون نصاً:

```text
referring_doctor_name
referring_clinic
external_order_number
```

### 9.3 Standalone Radiology adapter

```text
Radiology Intake
Create imaging request
Schedule imaging
Upload image/DICOM
Draft report
Validate report
Deliver report
```

### 9.4 Standalone Pharmacy adapter

```text
Walk-in customer or registered patient
Prescription upload/manual entry optional
Sale/dispense
Stock deduction
Receipt/POS
```

هنا لا يوجد `Visit` إجباري. يجب إنشاء نموذج:

```text
PharmacySale
PharmacySaleItem
StockLedger
```

أو استخدام invoice/payment بدون زيارة.

### 9.5 Private Doctor adapter

```text
Clinic Intake or doctor creates appointment/visit
Doctor encounter
Prescription/Follow-up
External lab/radiology referral optional
Billing optional
```

---

## 10. Backend Models إضافية مطلوبة لدعم SaaS Dynamic Modules

### 10.1 `TenantFeatureFlag`

```text
id
tenant_id
feature_key
is_enabled
value_json
updated_by
updated_at
```

أمثلة:

```text
lab.requires_payment_before_sample
doctor.requires_triage
pharmacy.allow_walkin_sale
radiology.enable_dicom
billing.allow_debt
```

### 10.2 `TenantModuleSetting`

```text
id
tenant_id
module_name
settings_json
updated_by
updated_at
```

أمثلة:

```json
{
  "default_dashboard": "/lab/worklist",
  "allow_external_referrals": true,
  "require_patient_registration": false,
  "enable_queue": true
}
```

### 10.3 `TenantWorkflowProfile`

```text
tenant_id
profile_code
workflow_config_json
```

يحدد إن كان tenant:

- standalone_lab
- standalone_pharmacy
- private_doctor
- center

### 10.4 `ModuleRouteMap`

اختياري أو static registry:

```text
module_name
route_prefix
blueprint_name
default_route
guard_required
```

لتغطية كل blueprints وليس بعضها فقط.

---

## 11. Frontend مطلوب حسب dynamic modules

### 11.1 Sidebar

`templates/partials/sidebar.html` جيد كبداية، لكنه يحتاج:

- استخدام `FeatureGate` لا مجرد `enabled_modules`.
- إظهار product profile name.
- إخفاء sub-features داخل module حسب settings.
- عدم إظهار modules advanced إذا غير guarded backend.

### 11.2 Dashboards ديناميكية

كل Tenant يجب أن يرى dashboard مناسب للبروفايل:

| Profile | Default dashboard |
|---|---|
| private doctor | `/doctor/dashboard` أو `/clinic/dashboard` |
| standalone lab | `/lab/worklist` |
| standalone radiology | `/radiology/worklist` |
| standalone pharmacy | `/medication/dashboard` أو `/pharmacy/pos` |
| small clinic | `/reception/dashboard` |
| full center | `/reception/dashboard` أو `/manager/dashboard` |

### 11.3 Empty states

إذا وحدة غير مفعلة، لا تظهر صفحة مكسورة. تظهر رسالة:

```text
هذه الوحدة غير مفعلة ضمن اشتراكك. تواصل مع مالك المنصة لترقيتها.
```

للـ owner/super_admin يظهر زر تفعيل.

### 11.4 أزرار الطلبات

في شاشة الطبيب:

- زر طلب مختبر يظهر فقط إذا lab enabled أو external lab referrals enabled.
- زر طلب أشعة يظهر فقط إذا radiology enabled أو external radiology referrals enabled.
- زر وصفة يظهر إذا pharmacy enabled أو prescription print enabled.

في standalone lab:

- لا تظهر doctor consultation screens.
- تظهر lab intake + sample + result فقط.

---

## 12. Cross-Module Data Contracts

يجب أن يكون لكل وحدة contract واضح.

### 12.1 Reception -> Any module

```text
patient_id
visit_id optional
encounter_id optional
source_module
priority
billing_clearance
```

### 12.2 Doctor -> Lab

```text
order_id
visit_id
patient_id
ordered_by
tests[]
priority
clinical_notes_summary
```

### 12.3 Standalone Lab Intake -> Lab

```text
patient_id optional initially
external_patient_name allowed
external_referrer
requested_tests[]
payment_mode
```

### 12.4 Doctor -> Pharmacy

```text
prescription_id
patient_id
visit_id
items[]
signed_by
status=READY_TO_DISPENSE
```

### 12.5 Pharmacy standalone sale

```text
sale_id
customer_name optional
patient_id optional
items[]
payment
stock_movements[]
```

---

## 13. Top Architecture Gaps بعد الفحص الديناميكي

| Gap | Impact | Fix |
|---|---|---|
| standalone modules غير مدعومة بقواعد dependencies الحالية | يمنع بيع مختبر/أشعة/صيدلية وحدها | product profiles + standalone intake |
| guards لا تغطي كل blueprints | وصول backend لوحدات غير مفعلة | centralized module route registration |
| sidebar يخفي فقط links | لا يكفي للحماية | backend FeatureGate |
| no product profile | tenant modules عشوائية بلا workflow | TenantWorkflowProfile |
| no tenant module settings | نفس الوحدة لا تتكيف حسب العميل | TenantModuleSetting |
| patient/visit assumptions في كل مكان | pharmacy/lab standalone قد تنكسر | data contracts allow visit optional by profile |
| billing مفترض في بعض flows | tenant بلا billing يتعطل | Billing optional adapter |
| reception مفروضة لكل clinical modules | يخالف standalone sales | intake capability بدل reception module |

---

## 14. خطة تنفيذ SaaS Module Integration

### Phase A — Inventory & Guard Coverage

Actions:

- بناء جدول بكل blueprints والمسارات.
- ربط كل blueprint بـ module.
- تحديد core routes التي لا تحتاج module.
- إضافة guard لكل blueprints غير المغطاة.

Validation:

```powershell
python -m flask routes
```

Expected output:

- كل route له module أو core.

### Phase B — Product Profiles

Actions:

- إضافة `ProductProfile` أو enum ثابت.
- إضافة `product_profile_code` إلى Tenant.
- ربط الخطط profiles.
- owner UI عند إنشاء tenant يختار profile.

Profiles:

```text
PRIVATE_DOCTOR_CLINIC
STANDALONE_LAB
STANDALONE_RADIOLOGY
STANDALONE_PHARMACY
SMALL_CLINIC
MULTI_DEPARTMENT_CENTER
CUSTOM
```

### Phase C — Module Dependency Refactor

Actions:

- تعديل `ModuleMeta` لدعم:
  - `standalone_allowed`
  - `required_any_of`
  - `capabilities`
  - `default_route`
- تعديل `can_activate_module` حسب product profile.
- عدم فرض reception على standalone lab/radiology/pharmacy.

### Phase D — Standalone Intake

Actions:

إنشاء lightweight intake capabilities:

```text
clinic_intake
lab_intake
radiology_intake
pharmacy_pos
```

يمكن تنفيذها كـ pages داخل نفس module بدلاً من modules منفصلة.

### Phase E — Tenant Feature Flags

Actions:

- إضافة `TenantFeatureFlag`.
- استخدامه في backend وfrontend.
- دعم flags مثل:

```text
requires_triage
billing_required_before_queue
allow_walkin_lab
allow_walkin_pharmacy_sale
external_referrals_enabled
```

### Phase F — Frontend Dynamic UI

Actions:

- إضافة Jinja helpers:
  - `feature_enabled(module_or_feature)`
  - `module_active(module)`
  - `tenant_profile()`
- تحديث sidebar.
- تحديث dashboards.
- إخفاء buttons حسب features.

### Phase G — Workflow Adapters

Actions:

- بناء adapter لكل profile:

```python
WorkflowAdapter.for_tenant(tenant).create_entry(...)
WorkflowAdapter.for_tenant(tenant).next_actions(...)
```

Adapters:

```text
CenterWorkflowAdapter
ClinicWorkflowAdapter
StandaloneLabWorkflowAdapter
StandaloneRadiologyWorkflowAdapter
StandalonePharmacyWorkflowAdapter
```

---

## 15. الخطة الطبية الأصلية المختصرة باقية

المشاكل الأصلية ما زالت صحيحة:

- توحيد حالات الزيارة والطابور والطلبات.
- فصل `create_visit` إلى services.
- منع تكرار lab/radiology orders.
- إضافة `TriageAssessment` مربوط بالزيارة.
- إنشاء `ClinicalEncounter` منظم.
- إصلاح الدفع/الإيصال/الطابور.
- بناء `VisitWorkflowService`.
- إعادة تصميم واجهة الاستقبال كـ wizard.
- بناء patient context panel.
- إصلاح صلاحيات الأدوار.

لكن الآن يجب تنفيذها تحت قاعدة أهم:

```text
كل تحسين workflow يجب أن يكون tenant-aware وmodule-aware وprofile-aware.
```

---

## 16. ترتيب الأولويات الجديد

### الأولوية 1 — SaaS/module safety

قبل أي UX كبير:

1. حصر كل routes وربطها بـ module.
2. إضافة guards لكل module routes.
3. إصلاح dependencies لتدعم standalone modules.
4. إضافة product profile للـ Tenant.

### الأولوية 2 — Workflow core

1. `VisitWorkflowService`.
2. `BillingStateService`.
3. `OrderService`.
4. `QueueService`.

### الأولوية 3 — Standalone module flows

1. standalone lab intake.
2. standalone radiology intake.
3. standalone pharmacy POS/sale.
4. private doctor clinic intake.

### الأولوية 4 — Full center UX

1. reception wizard.
2. triage integration.
3. doctor workbench.
4. lab/radiology/pharmacy worklists.
5. dashboards.

---

## 17. Checklist SaaS نهائي

### Tenant

- [ ] كل Tenant لديه product profile.
- [ ] كل Tenant لديه modules مفعلة.
- [ ] كل Tenant لديه feature flags.
- [ ] كل Tenant لديه default dashboard.
- [ ] كل Tenant لا يرى بيانات Tenant آخر.

### Modules

- [ ] كل module له registry entry.
- [ ] كل module له default route.
- [ ] كل module له backend guard.
- [ ] كل module له sidebar visibility.
- [ ] كل module له standalone/center behavior.

### Standalone

- [ ] المختبر يعمل بدون doctor/reception full.
- [ ] الأشعة تعمل بدون doctor/reception full.
- [ ] الصيدلية تعمل بدون patient visit.
- [ ] عيادة الطبيب تعمل بدون lab/radiology/nursing.

### Center

- [ ] reception ينسق بين الأقسام.
- [ ] queue يحدد المحطة الحالية.
- [ ] doctor يطلب lab/radiology/pharmacy فقط إذا مفعلة.
- [ ] billing لا يكسر flow إذا غير مفعلة.

### Frontend

- [ ] sidebar module-aware.
- [ ] buttons feature-aware.
- [ ] dashboards profile-aware.
- [ ] empty states واضحة.
- [ ] لا يوجد رابط ظاهر لمسار غير مسموح.

### Backend

- [ ] كل route guarded.
- [ ] كل query tenant-scoped.
- [ ] كل workflow service يقرأ product profile.
- [ ] كل activation/deactivation يسجل audit.

---

## 18. القرار النهائي الموصى به

النظام يجب أن ينتقل من:

```text
Modules as pages
```

إلى:

```text
Modules as products + capabilities + workflows
```

أي أن الوحدة ليست مجرد رابط في sidebar، بل عقد تشغيلي كامل:

- هل تعمل وحدها؟
- ماذا تحتاج؟
- كيف تبدأ؟
- ما نموذج بياناتها الأدنى؟
- ما dashboard الخاص بها؟
- ما علاقتها بالفوترة والطابور والمريض؟
- كيف تتصرف إذا كانت جزءاً من مركز كامل؟

أفضل بداية تنفيذية:

1. بناء route/module inventory.
2. توسيع `MODULE_REGISTRY`.
3. إضافة Product Profiles.
4. تصحيح module validators.
5. تغطية كل blueprints بال guards.
6. بعدها نبدأ workflow/UX لكل profile.

---

## 19. ملاحظة تنفيذية

هذه الوثيقة خطة تحليل وتحسين. لا تتضمن أي تعديل كود تنفيذي. التنفيذ يجب أن يتم على مراحل صغيرة، وكل مرحلة يجب أن تكون قابلة للاختبار والرجوع عنها، مع تجنب تعديل ملفات `tests/*` أو `logs/*` إلا بقرار واضح ومنفصل.

يجب أن يكون كل commit لاحقاً محدوداً وواضحاً:

```text
Phase SaaS-1: route module inventory and guard coverage
Phase SaaS-2: product profiles and module registry expansion
Phase SaaS-3: standalone intake adapters
Phase Workflow-1: constants and state normalization
Phase Workflow-2: billing gatekeeper consistency
Phase Workflow-3: order creation deduplication
Phase Workflow-4: triage visit binding
Phase Workflow-5: workflow service initial integration
```

ولا يتم دمج أكثر من مرحلة في commit واحد.
