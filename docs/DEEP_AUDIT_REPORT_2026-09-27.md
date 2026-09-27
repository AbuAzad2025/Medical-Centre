# تقرير التدقيق الفني العميق — منصة المركز الطبي v3.1

**التاريخ:** 27 سبتمبر 2026
**النطاق:** كل وظائف النظام الفعلية + كل نقطة نهاية (endpoints) على قاعدة بيانات PostgreSQL حيّة
**الطريقة:** تشغيل حقيقي، ليس قراءة ساكنة — تم إنشاء قاعدة بيانات مخصّصة، تطبيق 65 هجرة، زرع البيانات، تسجيل دخول فعلي، ثم تنفيذ **5,720 طلب** عبر كل نقطة نهاية × 11 دور.

---

## 0. الخلاصة التنفيذية

النظام **يعمل فعلياً**، وليس هيكلاً فارغاً: 752 نقطة نهاية، 226 جدول، 430 قالب، 65 هجرة. بعد الإصلاحات:

| المقياس | القيمة |
|---|---|
| نقاط النهاية المسجّلة فعلياً | **752** (GET 521 · POST 324 · PUT 2 · DELETE 2) |
| Blueprints | **61** |
| جداول RLS مُفعَّلة وFORCE | **207** |
| سياسات `tenant_isolation_*` محمية بـ `NULLIF` | **206 / 206 (100%)** |
| انحراف المخطط (ORM ↔ قاعدة بيانات) | **0** |
| قوالب Jinja تُترجم بنجاح | **430 / 430**، وأسماء غير معرّفة: **0** |
| **طلبات 500 في المسح الشامل** | **0 من 5,720** |
| نسبة 200 بعد اتباع التحويلات | **5,424 / 5,720 = 94.8%** |
| المسار السريري من طرف إلى طرف | **11 / 12** خطوة ناجحة |
| التثبيت الأول على قاعدة بيانات virgin | **كل الخطوات ناجحة** |

**لكن** اكتشفت **12 عيباً حقيقياً** — 11 منها كانت تُعطِّل النظام فعلياً، و12 حالة اختبار فاشلة. الأهم: **النظام لم يكن قابلاً للتثبيت أو الاستخدام على قاعدة بيانات مفروضة RLS بشكل صحيح** قبل إصلاحي.

---

## 1. البنية التحتية (مُنشأة بعزل تام)

اكتشفت خطورة بيئية قبل لمس أي شيء:

1. **متغير بيئة على مستوى الجهاز** `DATABASE_URL=…/azad_school` يشير إلى **قاعدة بيانات نظام آخر**. بما أن `python-dotenv` لا يتجاوز متغيرات البيئة الحقيقية، كان التطبيق الطبي سيكتب بيانات المرضى في قاعدة نظام آخر. تم توثيقه في `.env` وتصحيح مسار المشروع.
2. **PostgreSQL 18 على ويندوز معطّل فعلياً**: كل عملية ابن (child process) تنهار بـ `0xC0000142` (فشل تهيئة DLL) و `error code 487` (فشل حجز ذاكرة مشتركة)، مع `restart_after_crash=off`، فيسقط الـ cluster بالكامل. **لم أستخدمه ولم ألمسه.**

### ما أنشأته (معزول تماماً)

| البند | القيمة |
|---|---|
| المحرك | PostgreSQL 14.24 داخل WSL2، دليل بيانات خاص، منفذ **55433** |
| قاعدة البيانات | `medical_platform` + `medical_platform_test` |
| الدور | `med_app` — `NOSUPERUSER` · `NOBYPASSRLS` (أي أن RLS **مفروض فعلياً**) |
| `RLS_BYPASS_ALLOWED` | `0` — الحارس الفاشل مُفعَّل |

هذا الاختيار هو جوهر التدقيق: عند استخدام **دور غير مميَّز**، تكشف الأخطاء التي كانت مخفية لأن التطوير كان يتصل كـ superuser.

---

## 2. العيوب المكتشفة والمُصلَحة

