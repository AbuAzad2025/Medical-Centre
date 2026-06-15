# خطة تحسين منطق وتجربة استخدام النظام الطبي

**اسم الخطة:** Medical Center Workflow & UX Logic Improvement Plan  
**الإصدار:** v2 - Deep Repository Review  
**التاريخ:** 2026-06-16  
**أُعدت بواسطة:** GPT-5.5 Thinking  
**النطاق:** تحليل وخطة تحسين منطقية/تشغيلية/UX للنظام الطبي، بدون تعديل كود تنفيذي في هذه المرحلة.

---

## 0. الهدف التنفيذي

الهدف من هذه الخطة هو تحويل النظام من مجموعة شاشات ووحدات منفصلة إلى مسار طبي واضح يقود المستخدم خطوة بخطوة من تسجيل المريض إلى إغلاق الزيارة، مع تقليل التكرار، منع التناقضات المنطقية، وضمان أن كل قسم يرى فقط ما يحتاجه ويعرف ما المطلوب منه الآن.

المشكلة الأساسية ليست أن النظام ناقص برمجياً فقط، بل أن منطق التشغيل موزع بين `routes`, `models`, `services`, وواجهات كبيرة، بدون محرك موحد يحدد:

- أين تقع الزيارة الآن؟
- من المسؤول عن الخطوة الحالية؟
- ما البيانات المطلوبة قبل الانتقال؟
- ما الشاشة الصحيحة للمستخدم؟
- ما الذي يجب أن يظهر لكل دور؟
- ما الذي يمنع التكرار أو تضارب الحالات؟
- ما الذي يجب أن يحدث تلقائياً بدل أن يدخله المستخدم يدوياً؟
- ما الذي يجب أن يبقى خاصاً بكل قسم ولا يظهر لغيره؟

---

## 1. الملفات التي بُني عليها التحليل

تم بناء الخطة على قراءة وفحص ملفات فعلية من الريبو، منها:

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

### Backend / Services & Security

- `services/queue_management_service.py`
- `services/access_control_service.py`
- `services/gatekeeper_service.py`
- `utils/decorators.py`

### Frontend / Templates

- `templates/reception/create_visit.html`

---

## 2. الملخص التنفيذي الموسع

النظام يحتوي على مكونات كثيرة ومفيدة: مرضى، زيارات، مواعيد، طوابير، أطباء، تمريض، مختبر، أشعة، صيدلية، دفع، تأمين، طوارئ، تقارير، وصلاحيات. لكن هذه المكونات تعمل بمنطق متفرق. النتيجة أن تجربة المستخدم تبدو ثقيلة ومتعبة، خصوصاً في إنشاء الزيارة، الطوابير، الصلاحيات، وجلب سياق المريض بين الأقسام.

المشكلة ليست أن كل وحدة سيئة منفردة؛ المشكلة أن كل وحدة صنعت لنفسها لغة مختلفة للحالة والانتقال والصلاحيات. لذلك المستخدم يرى شاشات كثيرة لكن لا يرى مساراً واحداً واضحاً.

### أعلى 15 مشكلة حالية

| # | المشكلة | الأثر |
|---|---|---|
| 1 | تعدد حالات الزيارة والطابور والطلبات بدون قاموس موحد | تضارب بين الشاشات وصعوبة معرفة المرحلة الحالية |
| 2 | `create_visit` في `routes/reception.py` يجمع استقبال + دفع + تأمين + فحوصات + طابور + طوارئ | شاشة ثقيلة ومنطق هش |
| 3 | احتمال إنشاء طلب مختبر مكرر عند اختيار خدمات مختبرية | تكرار طلبات أو نتائج ناقصة |
| 4 | الطابور مرتبط بالدفع بطريقة غير واضحة للمستخدم | زيارة تنشأ لكن لا تدخل الطابور أو تظهر تحذيرات مربكة |
| 5 | `GatekeeperService` يشترط `receipt_printed` بينما مسار الدفع يولد `receipt_number` ولا يكفي ذلك بالضرورة | فجوة مباشرة بين الدفع والطابور |
| 6 | التمريض ليس محطة إلزامية واضحة قبل الطبيب | الطبيب قد يستلم زيارة دون vitals/triage |
| 7 | `VitalSigns` مرتبطة بالمريض والممرض فقط ولا تحمل `visit_id` | لا نضمن أن القياسات تخص هذه الزيارة |
| 8 | `MedicalRecord` عام جداً ولا يمثل encounter سريري منظم | ضعف التوثيق الطبي وسهولة ضياع السياق |
| 9 | `EmergencyCase` يحمل vital signs كنص JSON وتشخيص وخطة منفصلة عن visit lifecycle | ازدواجية بين الطوارئ والزيارة |
| 10 | نوع القسم يستنتج من الاسم `get_type()` بدلاً من حقل ثابت | هش عند تغيير أسماء الأقسام |
| 11 | المواعيد تحمل `notes` فقط للسبب/الأعراض/نوع الموعد | تحويل الموعد إلى زيارة يحتاج parsing غير موثوق |
| 12 | الطبيب/الممرض/المختبر قد يرون بيانات أوسع مما يحتاجون | ضعف خصوصية وتجربة غير مركزة |
| 13 | واجهة إنشاء الزيارة تعرض حقول كثيرة دفعة واحدة | إرهاق المستخدم وزيادة أخطاء الإدخال |
| 14 | الصيدلية ليست محطة workflow كاملة ضمن مسار الزيارة | الوصفات والصرف يعملان بمعزل عن الطابور |
| 15 | التحويل بين الأقسام يسجل old/new فقط ولا يسجل سبب/قبول/حالة التحويل | صعوبة تتبع المسؤولية بين الأقسام |

