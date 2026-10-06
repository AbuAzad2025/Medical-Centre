# سيناريوهات رحلة المريض الشاملة — End-to-End Medical Scenarios

> **أصل هذا المستند:** تدقيق مباشر لشيفرة النظام (routes / models / services / migrations / seeds)،
> وليس اجتهاداً من التوثيق. كل رقم في المصفوفة أدناه مُشتق من كود قابل للتنفيذ أو مُوثَّق بملف وسطر.
>
> **قاعدة صارمة:** لا يُكتب في هذه السيناريوهات سلوك غير موجود. حيث تكون الميزة
> **غير منفَّذة**، يُكتب `applicable: false` مع السبب — ولا يُخترع سعر باقة أو تحمّل تأمين.
> المسارات التي يستحيل تنفيذها موثّقة في [blocked-journeys.md](blocked-journeys.md) بدل تلفيقها.

---

## 1) خلاصة التدقيق (Phase 1)

| البُعد | القيمة |
|---|---|
| قواعد المسارات | 761 (منها **752 إنتاجية** + 9 متسربة من `tests/conftest.py` إلى `route_inventory.json`) |
| Blueprints مسجّلة | 61 |
| ملفات النماذج | 90 (~204 صنفاً) |
| الخدمات | 74 |
| التهجيرات | 69 — الرأس `s3_017_rbac_catalogue_readable` |
| RLS | 20 `ENABLE` · 23 `FORCE` · 30 `CREATE POLICY` عبر 14 ملفاً |
| عزل ORM | 4 طبقات في `app/shared/tenant_filter.py` |
| نماذج تحمل `tenant_id` | 200 من 204 |

### 1.1 أربع قدرات مفترضة في المواصفة **غير موجودة**

| القدرة المفترضة | الواقع في الشيفرة |
|---|---|
| **الباقات / الحزم السريرية** | **غير موجودة.** صفر `Package`/`Bundle` في `models/`. كل ما يُسمّى "package" هو اشتراك SaaS لمستأجر المنصة (`app/core/saas/models.py:73`). لا عناصر مشمولة، لا نافذة صلاحية، لا رسوم خارج الباقة، لا سقف. `LabTestPanel` (`models/lab_test_catalog.py:45`) **بلا سعر** وبلا مفتاح أجنبي من `LabRequest`. |
| **تحمّل / فرنشيز / استثناءات التأمين** | **غير منفَّذة.** `grep -i "deductible\|copay\|exclusion"` ← **صفر نتيجة**. القاعدة الوحيدة: `patient_share = total × (1 − coverage/100)` (`models/visit.py:285-302`). نسبة التغطية يكتبها موظف الاستقبال يدوياً. السقف الوحيد الحقيقي — `InsuranceProvider.max_coverage_amount` (`models/pricing.py:206`) — **شيفرة ميتة، صفر مستدعين**. |
| **الجراحة / غرف العمليات** | **قراءة فقط.** `routes/or_management_routes.py` = 53 سطراً، مساران GET، **ولا POST/PUT/DELETE في أي مكان**. لا `SurgeryService`. `SurgerySchedule` لا يُنشأ في أي موضع. النموذج ممتاز (قائمة WHO، 5 مفاتيح للفريق) لكن **لا كاتب**. |
| **ملخص الخروج** | **غير موجود.** لا `DischargeSummary` ولا مسار. خروج:|:fffffffffff intern الخ intern `'summary_notes'` كنص حر في `Admission.discharge_diagnosis` (`services/admission_service.py:135-140`). |

### 1.2 فجوات إضافية

- **eMAR غير قابل للوصول:** لا شيء في التطبيق ينشئ صفوف `eMARAdministration` إطلاقاً
  (الاستثناء الوحيد `tests/test_high_risk_hardening.py:83`)، فتبقى صفحات `/emar/*` فارغة دائماً.