### C1 — [حرج · مُصلَح] انحدار RLS يجعل تسجيل الدخول مستحيلاً
`s1_012_rls_nullif` كان يغلّف سياسات RLS بـ `NULLIF(...)` بشكل صحيح. لكن `s2_008` — الذي يأتي **لاحقاً** في السلسلة — أعاد كتابة تلك السياسات نفسها بالصيغة الخام، **مبطلاً الإصلاح على 191 من 200 جدول**.خام، **مبطلاً الإصلاح على 191 من 200 جدول**.

الكود في `app/shared/tenant_filter.py:520` ينفّذ عمداً:
```python
SET LOCAL app.tenant_id = ''      # لمسح السياق
```
التعليق المرفق يقول: *«النص الفارغ يعني لا يوجد مستأجر ولن يطابق أي tenant_id»* — وهذا **خطأ منطقي**: في PostgreSQL التحويل `''::integer` لا يُعطي قيمة غير مطابقة، بل **يرمي استثناء** `invalid input syntax for type integer: ""`.

**النتيجة:** بعد أي طلب لا يحل مستأجراً،becomeiry الطلب التالي على نفس اتصال مجمّع يفشل → HTTP 500. عملياً: `GET /auth/login` ثم `POST /auth/login` → **500**. أي أن **المصادقة مستحيلة**.

**الدليل الحاسم (تجربة ضابطة):** جداول الـ 3General Ledger التي أعادها `s3_003` بالصيغة المحمية تنجو من `GUC=''`، بينما الباقي ينهار.

**الإصلاح:**
- `migrations/versions/s3_012_rls_nullif_reassert.py` (جديد) — يعيد تطبيق الحارس على كل سياسات `tenant_isolation_*` التي تفتقده.
- `migrations/migration_utils.py` — **مصدر الانحدار**: `enable_tenant_rls()` كان ينتج الصيغة غير الآمنة وبلا `WITH CHECK`. أي هجرة مستقبلية تستخدم هذا المساعد كانت ستعيد إدخال الخلل من جديد.مُصلَح.

**النتيجة:** 206/206 سياسة محمية. `GUC=''` → 0 صفوف (fail-closed، لا انهيار). `GUC='1'` → صف واحد.

---

### C2 — [حرج P0 · مُصلَح] وضع «مركز طبي واحد» لا يستطيع تسجيل الدخول إطلاقاً
`USER_GUIDE.md` يوثّق وضع `ENABLE_SAAS_MODE=false`. في هذا الوضع:
- `/auth/*` مُعفى من حل الـ tenant ⇒ لا يُربط أي tenant.
- `bind_tenant_from_session()` لا يجد شيئاً، و`resolve_tenant()` يتطلب slug من المسار.
- ⇒ `g.tenant_id = None` ⇒ السياسة تُرجع **0 مستخدمين** ⇒ **401 على كل تسجيل دخول**.

كان هذا مخفياً لأن إعداد التطوير القديم يتصل كـ superuser فلا يُفلتر شيء.

**الإصلاح:** `_single_install_default_tenant()` في `app/core/tenant/middleware.py` — يربط tenant ضمنياً **في وضع non-SaaS فقط** (سلوك SaaS متعدد المستأجرين لم يتغيّر: يبقى 403). الاستعلام يتم على `tenants` فقط عمداً (لا RLS عليه)، لأن الاستعلام على `users` يبني تبعية دائرية: RLS تخفي المستخدمين حتى يُربط tenant.

**النتيجة:** تسجيل دخول 302 → لوحة الطبيب، مع `tenant_id` و`tenant_slug` في الجلسة.

---

### C3 — [حرج · مُصلَح] تناقض بين طبقتَي العزل: ORM مقابل RLS
`_GLOBAL_TENANT_TABLES` كان يصرّح بأن 10 جداول «عالمية» — أي **لا يُفلتر** ولا يُسند `tenant_id` تلقائياً. لكن قاعدة البيانات تفرض `tenant_id = المستأجر الحالي` على 9 منها.

**التعارض مستحيل التوفيق:** أي كتابة عبر ORM تنتج `tenant_id = NULL` → ترفضها `WITH CHECK`.

**الأثر الحقيقي:** `/nurse/dashboard` كان يحاول زرع بروتوكولات تمريضية افتراضية في `system_configs` → `InsufficientPrivilege` → 302. **لوحة القيادة التمريضية معطّلة كلياً.**

