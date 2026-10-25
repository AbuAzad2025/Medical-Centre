# دليل المستخدم — User Guide

> دليل عملي لمستخدمي المركز (استقبال، طبيب، طبيب طوارئ، ممرض، مختبر، أشعة، صيدلية، محاسب، مدير، مالك). **آخر تحقق من الكود:** 25 أكتوبر 2026 — الإصدار 3.3.

---

## 1. تسجيل الدخول

- افتح عنوان المنصة (مثال: `https://your-domain.com` أو `http://localhost:8080` للتطوير).
- أدخل **اسم المستخدم** و**كلمة المرور**.
- في النظام السحابي (`ENABLE_SAAS_MODE=true`): يُختار المركز (tenant) تلقائياً حسب النطاق الفرعي (`clinic.your-domain.com`) أو المسار (`/t/clinic-slug/`).
- في وضع المركز الواحد (`ENABLE_SAAS_MODE=false`): يُربط المستأجر تلقائياً عبر `TENANT_DEFAULT_SLUG` — لا يظهر مُحدد المركز.
- بعد المحاولات الفاشلة: قفل الحساب → تفعيل MFA أو WebAuthn إذا كانت المنصة مفعّلة (`PLATFORM_CAP_WEBAUTHN=true`).

---

## 2. الاستقبال (`reception`) — لوحة: `/reception/dashboard`

**الوحدة المطلوبة:** `reception` — تبويب "الاستقبال" في الشريط الجانبي.

| الوظيفة | المسار | الوصف |
|----------|-------|-------|
| **تسجيل مريض جديد** | `/reception/patients/new` | الاسم (ثلاثي/رباعي)، الهوية الوطنية، جهة الاتصال، بيانات طبية أساسية (حساسية، تشخيصات سابقة). التحقق من تكرار الهوية داخل المركز. |
| **فتح زيارة** | `/reception/visits/new` | اختر القسم/الطبيب — تُنشئ طابوراً للعيادة مع حالة `OPEN`. |
| **إدارة الطابور الحي** | `/reception/queue` | عرض المرضى المنتظرين، استدعاء، تحويل، إنهاء. widget: `queue_live`. |
| **المواعيد** | `/reception/appointments` | جدولة، إلغاء، تأكيد، حجز من البوابة الإلكترونية. widget: `appointments_pending`. |
| **الصندوق النقدي** | `/reception/cash-register` | فتح/إقفال وردية، تسجيل مدفوعات نقدية، ملخص الصندوق. widget: `cash_summary` (يتطلب وحدة `billing`). |
| **متابعة الحالة** | `/reception/visits` | المريض في انتظار العيادة، المختبر، الأشعة، الصيدلية. widget: `visits_today`. |
| **تقارير الاستقبال** | `/reception/reports` | إحصائيات الزيارات، أوقات الانتظار، تحويلات. |

**الوحدات المرتبطة:** `appointments` (للمواعيد)، `billing` (للصندوق)، `lab`/`radiology`/`pharmacy` (لتحويل الطلبات).

---

## 3. الطبيب (`doctor`) — لوحة: `/doctor/dashboard`

**الوحدة المطلوبة:** `doctor` — تبويب "الطبيب" في الشريط الجانبي.

| الوظيفة | المسار | الوصف |
|----------|-------|-------|
| **لوحة اليوم** | `/doctor/dashboard` | قائمة الزيارات المعلقة، widget: `my_queue`، `patients_waiting`، `appointments_pending`، `lab_pending`، `radiology_pending`. |
| **فتح زيارة / نموذج SOAP** | `/doctor/visits/<id>` | شكوى (Subjective)، فحص (Objective)، تقييم (Assessment)، خطة (Plan). |
| **التشخيص** | داخل الزيارة | ترميز ICD-10 (مدوّن) + إجراءات CPT. |
| **الروشيتة الإلكترونية (e-prescription)** | `/doctor/prescriptions/new` | أدوية مع جرعات ومدة، فحص التفاعلات الدوائية (`drug_interactions`)، إرسال مباشر للصيدلية. |
| **طلب مختبر** | `/doctor/lab-requests/new` | اختيار التحاليل، ملاحظات سريرية — يصل لـ `lab.worklist`. |
| **طلب أشعة** | `/doctor/radiology-requests/new` | النمط (XRAY/CT/MRI/US)، العضو، ملاحظات — يصل لـ `radiology.worklist`. |
| **نماذج التخصص الديناميكية** | `/doctor/forms` | نماذج SOAP مخصصة لكل تخصص (قلب، عظام، جلدية...). راجع [DYNAMIC_FORM_GOVERNANCE.md](DYNAMIC_FORM_GOVERNANCE.md). |
| **التوقيع الإلكتروني** | عند الحفظ | للتقارير والنتائج عند تفعيل القدرة (`e_signature`). |
| **الاستشارات عن بعد** | `/telemedicine` | جلسة فيديو/صوت، وصفات، تحويلات — حسب تفعيل `telemedicine`. |

