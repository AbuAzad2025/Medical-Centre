# خطة تحسين منطق وتجربة استخدام النظام الطبي

**اسم الخطة:** Medical Center Workflow & UX Logic Improvement Plan  
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

---

## 1. الملفات التي بُني عليها التحليل

تم بناء الخطة على قراءة وفحص ملفات فعلية من الريبو، منها:

### Backend / Models

- `app_factory.py`
- `models/patient.py`
- `models/visit.py`
- `models/queue_management.py`
- `models/request_workflow.py`
- `models/lab_request.py`
- `models/radiology_request.py`
- `models/nurse.py`
- `models/medication.py`

### Backend / Routes

- `routes/reception.py`
- `routes/doctor.py`
- `routes/nurse_routes.py`
- `routes/lab.py`
- `routes/radiology.py`

### Backend / Services & Security

- `services/queue_management_service.py`
- `services/access_control_service.py`
- `services/gatekeeper_service.py`
- `utils/decorators.py`

### Frontend / Templates

- `templates/reception/create_visit.html`

---

## 2. الملخص التنفيذي

النظام يحتوي على مكونات كثيرة ومفيدة: مرضى، زيارات، مواعيد، طوابير، أطباء، تمريض، مختبر، أشعة، صيدلية، دفع، تأمين، طوارئ، تقارير، وصلاحيات. لكن هذه المكونات تعمل بمنطق متفرق. النتيجة أن تجربة المستخدم تبدو ثقيلة ومتعبة، خصوصاً في إنشاء الزيارة، الطوابير، الصلاحيات، وجلب سياق المريض بين الأقسام.

### أعلى 10 مشاكل حالية

| # | المشكلة | الأثر |
|---|---|---|
| 1 | تعدد حالات الزيارة والطابور والطلبات بدون قاموس موحد | تضارب بين الشاشات وصعوبة معرفة المرحلة الحالية |
| 2 | `create_visit` في `routes/reception.py` يجمع استقبال + دفع + تأمين + فحوصات + طابور + طوارئ | شاشة ثقيلة ومنطق هش |
| 3 | احتمال إنشاء طلب مختبر مكرر عند اختيار خدمات مختبرية | تكرار طلبات أو نتائج ناقصة |
| 4 | الطابور مرتبط بالدفع بطريقة غير واضحة للمستخدم | زيارة تنشأ لكن لا تدخل الطابور أو تظهر تحذيرات مربكة |
| 5 | التمريض ليس محطة إلزامية واضحة قبل الطبيب | الطبيب قد يستلم زيارة دون vitals/triage |
| 6 | الطبيب/الممرض/المختبر قد يرون بيانات أوسع مما يحتاجون | ضعف خصوصية وتجربة غير مركزة |
| 7 | واجهة إنشاء الزيارة تعرض حقول كثيرة دفعة واحدة | إرهاق المستخدم وزيادة أخطاء الإدخال |
| 8 | المختبر والأشعة يملكان statuses خاصة لا تتصل بوضوح بمسار الزيارة | الطبيب لا يعرف دائماً هل النتائج جاهزة أو تحتاج مراجعة |
| 9 | الصيدلية ليست محطة workflow كاملة ضمن مسار الزيارة | الوصفات والصرف يعملان بمعزل عن الطابور |
| 10 | منطق الصلاحيات موجود في decorators وservice وroutes بأشكال مختلفة | تناقض وتكرار وصعوبة صيانة |

### أعلى 10 توصيات

| # | التوصية | الأولوية |
|---|---|---|
| 1 | إنشاء `VisitWorkflowService` كمصدر وحيد لحالة الزيارة | Critical |
| 2 | توحيد status constants في ملف مركزي | Critical |
| 3 | فصل منطق إنشاء الطلبات والفحوصات عن `create_visit` إلى `OrderService` | Critical |
| 4 | إعادة تصميم `create_visit.html` كـ wizard من 5 خطوات | High |
| 5 | جعل التمريض/triage خطوة واضحة قبل الطبيب عند الحاجة | High |
| 6 | إنشاء queue state machine موحد بمحطات `station` | High |
| 7 | ضبط permission matrix حسب role + department + ownership | High |
| 8 | بناء patient context panel مشترك لكل الأقسام | High |
| 9 | توحيد lab/radiology/pharmacy handoff داخل workflow واحد | Medium/High |
| 10 | بناء audit trail لكل انتقال في الزيارة والطابور والطلبات | Medium/High |

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

### 3.2 الطابور

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

### 3.3 الطلبات

`models/lab_request.py`:

- `LabRequest.status`: `REQUESTED / IN_PROGRESS / DONE / CANCELLED`
- `LabResult.status`: `PENDING / READY / VALIDATED`

`models/radiology_request.py`:

- `RadiologyRequest.status`: `REQUESTED / IN_PROGRESS / DONE / CANCELLED`

`models/request_workflow.py`:

- `RequestWorkflow` عام، لكنه يعتمد على strings مثل `request_type`, `department`, `status`, `action` بدون قيود صارمة.

الملاحظة: توجد محاولة جيدة لتوثيق سير العمل، لكنها ليست محركاً حاكماً؛ هي أقرب لسجل نصي.

### 3.4 التمريض

`models/nurse.py` يحتوي على:

- `Nurse`
- `VitalSigns`
- `MedicationAdministrationLog`

الملاحظة: vitals موجودة، لكن ليست مرتبطة مباشرة بزيارة عبر `visit_id` في `VitalSigns`. الربط الحالي بالمريض والممرضة فقط. هذا يجعل الطبيب قد يرى آخر vitals للمريض، لكنها ليست بالضرورة vitals هذه الزيارة.

### 3.5 الصيدلية

