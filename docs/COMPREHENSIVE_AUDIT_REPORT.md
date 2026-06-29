# تقرير التدقيق الشامل والنظام — Comprehensive System Audit & Maintenance Plan

**تاريخ التقرير الأصلي:** 2026-06-16  
**آخر تحديث للحالة:** 2026-06-28  
**النسخة:** Azad Medical Platform v3.1

---

## تحديث يونيو 2026 — ما تغيّر منذ التقرير الأصلي

> القسم أدناه (§1–§9) يوثّق حالة **16 يونيو**. هذا القسم يعكس **الكود الفعلي** بعد إغلاق فجوات الإنتاج.

| البند | يونيو 16 | يونيو 28 |
|-------|----------|----------|
| SaaS تسجيل ذاتي | ❌ | ✅ `/saas/signup` + API |
| دفع عند التسجيل | ❌ | ✅ Stripe checkout + `PENDING` |
| RLS | 11 جدول | **31 جدول** (`s1_002` + `s1_004`) |
| مصروفات | stub | ✅ `Expense` model + service |
| بصمة | mock | ✅ DB-backed `BiometricAuth` |
| Owner provision | مسارين | ✅ موحّد `TenantProvisioningService` |
| قيود فريدة عالمية | 3+ مكسورة | ✅ per-tenant (insurance, barcode, ward, department) |
| `guard_module` مزدوج | نعم | ✅ مركزي فقط في `app_factory` |
| Docker SaaS | معطل | ✅ postgres+redis+celery |
| CI | جزئي | ✅ ~1200+ test, `ENABLE_SAAS_MODE=true` |
| owner backdoor password | موجود | ✅ مُزال |
| trial login | مكسور | ✅ `TRIAL` + `ACTIVE` |

**تقييم محدّث:** نشر **مركز واحد** أو **SaaS مع Stripe** — جاهز تقنياً. تحسينات **UX/UI** (P2/P3 أدناه) ما زالت مفتوحة ولا تمنع التشغيل.

---

## الأصل — 2026-06-16

**مصادر التدقيق:** 8 تقارير تدقيق داخلي (UI، تنقل، صلاحيات، نماذج، جداول، CSS، RTL، بنية) + تدقيق خارجي مستقل (GitHub Static Code Audit)

---

## السياسة الصارمة — Strict Code Policy (ملزمة لكل التعديلات)

1. **لا تكرار للوظائف:** ممنوع وجود endpoint بنفس الاسم في ملفين مختلفين لنفس الغرض. البحث أولاً عن الوظيفة الموجودة، ثم توسيعها وليس مضاعفتها.
2. **لا تكرار للملفات بأسماء مختلفة:** كل مهمة لها مكان واحد. إذا وجد مكانان، يدمجان ويحذف القديم.
3. **لا تضخيم للملفات:** أي ملف يزيد عن 1000 سطر يُقسّم. أي دالة تزيد عن 50 سطر تُعاد هيكلتها. كل ملف مسؤول عن شيء واحد.
4. **لا تشتت:** كل مفهوم له تعريف واحد. الإعدادات في config.py، المسارات منظمة حسب القسم، CSS واحد للقاعدة.
5. **لا تكديس كود بلا فائدة:** أي كود لا يُستخدم يُحذف فورًا. أي ملف لا يُستورد يُحذف. أي دالة لا تُستدعى تُحذف.
6. **التصحيح أهم من الإضافات:** تصحيح الأخطاء المنطقية والبرمجية أولوية أولى. لا تضاف ميزة جديدة مع وجود أخطاء P0/P1 مفتوحة.
7. **تركيز عالي:** كل جلسة تطوير هدف واحد واضح. لا تغيير في الأولوية خلال التنفيذ. لا ميزات خارج النطاق.
8. **لا نسيان ولا فقدان:** كل مشكلة تُوثّق. بعد الإصلاح: تحديث التقرير. أي مشكلة جديدة تُكتشف: تُضاف مع تاريخها.

---

## فهرس المحتويات