**الوحدات المرتبطة:** `lab`، `radiology`، `pharmacy`، `appointments`، `billing` (للتسعير).

---

## 3.1 طبيب الطوارئ (`er_doctor`) — لوحة: `/emergency/dashboard`

**الوحدة المطلوبة:** `emergency` — تبويب "الطوارئ" في الشريط الجانبي. **مُصحح في الإصدار 3.3:** الدخول الآن يوجه مباشرة لـ `/emergency/dashboard` عند تفعيل وحدة `emergency`.

| الوظيفة | المسار | الوصف |
|----------|-------|-------|
| **لوحة الطوارئ** | `/emergency/dashboard` | الحالات الحرجة، فرز سريع، قائمة انتظار الطوارئ. widgets: `critical_count`، `triage_board`، `emergency_waitlist`. |
| **فرز فوري (Triage)** | `/emergency/triage/<visit_id>` | تقييم ESI، علامات حيوية، أولوية، تنبيهات حرجة. |
| **زيارة طوارئ مسرّعة** | `/emergency/visits/new` | إنشاء زيارة مع حالة `EMERGENCY`، طلبات مختبر/أشعة عاجلة، مراجعة علامات حيوية. |
| **إدارة الأسرة** | `/emergency/beds` | حالة الأسرة، تنظيف، تخصيص. (يتطلب وحدة `inpatient`). |

**عزل:** طبيب الطوارئ **معزول** عن الإدارة طويلة الأمد، إعدادات النظام، والتقارير المالية — يرى فقط ما يخص الطوارئ.

---

## 4. المختبر (`lab`) — لوحة: `/lab/dashboard` أو `/lab/worklist`

**الوحدة المطلوبة:** `lab` — تبويب "المختبر".

| الوظيفة | المسار | الوصف |
|----------|-------|-------|
| **قائمة العمل** | `/lab/worklist` | طلبات التحاليل الواردة (حالة: `REQUESTED`، `IN_PROGRESS`، `DONE`). widget: `lab_pending`، `lab_recent`. |
| **سحب العينة** | `/lab/collect/<request_id>` | تأكيد الاستلام، تسجيل المعرّف (باركود)، وقت السحب. |
| **إدخال النتائج** | `/lab/results/<request_id>/edit` | قيم مع نطاقات مرجعية (رقمياً أو نصياً)، علامات غير طبيعية. |
| **اعتماد النتيجة** | `/lab/results/<request_id>/validate` | خطوة تحقق قبل التحرير للمريض/الطبيب (`result_validation`). |
| **ضبط الجودة (QC)** | `/lab/qc` | سجلات QC، مراقبة الكواشف، منحنى Levey-Jennings — عند تفعيل `enable_lab_qc`. |
| **التقارير** | `/lab/reports` | إحصائيات الحجم، أوقات التسليم، نتائج حرجة. |

**الوحدات المرتبطة:** `doctor` (طلبات)، `billing` (التسعير)، `inpatient` (عينات التنويم).

---

## 5. الأشعة (`radiology`) — لوحة: `/radiology/dashboard` أو `/radiology/worklist`

**الوحدة المطلوبة:** `radiology` — تبويب "الأشعة".

| الوظيفة | المسار | الوصف |
|----------|-------|-------|
| **قائمة العمل** | `/radiology/worklist` | طلبات الأشعة (حالة: `REQUESTED`، `IN_PROGRESS`، `DONE`، `DONE_TODAY`). widget: `radiology_pending`. |
| **استلام الطلب / التقاط الصورة** | `/radiology/acquire/<request_id>` | رفع ملف DICOM أو التقاط مباشر، تأكيد النمط (XRAY/CT/MRI/US). |
| **مسودة تقرير** | `/radiology/report/<request_id>/edit` | النتائج، الانطباع، التوصيات — قوالب جاهزة (`report_templates`)، ماكروات (`macros`). |
| **اعتماد وتوقيع** | `/radiology/report/<request_id>/sign` | توقيع إلكتروني، نشر للمريض/الطبيب. |
| **AI Imaging** | `/radiology/ai/<request_id>` | تحليل تلقائي للصور، تقارير مساعدة — عند تفعيل وحدة `ai_imaging` و `PLATFORM_CAP_AI_IMAGING`. |
| **PACS / DICOM** | `/radiology/pacs` | إرسال/استقبال DICOM — عند تفعيل `integration` مع `DICOM_LISTENER`. |