- **"الدفع المؤسسي / Corporate" غير موجود** كنموذج — يُمثَّل كـ`InsuranceCompany` أو نقداً.
- **الوعي الطبي التلقائي غير موجود:** لا حساب ESI ولا فرز مقود بالعلامات الحيوية.
- **التحويل بين الأقسام:** لا `DepartmentTransfer`. الآلية الفعلية `VisitTransferLog`
  (`models/visit_transfer.py:7`) + قاعدة "Hub-and-Spoke" التي تسمح فقط بـ`reception ↔ clinical`
  وتُعطّل التحويل بين الأقسام نظراء (`services/queue_management_service.py:239-272`).

### 1.3 ما هو منفَّذ فعلاً ونهايتي

- **عمود العيادة الخارجية:** تسجيل ← `create_visit` (تسعير `calculate_visit_cost`،
  `routes/reception/visits.py:1109`) ← بوابة الدفع (`queue_management_service.py:319-341`،
  `PAID` وحدها تمرّ) ← قائمة الطبيب ← تشخيص ← مختبر/أشعة (إعادة توجيه Hub-and-Spoke)
  ← وصفة ← صرف ← `/payment/process/<id>` ← قيد محاسبي ← أرشفة
  (تشترط `SUM(invoice_services) == visit.total_amount`).
- **المختبر والأشعة:** آلات حالة كاملة + FHIR/HL7 + تعديل نتائج + إشارة القيم الحرجة.
- **الصيدلة:** `402` عند عدم السداد · `403` عند الدفع القسري غير المعتمد · `428` لم acknowledgment
  المواد المُخضعة للرقابة · فحص تفاعلات ثنائي لكل زوج · خصم مخزون بقفل صف `WITH FOR UPDATE`.
- **الرعاية الداخلية ADT:** `AdmissionService` + admit/transfer/discharge + مدة الإقامة + علامة إعادة الدخول.
- **دفتر الأستاذ المزدوج:** 13 حساباً افتراضياً، رفض القيود غير المتوازنة، بوابات idempotent، إقفال الفترات.
- **لتعدد المستأجرين:** 200/204 نموذجاً تحمل `tenant_id`، والإسناد التلقائي **fail-closed**
  يرفع `TenantIsolationError` عند أي إدراج بلا سياق مستأجر.

### 1.4 أخطاء مُصمَّم لتُختبَر في السيناريوهات

| المعرّف | العيب |
|---|---|
| `E1` | مسارات `/accountant/refunds/*` الثلاثة ترمي `TypeError` (kwarg خاطئ) ← 500 |
| `E2` | **دفعتان متطابقتان على نفس الزيارة تتصادمان على `idempotency_key`** — الثانية تُعيد `replayed=True` ولا تزيد `paid_amount` إطلاقاً |
| `E3` | مبالغ العملة الأجنبية تُقيَّد في دفاتر ILS دون تحويل |
| `E4` | حفظ سعر صرف يدوي واحد **يُعطّل كل الأسعار النشطة في قاعدة البيانات** (لا فلتر زوج عملات، لا فلتر مستأجر) |
| `E11` | مدفوعات الاستقبال تتجاوز `PaymentService` والدفتر المحاسبي و idempotency بالكامل |
| `E13` | `InsurancePayout` لا يصل إلى الدفتر — رصيد `1105` لا يُخفَّض أبداً |
| `E15` | مساران لبيع الصيدلة يختلفان في إ recognising الإيراد |
| `E19` | `DoctorPricing` **يستبدل** سعر القسم/الفهرس فيلغي الخصم، فتكلّف زيارة المتابعة أكثر من أول زيارة |

---

## 2) مصفوفة التغطية الكاملة — 40 سيناريو