⚠️ **قرار تصميمي متعمّد:** أزلت `system_configs` و`branding_settings` فقط من القائمة (لأن نحو 15 موضع قراءة تعتمد على السياسة لتحديد المدى). **أبقيت** جداول صلاحيات RBAC الستة، لأن إزالتها تُفرغ صلاحيات كل مستأجر فيحوّل `has_permission()` و`can()` إلى `False` دائم (وأدى ذلك إلى نقص في اختبارين). هذه التوثيقات موثّقة في الملف، والنسختان المتطابقتان في `scripts/ci/audit_rls_coverage.py` و`routes/monitoring_routes.py` محدّثتان.

---

### C4 — [حرج · مُصلَح] التثبيت الأول مستحيل على قاعدة بيانات صحيحة
`create_default_permissions()` / `create_default_roles()` / `assign_super_admin_permissions()` تكتب `tenant_id = NULL` ⇒ يرفضها RLS ⇒ **فشل التهيئة الأول بالكامل**.

كان يعمل فقط لأن التطوير كان يتصل كـ superuser.

**ثلاثة أخطاء جذرية:**
1. الكتابة بـ NULL (تعارض RLS).
2. **خطأ ترتيب**: كانت البذور تُنفَّذ **قبل** إنشاء الـ platform tenant، فلا تجد مكاناً تأخذ منه `tenant_id`.
3. الـ seeder لا يربط سياق tenant، فيرفض RLS صفوفه الخاصة.

**الإصلاح:** `_seed_tenant_id()` في `models/permissions.py` (يعيد استخدام محلّل الـ seeder، فينشئ tenant عند الحاجة) + `_bind_seed_tenant()` في `seeds/production_baseline.py` (يربط `g.tenant_id` + `session.info` + GUC) + تحمّل `IntegrityError` والتنافر.

**النتيجة على قاعدة virgin:** 48 صلاحية + 15 دور + 100 ربط، جميعها `tenant_id` غير NULL، **بدون أي تجاوز لـ RLS**.

---

### C5 — [حرج · مُصلَح] 7 جداول و5 أعمدة معلَنة في ORM بلا هجرة
اكتشفته بـ drift audit على مستوى الأعمدة (224 جدول × كل عمود). **لم تكن هذه الأخطاء موجودة على أي قاعدة بيانات مبنية بـ `flask db upgrade`** — أي لا إنتاج ولا نسخ احتياطية:

| العنصر | الكود المتعطل |
|---|---|
| `payment_cards` | `/owner/cards-vault` → 500 |
| `insurance_claims.claim_date`, `patient_share_amount`, `insurance_share_amount`, `adjudication_notes` | `/api/claims` → 500 |
| `insurance_payouts`, `eobs` | `services/insurance_claim_service.py` → 500 |
| `patient_consents`, `consent_templates`, `consent_audit_logs` | **منظومة موافقة المريض كاملة** — و`PatientConsent` ضمن `TRACKED_MODELS` للتدقيق |
| `pharmacy_returns.disposition` | pharmacy returns |

**الإصلاح:** `migrations/versions/s3_013_missing_schema_objects.py` — ينشئها مع RLS + `NOT NULL` + فهارس + أعمدة `EncryptedString` كـ `TEXT`، و**idempotent**.

**النتيجة:** انحراف المخطط = **0**.

> **لماذا فات كل هذا التدقيق؟** `scripts/ops/pre_pilot_verification.py` يفحص `Model.__table__.columns` (بيانات ORM الوصفية) **لا** المخطط المهاجَر. لذلك alfaser ياف «86 تأكيداً، 0 إخفاق» على قاعدة بيانات تنقصها كل هذه العناصر. **هذه بوابة تحقق تُعطي ضماناً كاذباً** ويجب أن تُصحَّح لتفحص `information_schema`.

---

### C6 — [عالٍ · مُصلَح] 17 قالباً كان سيموت بـ 500 في الإنتاج
`{{ csrf() }}` مستعمل في **17 قالباً / 24 موضعاً**، بينما Flask-WTF يسجّل الاسم `csrf_token` فقط. `csrf` **غير مسجّل** في أي مكان في التطبيق ⇒ `jinja2.exceptions.UndefinedError: 'csrf' is undefined`.