---

## 6. الصيدلية (`pharmacy`) — لوحة: `/medication/dashboard` (POS: `/medication/pos`)

**الوحدة المطلوبة:** `pharmacy` — تبويب "الصيدلية". POS متاح في `standalone_pharmacy` و `walkin_clinic` و `hospital`.

| الوظيفة | المسار | الوصف |
|----------|-------|-------|
| **صرف الروشيتة** | `/medication/dispense` | تأكيد التوافر، الصرف، خصم المخزون، سجل `prescription_dispense_logs`. widget: `pharmacy_dispense`، `pharmacy_prescriptions`. |
| **بيع مباشر (POS)** | `/medication/pos` | بيع بدون روشتة — فاتورة صيدلية، نقدي/بطاقة، إيصال. widget: `pharmacy_sales`. |
| **إدارة المخزون** | `/medication/inventory` | جرد، طلب شراء، استلام، تحويلات، تنبيه انخفاض المخزون (`auto_reorder`)، باركود. widget: `pharmacy_low_stock`. |
| **أدوية خاضعة للرقابة** | `/medication/controlled` | سجل صرف خاص، تحقق الهوية، تقارير دورية (`controlled_medications`). |
| **التفاعلات الدوائية** | تلقائي عند الصرف | فحص `drug_interactions`، تحذيرات الحساسية، جرعات قصوى. |

**الوحدات المرتبطة:** `doctor` (الروشيتات)، `inventory` (المخزون المشترك)، `billing` (التسعير، الفوترة).

---

## 7. التمريض (`nursing`) — لوحة: `/nurse/dashboard`

**الوحدة المطلوبة:** `nursing` — تبويب "التمريض".

| الوظيفة | المسار | الوصف |
|----------|-------|-------|
| **العلامات الحيوية** | `/nurse/vitals` | تسجيل قياسات الزيارة/الجناح (ضغط، حرارة، نبض، تشبع، تنفس، وزن). widget: `nurse_assigned`. |
| **الفرز (Triage)** | `/nurse/triage` | تقييم أولوية الطوارئ (ESI)، تسجيل شكوى رئيسية. |
| **إدارة الأدوية (eMAR)** | `/nurse/emar` | جدولة جرعات، تأكيد الصرف للمريض، سجل `medication_administration_logs`. |
| **إدارة الأسرّة والأجنحة** | `/nurse/beds` | حالة الأسرة، تنظيف، تخصيص، نقل — يتطلب وحدة `inpatient`. |
| **ملاحظات التمريض** | `/nurse/notes` | تسجيل ملاحظات دورية، handover بين الورديات (`shift_handovers`). |

---

## 8. الفوترة (`billing`) — لوحة: `/accountant/dashboard`

**الوحدة المطلوبة:** `billing` — تبويب "الفوترة" أو "المحاسبة".

| الوظيفة | المسار | الوصف |
|----------|-------|-------|
| **إنشاء فاتورة** | `/accountant/invoices/new` | من خدمات الزيارة (دواء/تحليل/أشعة/جلسة)، أسعار من `service_prices`. |
| **تسجيل دفعة** | `/accountant/payments/new` | نقدي/بطاقة/تحويل/شيك → إيصال تلقائي (`receipts`). |
| **الأقساط والتحصيل** | `/accountant/installments` | جدولة، تذكير، تحصيل الديون (`debt_management`). |
| **فواتير التأمين** | `/accountant/insurance` | شركات التأمين، المطالبات (`insurance_claims`)، EOB، الدفعات. |
| **التسعير** | `/accountant/pricing` | قائمة الخدمات والأسعار، أسعار خاصة، قواعد التسعير (`pricing_rules`). |
| **التقارير المالية** | `/accountant/reports` | إيرادات يومية/شهرية، أداء المصادر، مصروفات، تدفقات نقدية. widget: `finance_overview`، `revenue_today`، `pending_payments`. |

---

## 9. المحاسب والمدير (`accountant` / `manager`) — لوحة: `/accountant/dashboard` / `/manager/dashboard`