### أعلى 15 توصية

| # | التوصية | الأولوية |
|---|---|---|
| 1 | إنشاء `VisitWorkflowService` كمصدر وحيد لحالة الزيارة | Critical |
| 2 | توحيد status constants في ملف مركزي | Critical |
| 3 | فصل منطق إنشاء الطلبات والفحوصات عن `create_visit` إلى `OrderService` | Critical |
| 4 | إصلاح فجوة `receipt_number` مقابل `receipt_printed` | Critical |
| 5 | إضافة `visit_id` أو نموذج `TriageAssessment` للعلامات الحيوية | Critical |
| 6 | إعادة تصميم `create_visit.html` كـ wizard من 5 خطوات | High |
| 7 | جعل التمريض/triage خطوة واضحة قبل الطبيب عند الحاجة | High |
| 8 | إنشاء queue state machine موحد بمحطات `station` | High |
| 9 | ضبط permission matrix حسب role + department + ownership + tenant | High |
| 10 | بناء patient context panel مشترك لكل الأقسام | High |
| 11 | توحيد lab/radiology/pharmacy handoff داخل workflow واحد | High |
| 12 | استبدال `Department.get_type()` المعتمد على الاسم بحقل `department_type` | High |
| 13 | تحويل appointment notes إلى حقول منظمة | Medium/High |
| 14 | بناء audit trail لكل انتقال في الزيارة والطابور والطلبات | Medium/High |
| 15 | فصل billing state عن clinical state | Medium/High |

---

## 3. خريطة النظام الحالية

### 3.1 الزيارة

`models/visit.py` يحتوي على `Visit` ككيان مركزي وفيه:

- `patient_id`
- `department_id`
- `doctor_id`
- `visit_number`
- `status`
- `payment_status`
- `total_amount`
- `paid_amount`
- `visit_type`
- `symptoms`
- `diagnosis`
- `treatment_plan`
- `follow_up_required`
- `lab_tests_ordered`
- `radiology_ordered`
- `triage_level`
- حقول تأمين وضريبة ودفع قسري وقفل مالي

الملاحظة: الكيان يحمل إدارياً ومالياً وسريرياً في نفس الجدول. هذا مقبول كبداية، لكنه أصبح نقطة ضغط عالية بسبب توسع المنطق.

### 3.2 المريض

`models/patient.py` يحتوي على بيانات أساسية جيدة:

- الاسم عربي/إنجليزي.
- الهوية.
- الهاتف.
- تاريخ الميلاد.
- الجنس.
- التأمين.
- الحمل.
- الحساسية عبر `PatientAllergy`.

النواقص التشغيلية:

- لا يوجد emergency contact.
- لا يوجد chronic conditions منظم.
- لا يوجد current medications منظم.
- لا يوجد blood type.
- الحساسية موجودة لكن يجب أن تظهر كتحذير ثابت في كل شاشة سريرية.

### 3.3 المواعيد

`models/appointment.py` يحتوي على:

- `patient_id`
- `doctor_id`
- `department_id`
- `starts_at`, `ends_at`
- `status`: `SCHEDULED|CONFIRMED|CANCELLED|NO_SHOW|DONE`
- `notes`

المشكلة: نوع الموعد، سبب الزيارة، الأعراض، أولوية الموعد، مصدر الموعد، حالة الوصول، وسبب no-show كلها ليست حقولاً منظمة. هذا يجعل التحويل من موعد إلى زيارة يعتمد على notes أو parsing.

### 3.4 القسم

`models/department.py` يستنتج نوع القسم من الاسم عبر `get_type()`:

- إن احتوى الاسم على lab/مختبر => lab.
- إن احتوى على radiology/أشعة => radiology.
- إن احتوى على emergency/طوارئ => emergency.
- وإلا general.

هذا هش جداً. تغيير اسم القسم أو إضافة تخصصات مثل Dental/Physio/Procedure قد يكسر تدفق الزيارة.

### 3.5 الطابور

`models/queue_management.py` يحتوي على `QueueManagement` و `QueueSettings`:

- `department_id`
- `patient_id`
- `visit_id`
- `queue_number`
- `priority_level`
- `status`
- `payment_status`
- `is_emergency`
- `force_entry`
- timestamps

الملاحظة: الطابور مرتبط بالقسم، لكن لا يوجد مفهوم واضح لـ `station` مثل reception/nurse/doctor/lab/radiology/pharmacy/cashier. لذلك يصبح القسم وحده غير كافٍ لشرح من عليه الدور الآن.

### 3.6 السجل الطبي

`models/medical_record.py` بسيط جداً:

- `patient_id`
- `title`
- `details`
- `created_by`

هذا لا يكفي كسجل encounter طبي حديث. المطلوب ليس مجرد notes، بل note بنمط منظم: chief complaint, HPI, exam, assessment, plan, diagnosis, procedures, orders, follow-up.

### 3.7 التمريض

`models/nurse.py` يحتوي على:

- `Nurse`
- `VitalSigns`
- `MedicationAdministrationLog`

النقطة الحرجة: `VitalSigns` لا يحتوي `visit_id`. لذلك يمكن معرفة آخر قياسات للمريض، لكن لا يمكن ضمان أنها قياسات هذه الزيارة.

### 3.8 الطوارئ

`models/emergency.py` يحتوي على `EmergencyCase` وفيه:

- `patient_id`
- `visit_id`
- `chief_complaint`
- `severity`
- `triage_notes`
- `vital_signs` كنص JSON
- `diagnosis`
- `treatment_plan`
- `status`

المشكلة: هذا يكرر حقول موجودة في Visit أو يجب أن تكون في Triage/ClinicalEncounter. وجود vital signs كنص JSON يمنع التحليل والفلترة والتنبيهات الدقيقة.