**الأخطر:** `tests/test_routes_owner.py:21` كان يفعل `app.jinja_env.globals['csrf'] = lambda: ...` — أي أن **الاختبارات نفسها كانت تخفي العيب**.

**الإصلاح:** تسجيل `csrf` كاسم بديل في `app_factory.py`.
**النتيجة:** فحص AST على 430 قالباً ⇒ **0 اسم غير معرّف**.

---

### C7..C9 — [مُصلَح] أخطاء أخرى مؤكدة
| # | العيب | الأثر | الإصلاح |
|---|---|---|---|
| C7 | `templates/owner/payment_vault.html` يرث `base_modern.html` غير الموجود (الأشقiae تستخدم `owner/base_modern.html`) | 500 | تصحيح المسار |
| C8 | `routes/accountant/financial.py` يستخدم `RefundRequest.created_at` — النموذج يملك `requested_at` | 500 على `/accountant/refunds` | تصحيح الحقل |
| C9 | `execute_pos_charge` يرجع **500** لأي فشل تجاري | تلويث لوحة الأخطاء |urd الآن 503 (غير مهيأ) / 502 (الجهاز) / 402 (مرفوض) + `code` ثابت |
| C10 | متغير بيئة الجهاز يشير إلى `azad_school` | تلويث قاعدة نظام آخر | توثيق + تصحيح `.env` |
| C11 | `cachelib` معلن في `requirements.txt` وغير مثبّت | الجلسات تنهار بصمت إلى cookies موقّعة | تثبيت |
| C12 | 21 خطأ stylelint في 6 ملفات CSS | — | إصلاح (آمن: إعادة ترتيب + longhand→shorthand) |
| C13 | `route_inventory.json` يدّعي 760 مساراً مقابل 752 فعلياً | انحراف توثيق | إعادة توليد |
| C14 | `docs/PLATFORM_STATUS.md` أرقام قديمة (60 هجرة، 188 جدول، 55 blueprint، 181 RLS) | تضليل | تحديث بالأرقام المتحقَّق منها |

---

## 3. العيب الحرج المتبقّي — لم أُصلحه عمداً

### [حرج] التشفير غير الحتمي على أعمدة قابلة للبحث وفريدة
`services/field_encryption_service.py` يستخدم `nonce = os.urandom(12)` — أي **نفس النص يُنتج نصاً مشفّراً مختلفاً في كل مرة** (وهو صحيح أمنياً لـ AES-GCM).

لكن `models/patient.py` يعرّف `national_id` و`first_name` و`phone` و`address` كـ `EncryptedString`، ومعها:
- `national_id = db.Column(EncryptedString(32), unique=True, index=True)`
- بحث بـ `ilike('%...%')` على الاسم ورقم الهوية
- 4 فهارس على أعمدة مشفّرة

**الأثبت تجريبياً على قاعدة حيّة:**

```
encrypt('123456789') #1 = $gcm$QtoGReqfD1ERYdhaT7bqYIR72yOLm4…
encrypt('123456789') #2 = $gcm$WvWlRusc579g1mbpBGvDyXk_h6lglsw…
deterministic? False

filter_by(national_id=<plaintext>)          -> 0 rows
filter(Patient.first_name.ilike('%Sara%'))  -> 0 rows
filter(Patient.national_id.ilike('%123%'))  -> 0 rows
إدراج مريضين بنفس رقم الهوية 'DUP-999'      -> نجح (!)  => unique=True لا يحمي شيئاً
```

**الأثر الطّبي:**
1. **منع تكرار المرضى معطّل** — يمكن إنشاء سجلات بمPatient الهوية نفسها (خطأ في هوية المريض وربط السجلات).
2. **البحث عن المرضى معطّل** — لا يعيد نتائج بالاسم أو رقم الهوية أو الهاتف.
3. **قيود `UNIQUE` على PHI غير قابلة للإنفاذ** — الفريدة على نص مشفّر عشوائي.
4. **الفهارس على أعمدة مشفّرة ميتة** — فهرسة بايتات عشوائية: تكلفة كتابة بلا انتقائية.
5. **الترتيب والتجميع على أعمدة مشفّرة بلا معنى** — مثل `group_by(MedicalRecord.diagnosis)` و`order_by(Patient.first_name)`.