| الدور | اللوحة | الصلاحيات الإضافية |
|-------|---------|-------------------|
| `accountant` | `/accountant/dashboard` | كل وظائف الفوترة + `finance_overview`، `revenue_today`، `pending_payments`. |
| `manager` | `/manager/dashboard` | `manager_finance`، `manager_hr`، `queue_live` (عرض فقط)، إدارة المستخدمين، الوحدات، إعدادات المركز. |

---

## 10. المالك — منصة SaaS (`owner`) — لوحة: `/owner/owner_dashboard`

**الوحدة المطلوبة:** `owner` (دائم للمالكين) — تبويب "المالك" في الشريط الجانبي (مرئي فقط لـ `owner`، `super_admin`، `platform_owner`).

| الوظيفة | المسار | الوصف |
|----------|-------|-------|
| **إدارة المستأجرين** | `/owner/tenants` | عرض/تعديل/تعليق المراكز، حالات: `TRIAL` / `ACTIVE` / `PENDING` / `SUSPENDED` / `CANCELLED`. |
| **توفير يدوي** | `/owner/tenants/create` | إنشاء مركز جديد مع باقة، مالك، إعدادات أولية. |
| **التسجيل الذاتي** | `/saas/signup` | عامة — Stripe checkout → توفير تلقائي. |
| **إدارة الباقات** | `/owner/bundles` | عرض/تعديل `product_bundles`، الوحدات، الأسعار، الحدود. |
| **المؤشرات الكلية** | `/owner/analytics` | MRR، Churn، المراكز النشطة، الاستخدام، الفوترة الكلية (`analytics_global`). |
| **إدارة المستخدمين العامين** | `/owner/users` | `super_admin` فقط — إنشاء/تعطيل `platform_owner`، `super_admin`. |

---

## 11. بوابة المريض (`patient`) — لوحة: `/portal/dashboard`

**الوحدة المطلوبة:** `portal` (دائم للمريض) — تبويب "البوابة" أو رابط مباشر `/portal`.

| الوظيفة | المسار | الوصف |
|----------|-------|-------|
| **حجز موعد** | `/portal/appointments/new` | اختيار الطبيب/القسم، الوقت، دفع مسبق اختياري (`online_booking_payment`). widget: `appointments_pending`. |
| **عرض النتائج** | `/portal/results` | تقارير المختبر/الأشعة بعد الاعتماد. |
| **الفواتير والدفع** | `/portal/billing` | عرض الفواتير، دفع إلكتروني (Stripe)، سجل الدفعات. |
| **الملف الطبي** | `/portal/medical-record` | ملخص الزيارات، التشخيصات، الروشيتات، الحساسيات. |
| **استبيانات الرضا** | `/portal/surveys` | استبيانات ما بعد الزيارة، NPS. |

---

## الأسئلة الشائعة

**هل يرى المريض نتائج المختبر فوراً؟**
لا — النتيجة تمر بالاعتماد (`validation`) أولاً ثم تُحرر للبوابة.

**هل يمكن لمحاسب رؤية بيانات طبية؟**
لا — الصلاحيات تحددها الأدوار والوحدات. الفوترة ترى الخدمات والأسعار فقط، لا ملف المريض الطبي.

**كيف أضيف نموذج تخصص جديد؟**
يُنشئه `manager`/`admin` من `/specialty-forms/new` — خطوات مفصلة في [DYNAMIC_FORM_GOVERNANCE.md](DYNAMIC_FORM_GOVERNANCE.md).

**طبيب الطوارئ لا يرى لوحة الطوارئ؟**
تأكد من تفعيل وحدة `emergency` في باقة المركز (`product_bundles` → `tenant_modules`). في الإصدار 3.3+ الدخول يوجه تلقائياً لـ `/emergency/dashboard`.

---

## تنبيهات هامة

- **لا تشارك كلمة المرور** — النظام يسجل محاولات الدخول الفاشلة والجلسات (`login_attempts`، `session_logs`).
- **الروشيتات والأوامر السريرية** تحمل توقيعاً رقمياً وتاريخاً (`created_by`، `signed_at`).
- **أي تعديل في الأسعار** يتم عبر لوحة التسعير (`/accountant/pricing`) وليس عبر قاعدة البيانات مباشرة.
- **الوحدات المطفأة** = البيانات مخفية (قراءة = 0 صفوف، كتابة = `ModuleNotEnabledError`). لتفعيل: غيّر الباقة أو فعّل الوحدة من لوحة المالك/المدير.