### 3.9 الخدمات والتسعير

`models/service.py` يحتوي على `ServiceMaster`:

- `code`
- `name/name_ar`
- `category`: doctor/lab/radiology/general
- `department_id`
- `base_price`
- `emergency_price`
- `insurance_price`
- `duration`
- `max_daily`
- `is_required`

ممتاز كبداية، لكن واجهة الاستقبال تسمح بخدمات يدوية تتحول إلى خدمات دائمة. الأفضل أن تكون الخدمات اليدوية temporary line items بانتظار اعتماد manager.

### 3.10 الدفع والفواتير

`models/payment.py` يحتوي على:

- `PaymentMethod`: CASH/CARD/WIRE/INSURANCE/FORCE
- `PaymentStatus`: PENDING/CONFIRMED/CANCELLED/REFUNDED
- `Payment` مرتبط بـ patient/visit/invoice.

`models/invoice.py` يحتوي على:

- `Invoice.status`: DRAFT/ISSUED/PAID/VOID
- `InvoiceService` لأسطر الخدمات.

المشكلة: `Visit.payment_status` يستخدم PENDING/PAID/PARTIAL/DEBT، وهي لغة مختلفة عن `PaymentStatus` و`Invoice.status`. هذا يخلق صعوبة عند تحديد إن كانت الزيارة مسموحة للطابور أو الإغلاق.

### 3.11 الصيدلية

`models/medication.py` يحتوي على:

- `Medication`
- `Prescription`
- `PrescriptionItem`
- `PrescriptionDispenseLog`

`routes/medication_routes.py` يعطي dashboard لأدوار doctor/nurse/pharmacist/admin/manager. هذا مفيد للإطلاع، لكن workflow الصيدلية يجب أن يكون مخصصاً أكثر للصيدلي: وصفات جاهزة للصرف، نقص مخزون، بدائل، صرف جزئي، إرجاع أو إلغاء.

### 3.12 التحويل بين الأقسام

`models/visit_transfer.py` يسجل:

- من قسم إلى قسم.
- من طبيب إلى طبيب.
- من قام بالتحويل.
- المصدر.

النقص:

- لا يوجد سبب التحويل.
- لا يوجد حالة قبول التحويل.
- لا يوجد تعليق من القسم المستقبل.
- لا يوجد SLA أو وقت انتظار.

---

## 4. منطق العمل الطبي المثالي للمركز

المسار المقترح:

```text
Patient Registration
  -> Appointment / Walk-in / Emergency
  -> Reception Check-in
  -> Payment / Insurance / Liability approval
  -> Queue Ticket
  -> Nurse Triage / Vitals
  -> Doctor Consultation
  -> Orders: Lab / Radiology / Prescription / Procedure
  -> Department Worklists
  -> Results / Dispense / Completion
  -> Doctor Review if needed
  -> Checkout / Follow-up
  -> Archive
```

### 4.1 الاستقبال

الاستقبال لا يجب أن يملأ كل شيء طبياً. دوره:

- تعريف المريض أو إضافته.
- تحديد نوع الدخول: موعد، دخول مباشر، طوارئ.
- اختيار القسم والطبيب إن مطلوب.
- إدخال الشكوى الرئيسية فقط.
- تحديد الدفع/التأمين/الإعفاء الإداري.
- إنشاء تذكرة الطابور.

### 4.2 التمريض

التمريض يستلم الحالات التي تحتاج triage:

- قياس العلامات الحيوية.
- تحديد مستوى triage.
- تأكيد الشكوى الرئيسية.
- إضافة ملاحظة تمريضية.
- تحويل للطبيب أو للطوارئ أو إرجاع للاستقبال عند نقص إداري.

### 4.3 الطبيب

الطبيب يرى:

- بيانات المريض المختصرة.
- حساسية وأدوية حالية وتحذيرات.
- vitals هذه الزيارة.
- تاريخ الزيارات السابقة.
- الطلبات والنتائج.

ويقوم بـ:

- SOAP note.
- تشخيص.
- خطة علاج.
- طلب مختبر/أشعة.
- وصفة.
- متابعة.
- إغلاق سريري.

### 4.4 المختبر

المختبر يرى فقط الطلبات المطلوبة منه:

- استلام الطلب/العينة.
- إدخال النتائج.
- تعليم النتائج الحرجة.
- اعتماد النتيجة.
- إبلاغ الطبيب/تحويل الحالة إلى review.

### 4.5 الأشعة

الأشعة ترى فقط طلبات التصوير:

- استلام الطلب.
- تنفيذ التصوير.
- رفع الصور/المرفقات.
- كتابة التقرير.
- الاعتماد.
- إبلاغ الطبيب.

### 4.6 الصيدلية

الصيدلية ترى فقط الوصفات المعتمدة:

- التحقق من التوفر.
- صرف الدواء.
- تسجيل الصرف.
- تعليم partial dispense إن نقص المخزون.

### 4.7 المحاسبة

المحاسبة ترى:

- الفواتير.
- الدفعات.
- التأمين.
- إغلاق الصندوق.

ولا ترى تفاصيل سريرية غير ضرورية.

---

## 5. Gap Analysis الموسع