**السبب الجذري:** `EncryptedString.hash_for_lookup()` (HMAC-SHA256 — النمط الصحيح: *blind index*) **موجود في الكود لكن صفر استدعاءات له**.

**لماذا لم أُصلحه الآن:** الإصلاح الصحيح يتطلب هجرة مخطط حقيقية (أعمدة hash + backfill لملايين الصفوف + فهرس فريد + تحويل كل استعلامات البحث + قرار الخصوصية حول تسريب التطابق). تطبيق جزئي متسرّع على **هوية المريض** أخطر من تركه موثّقاً. **هذه توصية بقرار هندسي، لا إصلاحاً عابراً.**

**خطة المعالجة المقترحة:** عمود `national_id_hash` (HMAC، فريد لكل مستأجر) ← `WHERE national_id_hash = hash_for_lookup(:nid) AND tenant_id = :t` ← نفس الشيء للهاتف (باستثناء patients descendants للسماح بمشاركته العائلي) ← إعادة فهرسة الأعمدة القابلة للبحث فقط ← إزالة `unique` الوهمي من الأعمدة المشفّرة.

---

## 4. عيوب تصميمية تستحق قراراً (لم أغيّرها)

| # | الملاحظة | الأثر |
|---|---|---|
| D1 | `Department.get_type()` يستنتج نوع القسم من **نص الاسم** (`'lab' in name`، `'مختبر' in name_ar`). أي قسم اسمه "عيادة" ⇒ `general`، و`create_visit` يشترط طبيباً لأقسام `general` | هش؛ behaviour يتغيّر بتسمية القسم |
| D2 | الـ bootstrap لا يزرع الأقسام | على تثبيت جديد، قائمة الأقسام في نموذج فتح الزيارة **فارغة** ⇒ **لا يمكن فتح زيارة** (اكتشفتُه؛ زرعتُها في التحقق) |
| D3 | `/lab/dashboard` يتطلب صلاحية `lab_order` | على تثبيت جديد تُحوِّل لوحة المختبر الطلب (302) رغم وجود القسم |
| D4 | 5,074 تحويلاً (302) من 5,720 | كل رابط داخلي يمرّ بتحويل تطبيع بادئة `/t/<slug>/` — عبء على UX والأداء |
| D5 | انحراف nullability: 180 جدول `NOT NULL` في DB و`nullable` في ORM | موثّق ومقصود (fail-closed) لكن-tech-debt |
| D6 | `tests/test_backend_coverage_boost.py` **غير متتبَّع** ويكسر بوابة `ruff` المعلنة (14 خطأ) | الملف لن يُشحن لكنه يُفشل CI |
| D7 | طقم 3,001 اختبار يحتاج > ساعة تسلسلياً | صيانة CI بطيئة |
| D8 | 379 استيراد غير مستخدم (flake8) · 996 كلمة cspell | ديون معروفة (flake8 غير حاجب؛ cspell بـ `\|\| true`) |

---

## 5. ما أثبتَّه المكونات positives (بدون مبالغة)

| المكوّن | الدليل المباشر |
|---|---|
| **عزل RLS** | بدور `NOBYPASSRLS`: `GUC=''` ⇒ 0 مستخدمين · `GUC=3` ⇒ 11 · `GUC=1` ⇒ مستخدم واحد فقط من منصةٍ أخرى — عزل مُثبَت لا مُدَّعى |
| **حارس RLS الفاشل** | رفض الإقلاع فعلياً على دور `BYPASSRLS` (أوقفني أثناء العمل، لأحسن) |
| **التشفير** | `first_name` مخزَّن `$gcm$…`، و`FIELD_ENCRYPTION_KEY` مفروض في الإنتاج |
| **تدقيق PHI** | `phi_audit_logs` سجّل CREATE/UPDATE مع الفاعل والوقت (8 صفوف) |
| **تدقيق عام** | `audit_trails` 29 صفاً · `login_attempts` 26 (تتبّع محاولات الدخول) |
| **RBAC** | طبيب 200 على `/doctor/dashboard` و403 على `/lab/dashboard`؛ استقبال بالعكس |
| **الحراسة الطبية** | `platform_owner`/`super_admin` محجوبون عن نقاط النهاية السريرية |
| **معالجة الأخطاء** | 404/400/403 كلها صحيحة دلالياً؛ **صفر 500** |
| **الواجهة** | vitest: 65 ملف · **275 اختبار ناجح** |
| **الترجمة (i18n)** | صفحات عربية RTL عاملة (`لوحة القيادة التمريضية`، 41KB مُصيَّرة) |
| **الطباعة/الأجهزة** | escpos/PDF/ZPL، باركود، DICOM، HL7 MLLP، FHIR R4 مسجّلة |