| # | المعرّف | النطاق | نوع اللقاء | محور الاختبار |
|---|---|---|---|---|
| 1 | `SC-001` | Polyclinic | OPD | نقدي كامل: استشارة + CBC ← أرشفة |
| 2 | `SC-002` | Polyclinic | OPD | تأمين 80% + مطالبة ← فجوة `E13` |
| 3 | `SC-003` | Polyclinic | OPD | متابعة: خصم 30% مثبّت + فجوة `E19` |
| 4 | `SC-004` | Polyclinic | **ER** | إعفاء الطوارئ من بوابة الدفع ← فرز RED |
| 5 | `SC-005` | Polyclinic | OPD | دفع قسري ← اعتماد المدير ← فجوة الطابور |
| 6 | `SC-006` | Polyclinic | OPD | دفع جزئي + **تصادم `E2`** |
| 7 | `SC-007` | Polyclinic | OPD | رفض الطابور قبل السداد ← سباق استدعاء الطبيب |
| 8 | `SC-008` | Polyclinic | OPD | دورة حياة طلب المختبر + Hub-and-Spoke |
| 9 | `SC-009` | Polyclinic | OPD | أشعة + مراجعة ثانية + "ذكاء اصطناعي" وهمي |
| 10 | `SC-010` | Polyclinic | OPD | حساسية دوائية ← صرف + فجوة `E15` |
| 11 | `SC-011` | Specialized | OPD | **عيادة أسنان:** خريطة الأسنان (غير قابلة للفوترة) |
| 12 | `SC-012` | Specialized | OPD | **متابعة حمل:** حقول الحمل + تعارض أدوية |
| 13 | `SC-013` | Specialized | OPD | **فحص صحة تنفيذي:** طلبات متعددة ← فاتورة واحدة |
| 14 | `SC-014` | Specialized | OPD | **مختبر قائم بذاته:** بلا استقبال، دفع منفصل |
| 15 | `SC-015` | Specialized | OPD | **أشعة قائمة بذاتها:** بوابة قدرات المنصة تُرجع 404 عند التعطيل |
| 16 | `SC-016` | Polyclinic | OPD | Walk-in عيادة: دفع مقدّم عند الإنشاء |
| 17 | `SC-017` | Polyclinic | ER | **عاجل:** طابور `urgent` + exemption |
| 18 | `SC-018` | Polyclinic | OPD | حجز أونلاين + تسجيل وصول عبر الكشك |
| 19 | `SC-019` | Specialized | OPD | صيدلية قائمة: بيع POS + مرتجعات |
| 20 | `SC-020` | Specialized | OPD | نشر التذكيرات + **فجوة القراءة فقط** |
| 21 | `SC-021` | **Tertiary** | **IPD** | ER ← ترقيم ← **تحويل ER←ward محجوب ⛔** |
| 22 | `SC-022` | **Tertiary** | **IPD** | دخول من العيادة ← سرير ← **ICU/العناية** |
| 23 | `SC-023` | **Tertiary** | **IPD** | نقل بين الأسرة + حساب مدة الإقامة |
| 24 | `SC-024` | **Tertiary** | **IPD** | خروج `HOME` ← **فجوة ملخص الخروج** |
| 25 | `SC-025` | **Tertiary** | **IPD** | خروج `TRANSFER` ← `1100` قابل للتحصيل |
| 26 | `SC-026` | **Tertiary** | IPD | **حالة ولادة:** الإيراد لا يميّز ولادة من قيصرية — الحقل غير موجود |
| 27 | `SC-027` | **Tertiary** | **IPD** | **يوم جراحي ⛔** (لا كاتب لـ OR) |
| 28 | `SC-028` | **Tertiary** | **IPD** | **eMAR ⛔** (لا يُنشأ صف واحد) |
| 29 | `SC-029` | **Tertiary** | **IPD** | إعادة الدخول + راية إعادة الدخول |
| 30 | `SC-030` | **Tertiary** | **IPD** | **ATC / صيدلية المستشفى** + تناقص المخزون |
| 31 | `SC-031` | Polyclinic | — | طلب استرداد ← موافقة ← تنفيذ + **فجوة `E1`** |
| 32 | `SC-032` | Polyclinic | — | استرداد جزئي + عكس FIFO |
| 33 | `SC-033` | Polyclinic | — | دفع بالعملة الأجنبية ← **فجوة `E3`** + **`E4`** |
| 34 | `SC-034` | Polyclinic | — | المشتريات: طلب ← استلام ← قيد `1300/2005` |
| 35 | `SC-035` | Polyclinic | — | إقفال الفترة + ميزان المراجعة |
| 36 | `SC-036` | Polyclinic | — | إغلاق الصندوق اليومي + الفارق |
| 37 | `SC-037` | Polyclinic | — | تسليم المناوبة + تجميد النقد |
| 38 | `SC-038` | Polyclinic | — | التسوية: `Invoice` vs `Visit` ← **الكود الميت** |
| 39 | `SC-039` | Polyclinic | — | تجاوز الدفع القسري 5% ← رفض |
| 40 | `SC-040` | Polyclinic | — | تسوية شهادة Cerebral / رفض + `EOB` |