| Area | Current behavior | Problem | Evidence path | Recommended behavior | Priority | Complexity |
|---|---|---|---|---|---|---|
| Visit status | `OPEN/IN_PROGRESS/COMPLETED/ARCHIVED` | لا يشرح المرحلة الحالية فعلياً | `models/visit.py` | إضافة lifecycle state مفصل أو service mapping | Critical | Medium |
| Queue status | `waiting/called/in_progress/completed/cancelled` | لغة مختلفة عن Visit | `models/queue_management.py` | توحيد constants uppercase | Critical | Low |
| Lab status | `REQUESTED/IN_PROGRESS/DONE` ونتائج `PENDING/READY/VALIDATED` | غير متصل بوضوح بحالة الزيارة | `models/lab_request.py` | order workflow واضح | High | Medium |
| Radiology status | `REQUESTED/IN_PROGRESS/DONE` | لا توجد مراحل report/upload/validate واضحة في الطلب الأساسي | `models/radiology_request.py` | Imaging workflow مستقل متصل بالزيارة | High | Medium |
| Appointment | notes فقط لمعظم التفاصيل | parsing هش عند check-in | `models/appointment.py`, `routes/reception.py` | حقول منظمة للسبب/الأعراض/نوع الموعد | High | Low/Medium |
| Department type | مستنتج من الاسم | يتكسر عند تغيير التسمية | `models/department.py` | حقل `department_type` ثابت | High | Medium |
| Create visit | route ضخم | صعوبة UX وصيانة وتكرار | `routes/reception.py` | Service layer + wizard | Critical | High |
| Lab order creation | احتمال إنشاء مكرر | duplication | `routes/reception.py` | `OrderService.create_lab_order_once` | Critical | Medium |
| Vitals | مرتبطة بالمريض فقط | لا تضمن أنها لهذه الزيارة | `models/nurse.py` | إضافة `visit_id` أو `TriageAssessment` | Critical | Medium |
| Emergency | vitals كنص JSON وتشخيص منفصل | ازدواجية وضعف بحث | `models/emergency.py` | دمج مع Visit/Triage/Encounter | High | Medium |
| Medical record | title/details فقط | لا يدعم SOAP/structured clinical note | `models/medical_record.py` | `ClinicalEncounter` | High | Medium |
| Payments | Payment/Visit/Invoice كل منها status مختلف | تضارب دخول الطابور والإغلاق | `models/payment.py`, `models/invoice.py`, `models/visit.py` | `BillingStateService` | Critical | Medium |
| Receipt | رقم إيصال لا يعني مطبوع/معتمد | `can_enqueue_visit` قد يرفض | `services/gatekeeper_service.py`, `routes/payment_routes.py` | توحيد receipt issued/printed/confirmed | Critical | Low/Medium |
| Services | خدمة يدوية تتحول لدائمة | تضخم catalog وخطأ أسعار | `routes/reception.py`, `models/service.py` | temporary service line + approval | Medium/High | Medium |
| Permissions | الطبيب/الممرض يرى كثيراً | خصوصية وضعف تركيز | `services/access_control_service.py` | role + department + ownership scope | High | Medium |
| Transfers | log بسيط | لا يوجد سبب/قبول/رفض | `models/visit_transfer.py` | transfer workflow | Medium | Low/Medium |
| Pharmacy | prescription منفصلة عن queue | لا توجد station للصيدلية | `models/medication.py`, `routes/medication_routes.py` | pharmacy worklist + queue station | High | Medium |

---

## 6. State Machine المقترحة للزيارة

### 6.1 الحالات

| State | Owner | Required before entering | Allowed next states |
|---|---|---|---|
| `DRAFT` | reception | patient selected | `REGISTERED`, `CANCELLED` |
| `REGISTERED` | reception | patient + department + visit reason | `PAYMENT_PENDING`, `READY_FOR_TRIAGE`, `READY_FOR_DOCTOR`, `CANCELLED` |
| `PAYMENT_PENDING` | reception/accountant | amount calculated | `READY_FOR_TRIAGE`, `READY_FOR_DOCTOR`, `CANCELLED` |
| `READY_FOR_TRIAGE` | nurse | paid/waived/approved | `TRIAGE_IN_PROGRESS`, `CANCELLED` |
| `TRIAGE_IN_PROGRESS` | nurse | nurse started | `READY_FOR_DOCTOR`, `EMERGENCY_ESCALATED` |
| `READY_FOR_DOCTOR` | doctor | triage done or triage not required | `DOCTOR_IN_PROGRESS`, `TRANSFERRED`, `CANCELLED` |
| `DOCTOR_IN_PROGRESS` | doctor | doctor started | `ORDERS_PENDING`, `READY_FOR_CHECKOUT`, `FOLLOW_UP_SCHEDULED` |
| `ORDERS_PENDING` | lab/radiology/pharmacy | orders created | `RESULTS_PENDING_REVIEW`, `READY_FOR_CHECKOUT` |
| `RESULTS_PENDING_REVIEW` | doctor | lab/radiology done | `DOCTOR_IN_PROGRESS`, `READY_FOR_CHECKOUT` |
| `READY_FOR_CHECKOUT` | reception/accountant | clinical closure | `COMPLETED`, `PAYMENT_PENDING` |
| `COMPLETED` | reception/doctor | clinical + financial closure | `ARCHIVED` |
| `ARCHIVED` | manager/system | audit complete | none |
| `CANCELLED` | reception/manager | reason | none |

### 6.2 Backend service المقترح

ملف جديد:

```text
services/visit_workflow_service.py
```

وظائف أساسية:

```python
class VisitWorkflowService:
    def transition(visit_id, action, actor_id, payload=None): ...
    def allowed_actions(visit, user): ...
    def required_fields_for_state(state): ...
    def next_owner(visit): ...
    def create_event(visit, old_state, new_state, actor, action, payload): ...
```

ملف constants:

```text
constants/workflow.py
```

يحتوي:

```python
class VisitState:
    DRAFT = "DRAFT"
    REGISTERED = "REGISTERED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    READY_FOR_TRIAGE = "READY_FOR_TRIAGE"
    TRIAGE_IN_PROGRESS = "TRIAGE_IN_PROGRESS"
    READY_FOR_DOCTOR = "READY_FOR_DOCTOR"
    DOCTOR_IN_PROGRESS = "DOCTOR_IN_PROGRESS"
    ORDERS_PENDING = "ORDERS_PENDING"
    RESULTS_PENDING_REVIEW = "RESULTS_PENDING_REVIEW"
    READY_FOR_CHECKOUT = "READY_FOR_CHECKOUT"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"
    CANCELLED = "CANCELLED"
```

---

## 7. Queue Engine المقترح

### 7.1 المفهوم

الطابور يجب أن يكون طابور محطات وليس فقط طابور أقسام.

```text
Visit -> Queue Ticket -> Station
```

المحطات:

- `RECEPTION`
- `NURSE_TRIAGE`
- `DOCTOR`
- `LAB_SAMPLE`
- `LAB_RESULT`
- `RADIOLOGY`
- `PHARMACY`
- `CASHIER`

### 7.2 حالات الطابور

| Queue status | Meaning |
|---|---|
| `WAITING` | ينتظر |
| `CALLED` | تم استدعاؤه |
| `SERVING` | تحت الخدمة |
| `DONE` | انتهت المحطة |
| `SKIPPED` | تخطى الدور |
| `RECALLED` | أُعيد استدعاؤه |
| `CANCELLED` | ألغي |

### 7.3 أولوية الطابور

| Priority | Sort order |
|---|---|
| `EMERGENCY` | 0 |
| `URGENT` | 1 |
| `APPOINTMENT` | 2 |
| `NORMAL` | 3 |
| `LOW` | 4 |

### 7.4 قواعد مهمة

- لا يدخل المريض طابور الطبيب قبل إكمال الدفع أو الموافقة أو triage المطلوب.
- لا تظهر تذكرة في lab إلا إذا يوجد `LabRequest` فعلي.
- لا تظهر تذكرة في pharmacy إلا إذا يوجد `Prescription.active` ومغلقة من الطبيب.
- كل انتقال queue يسجل event.
- لا يسمح بوجود أكثر من ticket فعال لنفس visit ونفس station.

---

## 8. خطة إعادة تصميم واجهة إنشاء الزيارة

الملف الحالي: `templates/reception/create_visit.html`

### 8.1 الشكل المقترح

تقسيم الصفحة إلى wizard:

1. اختيار/إضافة المريض.
2. سبب الزيارة والوجهة.
3. الخدمات والتكلفة.
4. الدفع/التأمين/السماح الإداري.
5. التأكيد والطباعة.

### 8.2 Step 1 — المريض

حقول ظاهرة:

- البحث بالاسم/الهوية/الهاتف.
- بطاقة المريض.
- العمر والجنس والهاتف.
- حساسية إن وجدت.
- حالة الحمل إن وجدت.
- زر إضافة مريض جديد.

لا تظهر حقول الدفع أو الفحوصات في هذه الخطوة.

### 8.3 Step 2 — الوجهة

حقول:

- نوع الدخول: موعد / مباشر / طوارئ / مراجعة.
- القسم.
- الطبيب إذا القسم طبي عام.
- الشكوى الرئيسية.
- أولوية أولية.

### 8.4 Step 3 — الخدمات

- خدمات القسم فقط.
- إذا مختبر: تظهر تحاليل.
- إذا أشعة: تظهر modality/body part.
- إذا طبيب: تظهر كشف/استشارة فقط.
- خدمة يدوية تكون مؤقتة، لا تدخل catalog دائم إلا بموافقة manager.

### 8.5 Step 4 — الدفع

- طريقة الدفع.
- مبلغ مطلوب.
- مبلغ مدفوع.
- تأمين: شركة/رقم عضوية/نسبة تغطية.
- بطاقة: آخر 4 أرقام + POS.
- سماح إداري: سبب وموافقة لاحقة.

### 8.6 Step 5 — التأكيد

يعرض ملخصاً واضحاً:

- المريض.
- القسم.
- الطبيب/الموظف.
- المطلوب الآن.
- رقم الطابور.
- هل يحتاج triage؟
- هل الدفع مكتمل؟
- أزرار: حفظ، طباعة إيصال، طباعة تذكرة، فتح الزيارة.

---

## 9. Permission Matrix المقترحة

| Role | Can see | Can create | Can edit | Must not access |
|---|---|---|---|---|
| `super_admin` | كل شيء إداري وتقني | مستخدمين/إعدادات | إعدادات وصلاحيات | لا يستخدم يومياً كطبيب إلا بصلاحية سريرية صريحة |
| `admin` | إدارة النظام | مستخدمين/أقسام | إعدادات تشغيلية | تفاصيل سريرية غير لازمة |
| `manager` | تقارير وموافقات | موافقات/تعريفات | أسعار/كادر/صلاحيات | ملاحظات سريرية تفصيلية إلا عند الحاجة |
| `reception` | بيانات إدارية، زيارات، طوابير | مريض/موعد/زيارة | بيانات إدارية قبل الإغلاق | تشخيص وخطة علاج |
| `nurse` | زيارات تحتاج triage أو تمريض | vitals/assessment | قياسات وملاحظات تمريضية | دفع وتقارير مالية |
| `doctor` | زياراته وسياق المريض الطبي | تشخيص/طلبات/وصفة | ملاحظاته وطلباته | زيارات غيره إلا صلاحية استشارة |
| `lab` | طلبات المختبر | نتائج | نتائج قبل الاعتماد | كل ملف المريض غير اللازم |
| `radiology` | طلبات الأشعة | تقارير وصور | تقرير قبل الاعتماد | بيانات مالية |
| `pharmacist` | وصفات معتمدة | صرف | حالة الصرف | تشخيص تفصيلي غير لازم |
| `accountant` | فواتير ودفعات | دفعة/إغلاق | مالي فقط | SOAP/تشخيص/نتائج تفصيلية |
| `emergency` | حالات الطوارئ | دخول سريع/triage طوارئ | بيانات طوارئ | صلاحيات مالية موسعة |