---

## 6. حالة البوابات

| البوابة | الحالة |
|---|---|
| `ruff check` (ملفاتي) | ✅ All checks passed |
| `ruff format --check` (ملفاتي) | ✅ |
| `ruff check --select F821,F823` (CI) | ✅ لا أسماء غير معرّفة |
| `flake8 --select E9,F63,F7` (CI) | ✅ exit 0 |
| `npx vitest run` | ✅ 275/275 |
| `npx stylelint` | ✅ exit 0 (بعد إصلاح 21 خطأ) |
| `scripts/ci/check_no_cjk.py` | ✅ 1456 ملف |
| `pytest` (3,001 اختبار) | ⚠️ تشغيل جزئي 7% (المجموعة كاملة تستحق > ساعة). في الملف المفحوص: **155 ناجح / 6 فاشل** ← بعد إصلاحي **3 فاشل**، وجميعها نفس سبب التشفير (القسم 3) |
| `cspell` | ⚠️ 996 (غير حاجب في CI) |

---

## 7. قائمة الملفات المعدَّلة

**مُصلَح (12 ملف):**
`app_factory.py` · `app/core/tenant/middleware.py` · `app/shared/tenant_filter.py` · `app/shared/pos_charge.py` · `models/permissions.py` · `seeds/production_baseline.py` · `services/pos_terminal_service.py` · `routes/accountant/financial.py` · `routes/monitoring_routes.py` · `scripts/ci/audit_rls_coverage.py` · `migrations/migration_utils.py` · `templates/owner/payment_vault.html` · `docs/PLATFORM_STATUS.md` · `route_inventory.json` · 6 ملفات CSS · `tests/test_agent1_reception.py`

**جديد (2):**
`migrations/versions/s3_012_rls_nullif_reassert.py` · `migrations/versions/s3_013_missing_schema_objects.py`

**نصيحة:**
- اضبط `TENANT_DEFAULT_SLUG` على slug عيادتك في `.env` (ليس `platform`).
- امسح متغير البيئة على مستوى الجهاز: `[Environment]::SetEnvironmentVariable('DATABASE_URL', $null, 'User')`.
- **لا تستخدم `db.create_all()`**؛ استخدم `flask db upgrade` (وإلا تكررت مشكلة C5).

---

## 8. التوصيات بالترتيب

1. **[P0] خطة تشفير قابلة للبحث** (قسم 3) —Sections الخطر هوية المريض.
2. **[P0] صحّح `pre_pilot_verification.py`** ليعمل على `information_schema` لا ORM metadata — وإلا ستستمر البوابة بإعطاء ضمان كاذب.
3. **[P1] أضف فحص انحراف المخطط** إلى CI (`alembic check` + مقارنة ORM) — كان سيكتشف C5 فوراً.
4. **[P1] اجعل `Department.get_type()` عموداً حقيقياً** (`department_type`) بدل استنتاج الاسم.
5. **[P1] ازرع الأقسام** في `bootstrap_platform.py` (D2).
6. **[P2] راجع كتابيات RBLS الستة** لتفادي فجوة `tenant_id` (§C3 «الفجوة المعروفة»).
7. **[P2] احذف `tests/test_backend_coverage_boost.py`** أو أضفه للتجهيز.
8. **[P3] شغّل pytest على التوازي** لتقليل زمن CI.