**مسارات ممنوعة من التوليد** — موثّقة في [blocked-journeys.md](blocked-journeys.md):
`BLOCKED-01` يوم جراحي · `BLOCKED-02` eMAR · `BLOCKED-03` ملخص خروج منظم ·
`BLOCKED-04` باقة سريرية · `BLOCKED-05` تحمّل/فرنشيز تأمين · `BLOCKED-06` رموز LOINC/CPT مُولّدة ·
`BLOCKED-07` سرير/غرفة مُنشأة عبر التطبيق · `BLOCKED-08` إحالة صادرة قابلة للإنشاء.

---

## 3) الملفات

| الملف | المحتوى |
|---|---|
| [`phase1-audit.md`](phase1-audit.md) | تقرير التدقيق الكامل مع الأدلة `file:line` |
| [`batch-01-outpatient-polyclinic.json`](batch-01-outpatient-polyclinic.json) | `SC-001` … `SC-010` |
| [`batch-02-specialized-centers.json`](batch-02-specialized-centers.json) | `SC-011` … `SC-020` |
| [`batch-03-inpatient-tertiary.json`](batch-03-inpatient-tertiary.json) | `SC-021` … `SC-030` |
| [`batch-04-financial-lifecycle.json`](batch-04-financial-lifecycle.json) | `SC-031` … `SC-040` |
| [`blocked-journeys.md`](blocked-journeys.md) | المسارات المستحيلة + البديل المتاح |

## 4) اصطلاح القيم

مفاتيح JSON بالإنجليزية (للتشغيل الآلي). القيم بالعربية مع الحفاظ على
المسارات وأسماء الأعمدة و قيم التعداد بالإنجليزية كما هي في الشيفرة
(مثل `PAID` و `PaymentStatus.DEBT`) — لأن توليد قيم غير موجودة في الكود
هو بالضبط الخطأ الذي يفشل في الاختبار.

### قيم التعدادات المعتمدة

```
Visit.status          OPEN | CHECKED_IN | IN_PROGRESS | COMPLETED | CANCELLED
PaymentStatus         PENDING | PARTIAL | PAID | DEBT
Visit.triage_level    RED | YELLOW | GREEN          (لا قيم أخرى يكتبها الكود)
EmergencyCase.severity LOW | MODERATE | HIGH | CRITICAL
LabRequest.status     REQUESTED | COLLECTED | RECEIVED | ANALYZING | REVIEWED | APPROVED | IN_PROGRESS | DONE | CANCELLED
LabResult.status      PENDING | READY | VALIDATED
RadiologyRequest      REQUESTED | IN_PROGRESS | DONE | CANCELLED
Prescription.status   active | issued | dispensed | cancelled     (CHECK في قاعدة البيانات)
Bed.status            AVAILABLE | OCCUPIED | RESERVED | CLEANING | OUT_OF_ORDER
Admission.discharge_type HOME | TRANSFER | DEATH | AGAINST_ADVICE
```