---

## 10. Patient Context Panel موحد

يجب بناء مكوّن مشترك لكل شاشة سريرية:

```text
templates/shared/_patient_context_panel.html
```

يعرض حسب الدور:

### للجميع تقريباً

- الاسم.
- العمر/الجنس.
- رقم الملف.
- الحساسية.
- تنبيه حمل.
- آخر زيارة.

### للطبيب/التمريض

- الشكوى الرئيسية.
- vitals هذه الزيارة.
- آخر تشخيصات.
- آخر أدوية.
- نتائج حديثة.

### للمختبر/الأشعة

- الطلب المطلوب.
- الشكوى المختصرة إذا مهمة.
- الطبيب الطالب.
- أولوية الطلب.

### للمحاسبة

- رقم الزيارة.
- الخدمة.
- المبلغ.
- التأمين.
- حالة الدفع.

---

## 11. Backend Refactor Plan

### 11.1 ملفات جديدة مقترحة

```text
constants/workflow.py
services/visit_workflow_service.py
services/order_service.py
services/clinical_context_service.py
services/permission_scope_service.py
services/billing_state_service.py
services/appointment_checkin_service.py
models/visit_workflow_event.py
models/visit_order.py
models/triage_assessment.py
models/clinical_encounter.py
models/queue_event.py
models/pharmacy_work_item.py
```

### 11.2 تقليل منطق routes

الهدف أن تصبح routes كالتالي:

```python
def create_visit():
    form = VisitCreateForm.from_request(request)
    result = VisitRegistrationService.create_visit(form, current_user)
    return redirect_or_json(result)
```

بدل احتواء route على:

- تحقق دفع.
- إنشاء مريض.
- إنشاء خدمات.
- إنشاء مختبر.
- إنشاء أشعة.
- حساب تأمين.
- إنشاء دفعات.
- إدخال طابور.

### 11.3 Service ownership

| Service | Responsibility |
|---|---|
| `VisitRegistrationService` | إنشاء الزيارة من الاستقبال |
| `VisitWorkflowService` | انتقالات الحالة |
| `QueueService` | الطوابير والاستدعاء |
| `OrderService` | lab/radiology/pharmacy orders |
| `PaymentGatekeeperService` | السماح بالدخول/الدفع |
| `BillingStateService` | توحيد visit/payment/invoice state |
| `ClinicalContextService` | جلب سياق المريض لكل دور |
| `PermissionScopeService` | تحديد scope حسب role/department/tenant |
| `AppointmentCheckinService` | تحويل الموعد إلى زيارة بدون parsing notes |
| `TransferService` | تحويل الزيارات بين الأقسام مع قبول/رفض/سبب |

---

## 12. نماذج بيانات تفصيلية مقترحة

### 12.1 `ClinicalEncounter`

الغرض: توثيق الكشف السريري المنظم بدل الاعتماد على `Visit.diagnosis/treatment_plan` فقط.

Fields:

```text
id
visit_id
patient_id
doctor_id
chief_complaint
history_of_present_illness
review_of_systems
physical_exam
assessment
plan
diagnosis_text
diagnosis_code
procedure_notes
follow_up_required
follow_up_date
created_at
updated_at
signed_at
signed_by
```

### 12.2 `TriageAssessment`

الغرض: ربط التمريض بهذه الزيارة تحديداً.

Fields:

```text
id
visit_id
patient_id
nurse_id
chief_complaint_confirmed
triage_level
pain_score
bp_systolic
bp_diastolic
heart_rate
temperature
oxygen_saturation
respiratory_rate
weight
height
notes
started_at
completed_at
```

### 12.3 `VisitWorkflowEvent`

الغرض: audit واضح لكل حركة.

Fields:

```text
id
visit_id
from_state
to_state
action
actor_id
actor_role
notes
payload_json
created_at
```

### 12.4 `QueueEvent`

Fields:

```text
id
queue_id
visit_id
from_status
to_status
action
actor_id
station
notes
created_at
```

### 12.5 `Order` / `OrderItem`

بدل إنشاء LabRequest/RadiologyRequest مباشرة من عدة أماكن:

```text
Order:
  id
  visit_id
  patient_id
  order_type: LAB/RADIOLOGY/PHARMACY/PROCEDURE
  ordered_by
  status
  priority
  created_at

OrderItem:
  id
  order_id
  service_id
  service_code
  service_name
  status
  price
  notes
```

يمكن إبقاء `LabRequest` و`RadiologyRequest` كجداول تنفيذية، لكن الإنشاء يكون عبر `OrderService` فقط.

---

## 13. UX Redesign تفصيلي حسب الدور

### 13.1 Reception Dashboard

يجب أن تعرض:

- زيارات اليوم حسب الحالة.
- مرضى ينتظرون دفع.
- مرضى جاهزون للتمريض.
- مرضى لم يدخلوا الطابور بسبب مشكلة دفع/إيصال.
- مواعيد اليوم: Scheduled/Confirmed/Arrived/No-show.
- أزرار واضحة: Check-in, Pay, Print Ticket, Transfer.

### 13.2 Nurse Dashboard

يجب أن تعرض:

- `READY_FOR_TRIAGE`.
- حالات طوارئ أولاً.
- زيارات بدون vitals.
- vitals abnormal alerts.
- زر: Start Triage.
- زر: Complete and send to doctor.

### 13.3 Doctor Dashboard

يجب أن تعرض:

- مرضى جاهزون للطبيب.
- مريض قيد الكشف.
- نتائج تنتظر المراجعة.
- follow-up due.
- زر: Start encounter.
- زر: Order lab/radiology.
- زر: Prescribe.
- زر: Complete clinical visit.

### 13.4 Lab Dashboard

يجب أن تعرض:

- طلبات بانتظار عينة.
- طلبات قيد العمل.
- نتائج تحتاج اعتماد.
- critical results.
- زر: Receive sample.
- زر: Enter results.
- زر: Validate.

### 13.5 Radiology Dashboard

- طلبات بانتظار تصوير.
- قيد التصوير.
- تقارير draft.
- تقارير تحتاج اعتماد.
- زر: Start imaging.
- زر: Upload images.
- زر: Draft report.
- زر: Validate report.

### 13.6 Pharmacy Dashboard

- وصفات جاهزة للصرف.
- أدوية ناقصة.
- صرف جزئي.
- سجل صرف.
- تنبيه تداخلات دوائية.

### 13.7 Accountant Dashboard

- زيارات تنتظر دفع.
- زيارات دفع جزئي.
- دين يحتاج موافقة.
- تأمين ينتظر مطالبة.
- إغلاق يومي.
- لا يعرض diagnosis/clinical notes.

---

## 14. Roadmap التنفيذ

### Phase 0 — Safety & Inventory

**الهدف:** لا تغيير سلوك. فقط توثيق وتثبيت.

Files:

- `models/visit.py`
- `models/queue_management.py`
- `models/lab_request.py`
- `models/radiology_request.py`
- `models/medication.py`
- `routes/reception.py`

Actions:

- استخراج كل status strings.
- توثيق mappings.
- إضافة checklist للتناقضات.

Validation:

```powershell
python -m compileall .
pytest -q tests/test_app_factory.py
```

### Phase 1 — Constants & Status Cleanup

**الهدف:** توحيد الأسماء بدون كسر DB.

Actions:

- إنشاء `constants/workflow.py`.
- عدم تغيير القيم في DB فوراً.
- إضافة mapping functions:
  - `normalize_visit_status`
  - `normalize_queue_status`
  - `normalize_order_status`

Risks:

- كسر templates التي تتوقع strings قديمة.

Validation:

```powershell
python -m compileall constants services models routes
```

### Phase 2 — Fix Department Type

**الهدف:** عدم الاعتماد على الاسم.

Actions:

- إضافة `department_type` إلى `Department`.
- migration تملأ القيم من `get_type()` مرة واحدة.
- تحديث أي code يعتمد على `get_type()` ليستخدم الحقل الجديد.

Suggested values:

```text
GENERAL
LAB
RADIOLOGY
EMERGENCY
PHARMACY
NURSING
FINANCE
ADMIN
```

### Phase 3 — Prevent Duplicate Orders

**الهدف:** منع تكرار طلب المختبر والأشعة.

Actions:

- إنشاء `services/order_service.py`.
- نقل إنشاء `LabRequest/LabResult/RadiologyRequest` من `routes/reception.py`.
- ضمان idempotency:
  - نفس visit + نفس service لا يتكرر.

Validation:

- إنشاء زيارة مختبر بفحصين.
- التأكد من `LabRequest` واحد و`LabResult` بعدد الفحوصات.
- إنشاء زيارة أشعة بفحصين.

### Phase 4 — Billing State Fix

**الهدف:** إصلاح فجوة الدفع/الإيصال/الطابور.

Actions:

- إنشاء `BillingStateService`.
- توحيد معنى:
  - `receipt_number`
  - `receipt_printed`
  - `payment_status`
  - `invoice.status`
  - `payment.status`
- عند الدفع المؤكد، تحديد هل الإيصال issued/printed أم لا.
- تعديل gatekeeper ليفرق بين:
  - paid
  - receipt issued
  - receipt printed
  - financially cleared

### Phase 5 — Visit Workflow Service

**الهدف:** source of truth لحالة الزيارة.

Actions:

- إنشاء `VisitWorkflowService`.
- إضافة `VisitWorkflowEvent`.
- استعماله في create visit فقط أولاً.

Validation:

- كل زيارة جديدة تسجل event.
- كل انتقال يسجل old/new state.

### Phase 6 — Queue Engine Refactor

**الهدف:** معرفة من عليه الدور الآن.

Actions:

- إضافة مفهوم `station`.
- منع ticket مكرر لنفس station.
- بناء `next_action` لكل زيارة.

Validation:

- Reception creates visit -> queue station correct.
- Nurse completes triage -> doctor queue appears.
- Doctor orders lab -> lab queue appears.

### Phase 7 — Reception Wizard

**الهدف:** تحسين UX بدون إخفاء وظائف.

Actions:

- تقسيم template إلى partials.
- progressive disclosure.
- validation في كل خطوة.
- summary final step.

Validation:

- مستخدم الاستقبال يستطيع إنشاء زيارة عادية خلال أقل من دقيقة.
- لا تظهر حقول التأمين إلا عند اختيار تأمين.
- لا تظهر حقول الأشعة إلا عند اختيار قسم أشعة أو خدمة أشعة.

### Phase 8 — Nurse/Triage Integration

**الهدف:** جعل التمريض مرحلة واضحة.

Actions:

- إضافة `visit_id` إلى `VitalSigns` أو نموذج `TriageAssessment`.
- ربط vitals بالزيارة الحالية.
- الطبيب يرى vitals الخاصة بهذه الزيارة أعلى الشاشة.

Validation:

- زيارة تحتاج triage لا تبدأ عند الطبيب قبل vitals إلا إذا emergency override.

### Phase 9 — Appointment Check-in Refactor