`models/medication.py` يحتوي على:

- `Medication`
- `Prescription`
- `PrescriptionItem`
- `PrescriptionDispenseLog`

الملاحظة: الوصفة مرتبطة بـ `visit_id` اختيارياً، والحالة `active/dispensed/cancelled`. الصرف موجود، لكن لا يظهر كمرحلة رسمية في lifecycle الزيارة.

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

## 5. Gap Analysis

| Area | Current behavior | Problem | Evidence path | Recommended behavior | Priority | Complexity |
|---|---|---|---|---|---|---|
| Visit status | `OPEN/IN_PROGRESS/COMPLETED/ARCHIVED` | لا يشرح المرحلة الحالية فعلياً | `models/visit.py` | إضافة lifecycle state مفصل أو service mapping | Critical | Medium |
| Queue status | `waiting/called/in_progress/completed/cancelled` | لغة مختلفة عن Visit | `models/queue_management.py` | توحيد constants uppercase | Critical | Low |
| Lab status | `REQUESTED/IN_PROGRESS/DONE` ونتائج `PENDING/READY/VALIDATED` | غير متصل بوضوح بحالة الزيارة | `models/lab_request.py` | order workflow واضح | High | Medium |
| Radiology status | `REQUESTED/IN_PROGRESS/DONE` | لا توجد مراحل report/upload/validate واضحة في الطلب الأساسي | `models/radiology_request.py` | Imaging workflow مستقل متصل بالزيارة | High | Medium |
| Create visit | route ضخم | صعوبة UX وصيانة وتكرار | `routes/reception.py` | Service layer + wizard | Critical | High |
| Lab order creation | احتمال إنشاء مكرر | duplication | `routes/reception.py` | `OrderService.create_lab_order_once` | Critical | Medium |
| Vitals | مرتبطة بالمريض فقط | لا تضمن أنها لهذه الزيارة | `models/nurse.py` | إضافة `visit_id` إلى `VitalSigns` | High | Medium |
| Permissions | الطبيب/الممرض يرى كثيراً | خصوصية وضعف تركيز | `services/access_control_service.py` | role + department + ownership scope | High | Medium |
| Force payment | أسماء مختلفة: force/strong/emergency | ارتباك مالي وتشغيلي | `models/visit.py`, `services/gatekeeper_service.py` | توحيد مصطلح liability/administrative override | High | Medium |
| UI form | شاشة واحدة طويلة | UX ضعيف | `templates/reception/create_visit.html` | wizard + progressive disclosure | High | Medium/High |

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
models/visit_workflow_event.py
models/visit_order.py
models/triage_assessment.py
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
| `ClinicalContextService` | جلب سياق المريض لكل دور |
| `PermissionScopeService` | تحديد scope حسب role/department |

---

## 12. Roadmap التنفيذ

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

### Phase 2 — Prevent Duplicate Orders

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

### Phase 3 — Visit Workflow Service

**الهدف:** source of truth لحالة الزيارة.

Actions:

- إنشاء `VisitWorkflowService`.
- إضافة `VisitWorkflowEvent`.
- استعماله في create visit فقط أولاً.

Validation:

- كل زيارة جديدة تسجل event.
- كل انتقال يسجل old/new state.

### Phase 4 — Queue Engine Refactor

**الهدف:** معرفة من عليه الدور الآن.

Actions:

- إضافة مفهوم `station`.
- منع ticket مكرر لنفس station.
- بناء `next_action` لكل زيارة.

Validation:

- Reception creates visit -> queue station correct.
- Nurse completes triage -> doctor queue appears.
- Doctor orders lab -> lab queue appears.

### Phase 5 — Reception Wizard

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

### Phase 6 — Nurse/Triage Integration

**الهدف:** جعل التمريض مرحلة واضحة.

Actions:

- إضافة `visit_id` إلى `VitalSigns` أو نموذج `TriageAssessment`.
- ربط vitals بالزيارة الحالية.
- الطبيب يرى vitals الخاصة بهذه الزيارة أعلى الشاشة.

Validation:

- زيارة تحتاج triage لا تبدأ عند الطبيب قبل vitals إلا إذا emergency override.

### Phase 7 — Department Handoff

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

### Phase 8 — Permission Scope

**الهدف:** الخصوصية والتركيز.

Actions:

- بناء `PermissionScopeService`.
- الطبيب يرى زياراته أو consultations المسموحة.
- nurse يرى قسمه/مهامه.
- lab/radiology يرى الطلبات فقط.
- accountant يرى المالي فقط.

Validation:

- اختبار كل دور على صفحات المرضى والزيارات والطلبات.

### Phase 9 — Dashboards & Reporting

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

## 13. Checklist: no contradictions / no repetition / no missing flow

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

---

## 14. قرار البداية الموصى به

لا تبدأ بتجميل الواجهة أولاً. البداية الصحيحة:

1. توحيد constants والحالات.
2. منع تكرار lab/radiology orders.
3. إنشاء `VisitWorkflowService` بسيط.
4. ربط create visit به.
5. بعد ثبات المنطق، إعادة تصميم واجهة الاستقبال كـ wizard.

السبب: إذا تم تجميل الواجهة قبل توحيد workflow، سيتم فقط إخفاء الفوضى لا حلها.

---

## 15. ملاحظة تنفيذية

هذه الوثيقة خطة تحليل وتحسين. لا تتضمن أي تعديل كود تنفيذي. التنفيذ يجب أن يتم على مراحل صغيرة، وكل مرحلة يجب أن تكون قابلة للاختبار والرجوع عنها، مع تجنب تعديل ملفات `tests/*` أو `logs/*` إلا بقرار واضح ومنفصل.