1. [الخلاصة التنفيذية](#1-الخلاصة-التنفيذية)
2. [النظام الكامل: إحصائيات عامة](#2-النظام-الكامل-إحصائيات-عامة)
3. [الأخطاء الحرجة — Critical Blockers (P0)](#3-الأخطاء-الحرجة--critical-blockers-p0)
4. [الأخطاء عالية الخطورة — High Priority (P1)](#4-الأخطاء-عالية-الخطورة--high-priority-p1)
5. [الأخطاء متوسطة الخطورة — Medium Priority (P2)](#5-الأخطاء-متوسطة-الخطورة--medium-priority-p2)
6. [الأخطاء منخفضة الخطورة — Low Priority (P3)](#6-الأخطاء-منخفضة-الخطورة--low-priority-p3)
7. [التقييم النهائي: درجة الجاهزية](#7-التقييم-النهائي-درجة-الجاهزية)
8. [خطة الإصلاح المرحلية — Phased Remediation Plan](#8-خطة-الإصلاح-المرحلية--phased-remediation-plan)
9. [ملاحق — ملخص التداخلات](#9-ملاحق--ملخص-التداخلات)

---

## 1. الخلاصة التنفيذية

> **أرشيف 16 يونيو 2026:** الفقرات التالية تصف الحالة **قبل** إغلاق فجوات SaaS. كثير من بنود P0/P1 أُغلقت — راجع جدول «تحديث يونيو 2026» أعلاه و`CEO_OVERVIEW.md`.

**النظام مبني على Flask + SQLAlchemy + PostgreSQL، ويحتوي بنية ضخمة (153 نموذجًا، 168 جدولًا، 245 قالبًا، 498 مسارًا، 44 بلووبرنت).** يحتوى على تغطية وظيفية ممتازة لمجال طبي متكامل (استقبال، طبيب، مختبر، أشعة، تمريض، صيدلية، مالية، إدارة، طوارئ، حجز، تقارير، سوبر أدمن).

**ولكن (حالة 16 يونيو):** النظام **لم يكن** جاهزًا للإنتاج العام بعد. توجد 6 مشاكل حرجة (P0) كانت تمنع النشر الفوري، و12 مشكلة عالية الخطورة (P1) تحتاج إصلاحًا قبل تشغيل SaaS أو الاستخدام المالي الحقيقي.

| الفئة | العدد | أبرز المشاكل |
|-------|-------|-------------|
| **P0 — Blockers** | 6 | `/__perf/finance` مكشوف، تصعيد صلاحيات ذاتي، Docker معطل، دفع قسري مكسور، Telemedicine بدون عزل، Backup لا يعمل مع PostgreSQL |
| **P1 — High** | 12 | Multi-tenant غير محمي، خطأ عملات، 23 ملف route بدون error handling، 46 endpoint مكرر، Arabic fonts مفقودة، double footer |
| **P2 — Medium** | 24 | 45 × `btn-block`، 73 جدول بدون responsive، 17 صفحة بدون pagination، 492 `!important`، سايدبارين متنافسين |
| **P3 — Low** | 16 | قوالب ناقصة (6)، استيرادات غير مكتملة، Bootstrap 4/5 mix، voice dictation غير مختبر |

**التقييم الإجمالي: 55–60% جاهزية لنظام داخلي تجريبي، 30–40% كنظام إنتاج عام أو SaaS طبي.**

---

## 2. النظام الكامل: إحصائيات عامة

### الإحصائيات الأساسية

| البند | القيمة |
|-------|--------|
| النماذج (Models) | **153** |
| الجداول (Tables) | **168** |
| الـ Blueprints | **44** |
| المسارات (Routes) | **498** |
| القوالب (Templates) | **245** |
| ملفات Routes | **43** |
| إجمالي الوظائف في Routes | **~520** |

### ملفات CSS

| الملف | عدد الأسطر | عدد `!important` |
|-------|-----------|-----------------|
| accessibility.css | 786 | 78 |
| advanced-interface.css | 1,181 | 7 |
| app.css | 578 | 31 |
| arabic-fonts.css | 440 | 0 |
| azad-modern.css | 1,435 | 297 |
| design-system.css | 121 | 0 |
| medical-login.css | 604 | 0 |
| medical-system.css | 789 | 5 |
| modern-medical.css | 618 | 31 |
| performance.css | 401 | 3 |
| responsive.css | 789 | 31 |
| security.css | 331 | 0 |
| ui-enhancements.css | 795 | 9 |
| **المجموع** | **8,868** | **492** |

### القوالب

| القياس | القيمة |
|--------|--------|
| إجمالي القوالب | 245 |
| ملفات تحتوي `style=` (inline) | 74 |
| إجمالي `style=` inline | 282 |
| إجمالي `<table>` | 247 |
| ملفات عدد جداولها > عدد `table-responsive` | 54 |
| استخدام `btn-block` (مهمل في Bootstrap 5) | 45 |
| إجمالي `<br>` داخل الفورم | 125 |

### البنية

| القياس | القيمة |
|--------|--------|
| ملفات Routes بدون try/except | 23/43 |
| دوال مكررة (نفس الاسم في ملفين+) | 46+ |
| إجمالي blueprints | 44 |
| CSS files | 13 |
| Selectors CSS مكررة عبر ملفات | 35+ |

---

## 3. الأخطاء الحرجة — Critical Blockers (P0)

هذه الأخطاء **تمنع النشر العام أو تسبب ثغرات أمنية خطيرة** ويجب إصلاحها أولاً.

### P0.1 — مسار `/__perf/finance` مكشوف بدون صلاحيات

**الملف:** `app_factory.py:670`

**الوصف:** Route `/__perf/finance` مسجل بدون `@login_required`. يستخدم `app.test_client()`، يحاول تسجيل الدخول باسم `accountant` وبكلمات مرور hardcoded (`"123456"` أو `"p"`)، ثم يفحص صفحات مالية حساسة.

**الخطر:** ثغرة خطيرة — أي زائر يستطيع اكتشاف مسارات مالية، ورؤية أداء النظام، ومحاولة اختراق الحسابات.

**الحل:** الحذف الفوري أو الحماية بـ `@super_admin_required` + feature flag للتطوير فقط.

---

### P0.2 — تصعيد صلاحية ذاتي عبر `/auth/profile`

**الملف:** `routes/auth_routes.py:295-300`

**الوصف:** صفحة `/profile` محمية فقط بـ `@login_required`. في POST، تأخذ `role` من `request.form` وتحدّث `user.role` إذا كانت القيمة ضمن قائمة تشمل `manager`, `admin`, `super_admin`.

**الخطر:** أي مستخدم مسجل (حتى دور `user`) يمكنه إرسال POST يدويًا وتغيير دوره إلى `super_admin` — تحكم كامل بالنظام.

**الحل:** منع تعديل `role` من صفحة profile. نقل تغيير الأدوار إلى مسار إداري منفصل.

---

### P0.3 — Docker production معطل

**الملف:** `Dockerfile:34`، `requirements.txt`

**الوصف:** Dockerfile يشغّل `gunicorn -k eventlet run_server:app` ولكن:
1. `requirements.txt` لا يحتوي على `eventlet`
2. `run_server.py` يعرّف `app = create_app()` داخل `if __name__ == '__main__'` فقط — `gunicorn run_server:app` لن يجد `app`

**الخطر:** فشل بناء Docker ونشر الإنتاج.

**الحل:** إما استخدام `app:app` من `app.py`، أو تعديل `run_server.py` لتصدير `app` على مستوى الملف. تثبيت `eventlet` أو تغيير الـ worker.

---

### P0.4 — Workflow الدفع القسري غير متسق

**الملف:** `routes/payment_routes.py:179-180`، `services/gatekeeper_service.py`

**الوصف:** مسار `/payment/process/<visit_id>` محصور بدور `accountant`. لكن `GatekeeperService.validate_force_payment()` يشترط دور `manager` أو `super_admin`. النتيجة: المحاسب لا يستطيع الموافقة على الدفع القسري، والمدير لا يستطيع دخول المسار.

**الحل:** فصل العملية — المحاسب يسجل الدفع، المدير يوافق عبر route مستقل (`/payment/force/<visit_id>/approve`).

---

### P0.5 — Telemedicine بدون عزل بيانات

**الملف:** `routes/telemedicine_routes.py:16-19` (index)، `:60-62` (view)

**الوصف:** `/telemedicine/` و `/telemedicine/<tm_id>` محميان فقط بـ `@login_required` بدون فلترة دور. يعرضان كل `TelemedicineAppointment` لأي مستخدم مسجل.

**الخطر:** أي موظف (حتى دور `user`) يستطيع تصفح مواعيد استشارات المرضى الآخرين.

**الحل:** فلترة حسب الدور — الطبيب يرى مواعيده، المريض يرى مواعيده، إضافة tenant filter.

---

### P0.6 — نظام النسخ الاحتياطي لا يدعم PostgreSQL

**الملف:** `routes/backup_routes.py:210-214`، `:248-250`

**الوصف:** النظام PostgreSQL-only (`config.py` يمنع SQLite)، لكن `backup_routes.py` يبحث عن `medical_system.db` أو `instance/medical_system.db` ويضعهما في ZIP. كما أن `zipf.extractall('temp_restore')` غير آمن.

**الخطر:** زر "إنشاء نسخة احتياطية" يعطي ZIP شكلي لا يحتوي على قاعدة البيانات الحقيقية. الاستعادة تستخدم `extractall` غير آمن.

**الحل:** استبدال بـ `pg_dump`/`pg_restore` مع تشفير، تخزين خارج مجلد التطبيق، استخدام `ZipFile.extractall()` بحذر.

---

## 4. الأخطاء عالية الخطورة — High Priority (P1)

### P1.1 — Multi-tenant غير محمي ORM-wise

**الملف:** جميع ملفات Routes

**الوصف:** النظام يحتوي `tenant_id` في `Patient`, `Visit`, `Payment`, `Invoice` لكن معظم الاستعلامات تستخدم `Model.query` مباشرة بدون فلترة tenant. كما أن `UniqueConstraint('national_id')` عالمي وليس لكل tenant.

**الحل:** إضافة طبقة ORM scoping مركزية، تعديل unique constraints إلى `UniqueConstraint('tenant_id', 'national_id')`.

---

### P1.2 — خطأ مالي في تحويل العملات

**الملف:** `routes/payment_routes.py:118-277`

**الوصف:** عند الدفع بعملة غير ILS، يتم حساب `converted_amount` لكن في السطر 277: `visit.paid_amount = Decimal(str(visit.paid_amount or 0)) + amount_value` (يستخدم `amount_value` الأصلي وليس `converted_amount`).

**الخطر:** تسجيل مبلغ خاطئ في حالة الدفع بعملة مختلفة.

**الحل:** إضافة `original_amount`, `original_currency`, `exchange_rate`, `base_amount` إلى Payment model.

---

### P1.3 — 23 ملف Route بدون error handling

| الملفات |
|---------|
| `ai_imaging_routes.py`، `backup_restore_routes.py`، `barcode_routes.py`، `bed_management_routes.py`، `biometric_routes.py` |
| `cds_alert_routes.py`، `clinical_coding.py`، `clinical_pathway_routes.py`، `data_warehouse_routes.py`، `dicom_routes.py` |
| `emar_routes.py`، `fhir_api_routes.py`، `mfa_routes.py`، `nursing_assessment_routes.py`، `or_management_routes.py` |
| `patient_education_routes.py`، `population_health_routes.py`، `referral_routes.py`، `security_advanced_routes.py` |
| `sso_routes.py`، `telemedicine_routes.py`، `vaccination_routes.py`، `what_if_routes.py` |

**الوصف:** 23 من 43 ملف Route (53%) لا تحتوي أي `try/except`. أي خطأ غير متوقع يؤدي إلى 500 Internal Server Error بدون رسالة واضحة.

**الحل:** إضافة `try/except` لكل دالة route مع رسائل خطأ مناسبة وتسجيل في log.

---

### P1.4 — Arabic Fonts غير محمّلة في base.html

**الملف:** `templates/base.html`، `static/css/arabic-fonts.css`

**الوصف:** ملف `arabic-fonts.css` (440 سطرًا) موجود في `static/css/` لكنه **غير مضمن** في `base.html`. خطوط Tajawal يتم تحميلها عبر fallback المتصفح فقط.

**الحل:** إضافة `<link rel="stylesheet" href="{{ url_for('static', filename='css/arabic-fonts.css') }}">` في `base.html`.

---

### P1.5 — سايدبارين متنافسين مع تناقضات

**الملف:** `templates/partials/sidebar.html`، `templates/partials/_sidebar.html`

**الوصف:** يوجد سايدباران:
- `sidebar.html`: 13 عنصرًا، يستخدم hardcoded `href` (ليس `url_for`)، لكنه يدعم module gating
- `_sidebar.html`: ~56 عنصرًا، يستخدم `url_for()` بشكل صحيح، لكن بدون module gating

**الخطر:** تناقض في التنقل، بعض الصفحات تظهر في أحدهما دون الآخر، المسارات قد تكون خاطئة.

**الحل:** دمج السايدبارين في ملف واحد. توحيد استخدام `url_for()` مع module gating.

---

### P1.6 — Double Footer

**الملف:** `templates/base.html` (line 257 + 729-744)

**الوصف:** `base.html` يحتوي `{% include 'partials/_footer.html' %}` في السطر 257، ثم يحتوي **Standalone footer** كامل في الأسطر 729-744. هذا يعرض footer مرتين.

**الحل:** إزالة الـ standalone footer والاكتفاء بـ include.

---

### P1.7 — اختبارات غير كافية و.gitignore يمنع تتبعها

**الملف:** `.gitignore:85-86`، `tests/`

**الوصف:** 
- `.gitignore` يتجاهل مجلد `tests/` بالكامل (`tests/`)
- الاختبارات قد تحتوي قيم hardcoded (DB URL, SECRET KEY)
- `17/17 passing` تشمل اختبارات سطحية

**الخطر:** أي اختبارات جديدة لن يتم تتبعها في Git. لا يمكن الاعتماد على نتيجة الاختبارات الحالية.

**الحل:** إزالة `tests/` من `.gitignore`، إعادة كتابة الاختبارات لتكون integration tests حقيقية.

---

### P1.8 — CI لا يختبر Docker ولا Security

**الملف:** `.github/workflows/`

**الوصف:** CI يشغّل pytest فقط. لا يوجد:
- `docker build` job
- `flask db upgrade`
- Route smoke tests
- Security scanning (bandit, pip-audit)

**الخطر:** مشاكل Docker (`eventlet`, `run_server:app`) لن تظهر حتى النشر.

**الحل:** إضافة jobs للـ Docker build و route tests و security scan.

---

## 5. الأخطاء متوسطة الخطورة — Medium Priority (P2)

### P2.1 — Forms: `btn-block` (Bootstrap 4 deprecated)

**الملف:** ~45 استخدام في القوالب المختلفة

**الوصف:** Bootstrap 5 أزال `btn-block`؛ يجب استبداله بـ `w-100` class.

**الخطر:** الأزرار قد لا تظهر بالعرض الكامل في Bootstrap 5.

---

### P2.2 — 73 جدول بدون `table-responsive`

**الوصف:** من 247 جدول، 54 ملف (73+ جدول) تفتقر إلى `table-responsive` wrapper. الجداول قد تنكسر في الشاشات الضيقة.

---

### P2.3 — 17 صفحة قوائم بدون Pagination

**الوصف:** صفحات listing تفتقر إلى `pagination` رغم وجود 10+ سجل. المستخدم لا يستطيع التنقل عبر السجلات.

---

### P2.4 — 492 استخدام `!important` في CSS

| الملف | `!important` |
|-------|-------------|
| azad-modern.css | 297 |
| accessibility.css | 78 |
| app.css | 31 |
| modern-medical.css | 31 |
| responsive.css | 31 |
| ui-enhancements.css | 9 |
| advanced-interface.css | 7 |
| medical-system.css | 5 |
| performance.css | 3 |

**الوصف:** 492 `!important` يشير إلى معركة CSS cascade — الملفات تتجاوز بعضها البعض بالقوة. هذا يجعل الصيانة مستحيلة وكل تعديل جديد يتطلب `!important` إضافي.

---

### P2.5 — 44 Blueprint بدون روابط تنقل موحدة

**الوصف:** النظام يحتوي 44 بلووبرنت، معظمها لا يظهر في أي قائمة تنقل موحدة. يصل المستخدم إليها عبر التوجيه المباشر فقط.

**الحل:** إنشاء نظام nav مركزي يربط كل بلووبرنت بالصفحات المناسبة حسب الدور.

---

### P2.6 — 35+ Selector CSS مكرر عبر 13 ملف

**الوصف:** نفس الـ selectors (`.form-label`, `.btn`, `.card`, `.alert`, `.table`) معرّفة في **3-5 ملفات CSS** مختلفة بقواعد مختلفة. أي تغيير في CSS يحتاج تعديل 5 ملفات.

---

### P2.7 — 282 inline style في 74 قالب

**الوصف:** كتابة CSS مباشرة في HTML باستخدام `style="..."` في 74 ملف قالب. هذا يمنع إعادة الاستخدام ويجعل التعديل صعبًا.

---

### P2.8 — 46+ Endpoint مكرر (نفس اسم الدالة في ملفين+)

**مثال:**
| الدالة | الملفات |
|--------|---------|
| `dashboard` | 21 ملف |
| `index` | 18 ملف |
| `reports` | 7 ملفات |
| `patients` | 4 ملفات |
| `appointments` | 3 ملفات |
| `payments` | 3 ملفات |
| `worklist` | 2 ملف (lab + radiology) |
| `pricing` | 2 ملف (manager + super_admin) |

**الوصف:** نفس اسم الدالة يستخدم لأغراض مختلفة. يدل على حاجة لإعادة هيكلة أو ميراث.

---

### P2.9 — 46 استخدام `mr-`/`ml-` (Bootstrap 4 RTL)

**الوصف:** استخدام `mr-*` و `ml-*` (Bootstrap 4) بدلاً من `ms-*` و `me-*` (Bootstrap 5). هذا قد يكسر التنسيق في Bootstrap 5.

---

### P2.10 — Bootstrap 4 RTL + Bootstrap 5 RTL مختلطان

**الوصف:** النظام يستخدم Bootstrap 5 framework مع بعض bootstrap.rtl.css قديم. توجد 100+ `border-left-*` و 86 سهم اتجاه خاطئ لـ RTL.

---

### P2.11 — Macro `forms.html` ميت (0 استدعاءات)

**الملف:** `templates/macros/forms.html`

**الوصف:** 4 قوالب تستورد `forms.html` لكن لا يوجد أي استدعاء فعلي للـ macros داخله. الكود ميت لكنه يبقى يُحمّل.

---

### P2.12 — صلاحيات: 3 أنظمة غير متوافقة

**الوصف:** النظام يحتوي 3 أنظمة صلاحيات:
1. `@role_required('doctor')` — String-based role check
2. `@permission_required('perm')` — غير مستخدم (0 استدعاءات)
3. `current_user.role` — Hardcoded string comparison

**الخطر:** 28 role string مختلف، لا hierarchy، `technician` مستخدم لكن غير معرّف.

---

## 6. الأخطاء منخفضة الخطورة — Low Priority (P3)

| # | المشكلة | الملف | التفاصيل |
|---|---------|-------|----------|
| P3.1 | 6 قوالب ناقصة | `clinical_coding/*`، `cds/*`، `population_health/*` | Routes تشير لقوالب غير موجودة (500 error) |
| P3.2 | 3 استيرادات غير مكتملة | `models/__init__.py` | `PaymentStatus`, `PermissionCategory`, `PermissionLevel` |
| P3.3 | Bootstrap 4/5 mix في الأزرار | متعدد | بعض الأزرار تستخدم B4 classes |
| P3.4 | 125 `<br>` داخل الفورم | متعدد | استخدام `<br>` بدلاً من `margin`/`gap` |
| P3.5 | No breadcrumbs system | — | لا يوجد مسار تنقل (breadcrumb) |
| P3.6 | 17 صفحة بدون empty state | متعدد | جداول/قوائم تظهر فارغة بدون رسالة إرشادية |
| P3.7 | Form validation feedback مفقود | متعدد | لا `is-invalid`/`invalid-feedback` |
| P3.8 | 21 ملف بعرض pixel ثابت | متعدد | `width: 300px` بدلاً من responsive units |
| P3.9 | 5 ملفات بدون `csrf_token` في الفورم | متعدد | خطر CSRF |
| P3.10 | No service layer | — | `reception.py` = 4,307 سطر، `super_admin.py` = 3,332 سطر |
| P3.11 | doctor/emergency 40% overlap | `doctor.py`, `emergency.py` | 14 endpoint مشترك |
| P3.12 | lab/radiology 7 identical endpoints | `lab.py`, `radiology.py` | `worklist`, `results`, `requests`, `quality`, etc. |
| P3.13 | Voice dictation غير مختبر | — | JS موجود لكن لم يُختبر في browser |
| P3.14 | Biometric auth يحتاج `fido2` | — | WebAuthn API موجود لكن `fido2` غير مثبتة |
| P3.15 | Document OCR يعتمد على CDN | `advanced/document_ocr.html` | Tesseract.js من CDN |
| P3.16 | Foreign Key cascade ناقص | `NursingAssessment` | `visit_id` FK بدون `ondelete='CASCADE'` (مُصلح) |

---

## 7. التقييم النهائي: درجة الجاهزية

| البُعد | التقييم السابق (Triple-Lens) | التقييم الحالي (بعد التدقيق الشامل) | الفرق |
|--------|------------------------------|--------------------------------------|-------|
| Core EMR | 9.8/10 | 7.5/10 | ❌ مبالغ فيه |
| Clinical Workflow | 9.9/10 | 7.0/10 | ❌ مبالغ فيه |
| Pharmacy | 9.8/10 | 7.0/10 | ❌ مبالغ فيه |
| Billing | 9.5/10 | 5.5/10 | ❌ خطأ العملات + دفع قسري |
| Lab / Radiology | 9.7/10 | 7.5/10 | ❌ مكررات بدون تجريد |
| Patient Engagement | 9.9/10 | 6.0/10 | ❌ Telemedicine مكشوف + Arabic fonts |
| Interoperability | 9.0/10 | 7.0/10 | ❌ FHIR موجود لكن غير مختبر |
| Security | 9.5/10 | 4.0/10 | 🔴 3 ثغرات حرجة (P0.1, P0.2, P0.5) |
| UI/UX | 9.0/10 | 4.5/10 | 🔴 492 !important + 282 inline + double footer |
| **المتوسط** | **9.6/10** | **6.2/10** | **🔴 ليس جاهزًا للإنتاج** |

---

## 8. خطة الإصلاح المرحلية — Phased Remediation Plan

### المرحلة 0: الإصلاحات الفورية (أسبوع 1) — P0

هذه الإصلاحات **تمنع الخرق الأمني والفشل الفوري** ويجب تنفيذها قبل أي شيء آخر.

| # | المهمة | الملفات المتأثرة | الجهد المتوقع |
|---|--------|-----------------|---------------|
| **0.1** | حذف أو حماية `/__perf/finance` | `app_factory.py:670` | 15 دقيقة |
| **0.2** | منع تعديل `role` من `/auth/profile` | `routes/auth_routes.py:295-300` | 30 دقيقة |
| **0.3** | إصلاح Docker: `run_server.py` أو تغيير إلى `app:app` | `Dockerfile`, `run_server.py`, `requirements.txt` | 1 ساعة |
| **0.4** | إصلاح workflow الدفع القسري (فصل المسار) | `routes/payment_routes.py`, `services/gatekeeper_service.py` | 2 ساعة |
| **0.5** | إضافة فلترة أدوار لـ Telemedicine | `routes/telemedicine_routes.py:16-62` | 1 ساعة |
| **0.6** | استبدال backup SQLite بـ `pg_dump` | `routes/backup_routes.py` | 3 ساعات |

**إجمالي الجهد المقدر للمرحلة 0: 8 ساعات**

---

### المرحلة 1: إصلاحات الأمان والمالية (أسبوع 2-3) — P1 الأمنية والمالية

| # | المهمة | الملفات المتأثرة | الجهد المتوقع |
|---|--------|-----------------|---------------|
| **1.1** | تطبيق tenant ORM scoping + تعديل unique constraints | جميع routes + models | 3 أيام |
| **1.2** | إصلاح خطأ العملات (إضافة `base_amount` في Payment) | `routes/payment_routes.py`, `models/payment.py` | 4 ساعات |
| **1.3** | إضافة try/except لـ 23 ملف route | 23 ملف في `routes/` | 2 يوم |
| **1.4** | تحميل arabic-fonts.css في base.html | `templates/base.html` | 15 دقيقة |
| **1.5** | دمج السايدبارين وإصلاح الروابط | `templates/partials/sidebar.html`, `_sidebar.html` | 1 يوم |
| **1.6** | إصلاح double footer | `templates/base.html` | 15 دقيقة |
| **1.7** | إصلاح .gitignore وإعادة كتابة الاختبارات | `.gitignore`, `tests/` | 2 يوم |
| **1.8** | إضافة Docker build + security scan إلى CI | `.github/workflows/` | 1 يوم |

**إجمالي الجهد المقدر للمرحلة 1: 10 أيام**

---

### المرحلة 2: تحسين جودة الواجهات والـ CSS (أسبوع 4-6) — P2

| # | المهمة | الملفات المتأثرة | الجهد المتوقع |
|---|--------|-----------------|---------------|
| **2.1** | استبدال `btn-block` بـ `w-100` (45 استخدام) | ~25 قالب | 4 ساعات |
| **2.2** | إضافة `table-responsive` لـ 54 ملف | ~54 قالب | 6 ساعات |
| **2.3** | إضافة pagination لـ 17 صفحة قوائم | ~17 قالب + routes | 2 يوم |
| **2.4** | توحيد CSS: دمج 13 ملف → 3-4 ملفات (base, modules, rtl) | `static/css/*.css` | 3 أيام |
| **2.5** | إزالة inline styles ونقلها إلى CSS classes | 74 قالب | 3 أيام |
| **2.6** | توحيد selectors المكررة (35+) | جميع CSS files | 2 يوم |
| **2.7** | استبدال `mr-`/`ml-` بـ `ms-`/`me-` (Bootstrap 5 RTL) | جميع القوالب | 1 يوم |
| **2.8** | إزالة dead code: `templates/macros/forms.html` | `templates/macros/forms.html` | 30 دقيقة |
| **2.9** | توحيد نظام الصلاحيات (إزالة نظامين، تفعيل الثالث) | `utils/decorators.py`, `services/access_control_service.py` | 3 أيام |

**إجمالي الجهد المقدر للمرحلة 2: 16 يوم**

---

### المرحلة 3: إعادة هيكلة البنية (أسبوع 7-10) — P2+P3

| # | المهمة | الملفات المتأثرة | الجهد المتوقع |
|---|--------|-----------------|---------------|
| **3.1** | تقسيم `reception.py` (4,307 سطر) إلى وحدات أصغر | `routes/reception.py` | 3 أيام |
| **3.2** | تقسيم `super_admin.py` (3,332 سطر) | `routes/super_admin.py` | 2 يوم |
| **3.3** | تقسيم `doctor.py` (2,736 سطر) | `routes/doctor.py` | 2 يوم |
| **3.4** | تجريد endpoints المشتركة doctor/emergency (14 duplicate) | `doctor.py`, `emergency.py` | 2 يوم |
| **3.5** | تجريد endpoints المشتركة lab/radiology (7 duplicate) | `lab.py`, `radiology.py` | 1 يوم |
| **3.6** | إنشاء خدمة Breadcrumbs + نظام nav مركزي | كل القوالب | 2 يوم |
| **3.7** | إضافة empty state لـ 17 صفحة قائمة | ~17 قالب | 1 يوم |
| **3.8** | إضافة form validation feedback | ~30 قالب | 2 يوم |
| **3.9** | إصلاح 5 قوالب بدون CSRF | ~5 قوالب | 1 ساعة |
| **3.10** | إزالة hardcoded widths (21 ملف) | ~21 قالب | 1 يوم |

**إجمالي الجهد المقدر للمرحلة 3: 16 يوم**

---

### المرحلة 4: التحسينات النهائية (أسبوع 11-12) — P3 المتبقي

| # | المهمة | الملفات المتأثرة | الجهد المتوقع |
|---|--------|-----------------|---------------|
| **4.1** | إنشاء 6 قوالب ناقصة | `clinical_coding/*`, `cds/*`, `population_health/*` | 1 يوم |
| **4.2** | إكمال استيرادات models/__init__.py | `models/__init__.py` | 30 دقيقة |
| **4.3** | اختبار Voice Dictation + Biometric + OCR | متعدد | 2 يوم |
| **4.4** | إزالة Bootstrap 4/5 mix نهائيًا | جميع القوالب | 1 يوم |
| **4.5** | استبدال `<br>` في الفورم بـ CSS margin/gap | جميع القوالب | 1 يوم |
| **4.6** | إنشاء service layer للمنطق المتكرر | متعدد | 3 أيام |

**إجمالي الجهد المقدر للمرحلة 4: 8 أيام**

---

### الجدول الزمني الإجمالي

| المرحلة | المدة | الأسبوع | الحالة |
|---------|-------|---------|--------|
| **المرحلة 0 — فوري** | 8 ساعات | الأسبوع 1 | 🔴 لم يبدأ |
| **المرحلة 1 — أمان + مالية** | 10 أيام | الأسبوع 2-3 | 🔴 لم يبدأ |
| **المرحلة 2 — واجهات + CSS** | 16 يوم | الأسبوع 4-6 | 🔴 لم يبدأ |
| **المرحلة 3 — بنية + هيكلة** | 16 يوم | الأسبوع 7-10 | 🔴 لم يبدأ |
| **المرحلة 4 — تحسينات نهائية** | 8 أيام | الأسبوع 11-12 | 🔴 لم يبدأ |
| **الإجمالي** | **~50 يوم عمل** | **12 أسبوع** | **🔴 قيد الانتظار** |

---

## 9. ملاحق — ملخص التداخلات

### الملحق أ: مقارنة التقييمات

| التقييم | التاريخ | درجة الجاهزية | الجهة |
|---------|---------|---------------|-------|
| Triple-Lens Audit Report | 2026-06-12 | 9.6/10 ✅ جاهز للإنتاج | داخلي (المطور) |
| GitHub Static Code Audit | 2026-06-16 | 30-40% ❌ غير جاهز | خارجي (مستقل) |
| Internal 8-Agent Audit | 2026-06-16 | 55-60% ⚠️ تجريبي فقط | داخلي (تحت الإشراف) |
| **هذا التقرير (الموحد)** | **2026-06-16** | **6.2/10 — 30-40%** | **موقع بالبيانات** |

**لماذا الفرق؟** التقييم السابق (Triple-Lens) اعتمد على اختبارات تشغيل سطحية (17 اختبارًا). التقييمات الجديدة درست الكود مصدريًا — وجدت 71 مشكلة هيكلية و10 ثغرات أمنية/تشغيلية. التقييم 9.6/10 **غير دقيق** ويعطي انطباعًا خاطئًا عن جاهزية النظام.

### الملحق ب: مصادر التدقيق

| المصدر | عدد المشاكل التي وجدها | التغطية |
|--------|----------------------|---------|
| Agent 1 — UI/Visual Audit | 94 مشكلة | 74 ملف قالب |
| Agent 2 — Navigation Audit | 28 orphan blueprints + 2 sidebars | كل blueprints + 2 قالب |
| Agent 3 — Permissions Audit | 6 مشاكل حرجة | كل decorators + أدوار |
| Agent 4 — Forms Audit | 7 مشاكل حرجة | كل forms في القوالب |
| Agent 5 — Tables Audit | 10 مشاكل حرجة | 247 جدول |
| Agent 6 — CSS Audit | 16 مشكلة | 13 CSS files, 8,868 سطر |
| Agent 7 — RTL/Arabic Audit | 16 مشكلة | كل القوالب + CSS |
| Agent 8 — Architecture Audit | 12 مشكلة | كل ملفات routes + services |
| GitHub External Audit | 10 مشاكل حرجة | كل النظام |

---

### الملحق ج: الملفات الأكثر تأثرًا

| الملف | عدد الأسطر | المشاكل |
|-------|-----------|---------|
| `routes/reception.py` | 4,307 | P3.10 — ضخم جدًا، يحتوي 50+ endpoint |
| `routes/super_admin.py` | 3,332 | P3.10 — ضخم جدًا |
| `routes/doctor.py` | 2,736 | P3.10 + P3.11 — ضخم + 40% duplicate مع emergency |
| `templates/base.html` | ~800 | P1.6 — Double footer, P1.4 — Arabic fonts |
| `app_factory.py` | ~700 | P0.1 — `/__perf/finance`, 44 blueprint registration |
| `routes/emergency.py` | ~1,200 | P3.11 — 40% duplicate مع doctor |
| `routes/payment_routes.py` | ~500 | P0.4 — Force payment, P1.2 — Currency bug |
| `routes/auth_routes.py` | ~450 | P0.2 — Role escalation |
| `routes/backup_routes.py` | ~300 | P0.6 — SQLite backup in PostgreSQL system |
| `routes/telemedicine_routes.py` | ~200 | P0.5 — No authorization isolation |
| `static/css/azad-modern.css` | 1,435 | P2.4 — 297 `!important`, P2.6 — duplicate selectors |
| `static/css/advanced-interface.css` | 1,181 | P2.6 — duplicate selectors |

---

## خاتمة

**النظام ليس مجرد "كود مكدس" — لكنه ليس جاهزًا للإنتاج.** 

يحتوي بنية ضخمة وقابلة للتطوير، لكنه يعاني من:
1. **6 ثغرات أمنية/تشغيلية حرجة (P0)** تمنع النشر العام
2. **12 مشكلة عالية الخطورة (P1)** تمنع الـ SaaS والاستخدام المالي
3. **فوضى CSS وواجهات (P2)** تجعل الصيانة مكلفة والتطوير بطيئًا
4. **غياب اختبارات حقيقية** يجعل أي تغيير محفوفًا بالمخاطر

**خطة إصلاح مدتها 12 أسبوع (50 يوم عمل)** كافية لنقل النظام من 30-40% جاهزية → 85-90%، إذا التزم الفريق بالمراحل المذكورة أعلاه.

**الخطوة التالية:** بدء المرحلة 0 فورًا (إصلاح الثغرات الأمنية الثلاث: P0.1, P0.2, P0.5 قبل أي شيء آخر).