**الهدف:** تحويل الموعد إلى زيارة بدون notes parsing.

Actions:

- إضافة حقول منظمة للموعد:
  - `appointment_type`
  - `chief_complaint`
  - `symptoms`
  - `arrival_status`
  - `arrived_at`
  - `no_show_reason`
- إنشاء `AppointmentCheckinService`.

### Phase 10 — Emergency Unification

**الهدف:** دمج الطوارئ مع visit/triage/encounter.

Actions:

- لا تخزن vital signs كـ JSON نصي جديد.
- استخدم `TriageAssessment`.
- اجعل `EmergencyCase` extension للحالة الطارئة لا بديلاً عن visit.

### Phase 11 — Department Handoff

**الهدف:** المختبر والأشعة والصيدلية تصبح worklists واضحة.

Actions:

- Lab worklist by state.
- Radiology worklist by state.
- Pharmacy queue for active prescriptions.
- Doctor review queue for completed results.

Validation:

- الطبيب يطلب فحص -> يظهر في lab.
- lab يعتمد النتيجة -> تظهر عند الطبيب كمراجعة.
- الطبيب يغلق الزيارة -> checkout.

### Phase 12 — Permission Scope

**الهدف:** الخصوصية والتركيز.

Actions:

- بناء `PermissionScopeService`.
- الطبيب يرى زياراته أو consultations المسموحة.
- nurse يرى قسمه/مهامه.
- lab/radiology يرى الطلبات فقط.
- accountant يرى المالي فقط.

Validation:

- اختبار كل دور على صفحات المرضى والزيارات والطلبات.

### Phase 13 — Dashboards & Reporting

**الهدف:** كل دور يرى ما يحتاجه الآن.

Dashboards:

- Reception: today's visits, pending payments, queue problems.
- Nurse: vitals due, triage waiting, abnormal alerts.
- Doctor: ready patients, results to review, active visit.
- Lab: samples waiting, results pending validation, critical results.
- Radiology: imaging waiting, reports pending.
- Pharmacy: prescriptions ready to dispense.
- Accountant: unpaid, partial, insurance, daily closure.
- Manager: bottlenecks and approvals.

---

## 15. Checklist: no contradictions / no repetition / no missing flow

قبل أي release بعد التنفيذ:

### Visit lifecycle

- [ ] كل زيارة لديها state واضح.
- [ ] كل state له owner واضح.
- [ ] كل transition يسجل event.
- [ ] لا يوجد route يغير status مباشرة خارج service.

### Queue

- [ ] لا يوجد أكثر من ticket فعال لنفس visit/station.
- [ ] كل ticket له station.
- [ ] كل station تعرف أزرارها: call/start/finish/skip/cancel.
- [ ] priority موحدة.

### Orders

- [ ] لا يوجد LabRequest مكرر لنفس visit/services.
- [ ] لا يوجد RadiologyRequest مكرر لنفس visit/service.
- [ ] النتائج المعتمدة تظهر للطبيب.
- [ ] النتائج الحرجة تظهر كتنبيه.

### UX

- [ ] إنشاء زيارة عادية لا يعرض حقول غير لازمة.
- [ ] إنشاء زيارة طوارئ سريع لا يطلب بيانات كاملة.
- [ ] الدفع والتأمين يظهران فقط في سياقهما.
- [ ] المستخدم يعرف دائماً ما الخطوة التالية.

### Permissions

- [ ] كل دور يرى البيانات اللازمة فقط.
- [ ] finance لا يرى ملاحظات سريرية تفصيلية.
- [ ] lab/radiology لا يرون كل الزيارات.
- [ ] doctor لا يرى كل زيارات الأطباء الآخرين إلا بصلاحية واضحة.

### Data retrieval

- [ ] الطبيب يرى vitals الخاصة بهذه الزيارة.
- [ ] lab يرى الطلبات المطلوبة فقط.
- [ ] radiology يرى modality/body part/notes.
- [ ] pharmacy يرى الوصفات المعتمدة فقط.

### Billing

- [ ] payment status موحد بين visit/payment/invoice.
- [ ] receipt issued/printed/confirmed واضحة.
- [ ] الطابور لا يعتمد على علم غير مضبوط.
- [ ] الدين والإعفاء الإداري لهما موافقة واضحة وسجل audit.

---

## 16. قرار البداية الموصى به

لا تبدأ بتجميل الواجهة أولاً. البداية الصحيحة:

1. توحيد constants والحالات.
2. إصلاح فجوة `receipt_printed` / `receipt_number` / دخول الطابور.
3. منع تكرار lab/radiology orders.
4. إضافة `visit_id` إلى vitals أو إنشاء `TriageAssessment`.
5. إنشاء `VisitWorkflowService` بسيط.
6. ربط create visit به.
7. بعد ثبات المنطق، إعادة تصميم واجهة الاستقبال كـ wizard.

السبب: إذا تم تجميل الواجهة قبل توحيد workflow، سيتم فقط إخفاء الفوضى لا حلها.

---

## 17. ملاحظة تنفيذية

هذه الوثيقة خطة تحليل وتحسين. لا تتضمن أي تعديل كود تنفيذي. التنفيذ يجب أن يتم على مراحل صغيرة، وكل مرحلة يجب أن تكون قابلة للاختبار والرجوع عنها، مع تجنب تعديل ملفات `tests/*` أو `logs/*` إلا بقرار واضح ومنفصل.

يجب أن يكون كل commit لاحقاً محدوداً وواضحاً:

```text
Phase 1: constants only
Phase 2: billing gatekeeper consistency
Phase 3: order creation deduplication
Phase 4: triage visit binding
Phase 5: workflow service initial integration
```

ولا يتم دمج أكثر من مرحلة في commit واحد.
