# تقرير تدقيق المرحلة الأولى — Medical Centre Platform

> أُجري تدقيق مباشر للشيفرة عبر `routes/` و`models/` و`services/` و`migrations/` و`seeds/`
> و`e2e/`، بواسطة أربعة تحقيقات متوازية مع أدلة `file:line` على كل ادّعاء.
> **لم يُؤخذ أي وعد من التوثيق دون التحقق من الكود المقابل له.**

---

## 1) حجم النظام ومعماره

| المقياس | القيمة | الدليل |
|---|---|---|
| قواعد المسارات المعلنة | 761 | `route_inventory.json` |
| **المسارات الإنتاجية الحقيقية** | **752** | `docs/PLATFORM_STATUS.md:48` |
| مسارات متسربة من الاختبارات | 9 | `tests/conftest.py:489-512` |
| Blueprints مسجّلة | 61 | `app_factory.py:1139-1209` |
| ملفات النماذج | 90 (~204 صنفاً) | `models/` |
| الخدمات | 74 | `services/` |
| تهجيرات | 69 | `migrations/versions/` |
| رأس سلسلة التهجيرات | `s3_017_rbac_catalogue_readable` | رسم بياني تم التحقق منه |
| أكبر ملف-producing | `prod_baseline_20260622.py` (443 KB) | `migrations/versions/` |

### 1.1 انحراف جوهري في `route_inventory.json`

الجرد يقول 761، والتوثيق يقول 752. **الفارق دقيق وسببه قابل للتفسير**:

```
761 − 9 = 752      (المسارات)
530 GET − 9 = 521  (المتّسق مع التوثيق "GET 521")
```

التسعة هي بالضبط المسارات التي يعرّفها `tests/conftest.py` (`/test/g-trace`، `/test/idempotency-error` …).
وهي **المسارات الوحيدة التي فيها GET بلا HEAD** — البصمة القاطعة على أنها من نسخة pytest لا من `create_app()` إنتاجية.

**الأثر:** الجرد يبالغ في سطح المسارات بـ9. و`tests/test_route_inventory.py:31-37` يتحقق من اتجاه واحد فقط
(كل مسار مسجَّل يجب أن يظهر في الجرد)، فلا يفشل CI عند هذا الانحراف. موثّق كعيب `C13`.

### 1.2 prefixes المسارات المؤكَّدة من `app_factory.py`

`main` · `/api/search` · `/api/dashboard` · `/api/user` · `/api/lab` · `/api/radiology` · `/pwa` · `/kiosk` ·
`/owner` · `/auth` · `/super-admin` · `/reception` · `/doctor` · `/emergency` · `/lab` · `/radiology` · `/finance` ·
`/accountant` · `/backup` · `/manager` · `/booking` · `/medication` · `/procurement` · `/payment` · `/nurse` ·
`/clinical-coding` · `/bed` · `/or` · `/emar` · `/vaccination` · `/referral` · `/pathway` · `/cds` · `/barcode` ·
`/api/fhir` · `/dicom` · `/portal` · `/population-health` · `/report-builder` · `/security` · `/mfa` ·
`/nursing-assessment` · `/patient-education` · `/backup-restore` · `/telemedicine` · `/sso` · `/ai-imaging` ·
`/biometric` · `/data-warehouse` · `/what-if` · `/quality` · `/handover` · `/hl7` · `/ihe`

**وضع SaaS:** كل مخرجات `url_for()` تُسبَق بـ`/t/<tenant_slug>/` (`app_factory.py:1071-1087`).

---

## 2) آليات التحكم المشتركة — تنطبق على كل المسارات

### 2.1 بوابة وحدات المستأجر
`services/feature_gate_service.py:159` ← 403 إذا الوحدة غير مفعّلة. **معطّلة كلياً** عند
`ENABLE_SAAS_MODE = False` (`feature_gate_service.py:164`). طبقة ثانية في `app_factory.py:1089-1137` تغطي
اليتامي (e.g. `bed_bp`→`nursing`، `api_lab_bp`→`lab`).

### 2.2 مفردات الحُرّاس — `utils/decorators.py`
| الحارس | السطر | الدلالة |
|---|---|---|
| `role_required(*roles, use_hierarchy=True)` | 104 | تسلسل هرمي عند `decorators.py:78-84` |
| `reception_only` | 140 | سلسلة الاستقبال فقط |
| `can_approve_force_payment` | 256 | سلسلة المدير — **مستخدم في مسارين فقط** |
| `can_create_visits` | 278 | مُستخدم في `/reception/visits/create` |
| `can_handle_payments` | 231 | **معرَّف وغير مستخدم** |
| `require_payment_before_service` | 436 | **معرَّف وغير مستخدم** |
| `can_archive_visits` | 363 | **معرَّف وغير مستخدم** |
| `prevent_self_approval` | 468 | مُستخدم في `manager/approvals.py:91` |

**خطأ في `handle_route_errors`:** `logging.exception('... {f.__name__}')` عند السطر 543 **يمرّر بلا وسائط**،
فاسم العرض لا يُدرج أبداً في السجل.

### 2.3 آلة حالات الزيارة محمية
`Visit.status` الإسناد المباشر يرفع `ValueError` ما لم يكن مُفوَّضاً بخيط
(`models/visit.py:304-313`). الانتقالات في `services/visit_state_machine_service.py:35-44`:
`OPEN→{CHECKED_IN,CANCELLED}` · `CHECKED_IN→{IN_PROGRESS,CANCELLED}` · `IN_PROGRESS→{COMPLETED,CANCELLED,CHECKED_IN}`
· `COMPLETED→{OPEN}` · `CANCELLED→{}`.

---

## 3) مقارنة التوثيق بالشيفرة — ما كُذب

### 3.1 تقرير «مرحلة البوابة» أعطى ضماناً كاذباً
`PRE_PILOT_VERIFICATION_REPORT.md:238` يدّعي **«86/86 تأكيداً ناجحاً»**.
`docs/DEEP_AUDIT_REPORT_2026-09-27.md:129` ينقضه:
> «`pre_pilot_verification.py` يفحص `Model.__table__.columns` (بيانات ORM الوصفية) **لا** المخطط المهاجَر…
> **هذه بوابة تحقق تُعطي ضماناً كاذباً**»

و§C5 يسرد 7 جداول و5 أعمدة معلنة في ORM و**غائبة عن كل قاعدة مهاجَرة** — منها
`insurance_claims.claim_date/patient_share_amount/insurance_share_amount/adjudication_notes` ⇒ `/api/claims` كان يرجع 500.
أُضيفت لاحقاً في `migrations/versions/s3_013_missing_schema_objects.py`.

### 3.2 تقرير الفجوة الصحية تاريخي و outdated
`HEALTHCARE_GAP_AUDIT_REPORT.md` موسوم بنفسه **تاريخياً** (سطور 4-9). جدول التحقق:

| ادّعاء تاريخي (`:line`) | الحالة الآن |
|---|---|
| `:241` «صفر واجهة في `templates/accountant/`» للاسترداد | ✅ مُغلق — `accountant.refunds` + approve/reject/execute |
| `:216` «لا واجهة لـ `PHIAuditLog`» | ✅ مُغلق — `routes/super_admin/security.py:33-141` يستعلم سجلاً حقيقياً |
| `:187` «لا قوالب مورّد/شراء» | ✅ مُغلق — `medication.suppliers/*` و`procurement.*` |
| `:77,193,228` سجل تدقيق PHI مفقود (حرج) | ✅ مُغلق |
| `:74,162,189` مسار الاسترداد مفقود كلياً | ✅ مُغلق |
| `:196` لا واجهة لإعدادات الطابور | ✅ مُغلق — `super_admin/queue_settings.html` |
| `:194,257` لا لوحة أحداث أمنية | ✅ مُغلق |
| `:196` `PatientAccount` يتيم | ✅ مُغلق |

### 3.3 `openapi.json` وثيقة بقايا
يغطي **5 مسارات من 752 (0.7%)**: `/auth/login` + 4 أشعة. لا توثيق للفوترة أو التأمين أو ADT أو المختبر
أو الصيدلة أو البوابة أو FHIR. **وعيب بنيوي**: في مسارين `responses` متداخل **داخل** `requestBody`
فلا يعلن أي عملية استجابات صالحة. لا يُعتمد عليه كجرد.

### 3.4 `seeds/` لا يحتوي ما تتطلبه سيناريو سريري
`utils/seed_manifest.py:26-35` قائمة استثناء صريحة:
> «Deliberately excluded, because seeding them would be fabrication or a safety hazard»
> - حسابات الموظفين: «حساب بكلمة مرور معروفة باب خلفي غير مصادَق»
> - المرضى والزيارات: «سجلات سريرية ملفّقة خطر سلامة»
> - شركات التأمين: «كيانات تجارية تختلف بين بلد وبلد»
> - **الأجنحة والغرف والأسرة**: «جرد فيزيائي لمبنى محدّد؛ اختلاقها يجعل تقارير الإشغال تكذب»
> - **رموز LOINC / CPT**: «يجب أن تأتي من مصدر مصطلحات مُدار. رمز معقول لكنه خاطئ يُفوتر ويُبلَّغ كحقيقة»

**النتيجة العملية:** السيناريو التفاعلي **لا يمكن** أن يعتمد على أسرّة أو غرف أو شركات تأمين
أو أدوية أو فهرس فحوص مُبذَر. المصدر الوحيد هو `seeds/local_dev_story.py` (تطوير فقط، كلمة مرور `dev12345`).

### 3.5 اختبارات E2E لم تنجح يوماً
`e2e/artifacts/.last-run.json`: `{"status": "failed", "failedTests": [7 ids]}`.
جذر الفشل في كل حالة: `net::ERR_CONNECTION_REFUSED at http://127.0.0.1:8080`.
و`e2e/specs/adt-claim-cycle.spec.js` فيه `test.skip()` في **6 من 8** اختبارات.
⇒ **E2E يوفّر تغطية فعلية صفرية** للفوترة والتأمين وADT والخروج.
كما أن `openapi`/E2E لا يغطي: المختبر، الأشعة، الصيدلة، الجراحة، الباقات، البوابة.

---

## 4) تعدد المستأجرين و RLS

### 4.1 نموذج واحد
`TenantMixin` (`app/shared/mixins.py:22-31`): `tenant_id` → `tenants.id` بـ`nullable=True` **عمداً**
ليستطيع صفوف المنصّة أن تعيش بلا مستأجر.

**204 صنفاً، 4 فقط بلا `tenant_id`:** `DrugInteraction`، `ICD10Code`، `CPTCode`، `DRGCode`.
`DrugInteraction` بلا `tenant_id` يعني أن **تفاعل دواء في كتالوج مستأجر قد يحجب دواءً في كتالوج مستأجر آخر**.

### 4.2 أربع طبقات عزل في ORM — `app/shared/tenant_filter.py` (729 سطراً)
1. ترشيح تلقائي لـSELECT عبر `Query.before_compile` (`:373`) و`do_orm_execute` لـSQLAlchemy 2.0 (`:444`)
2. إسناد تلقائي عند INSERT عبر `before_flush` (`:580`) — **fail-closed**: إدراج بلا سياق يرفع `TenantIsolationError` (`:604`)
3. حارس UPDATE/DELETE عبر المستأجر (`:703`) → `PermissionError`
4. حارس `session.get()` (`:126`) للبحث بالمفتاح الأساسي الذي يتجاوز خط الأنابيب

### 4.3 RLS على مستوى قاعدة البيانات
| النمط | العدد |
|---|---|
| `ENABLE ROW LEVEL SECURITY` | 20 (14 ملفاً) |
| `FORCE ROW LEVEL SECURITY` | 23 |
| `CREATE POLICY` | 30 (16 ملفاً) |

**فجوة اتساق مؤلمة:** بينما تعتمد `services/financial_service.py` و`routes/accountant/*`
و`routes/manager/*` و`routes/reception/payments.py` على فلتر `tenant_id` في الشيفرة،
تعتمد هذه على RLS وحده **بلا فلتر برمجي**:
`routes/finance.py:37-79` · `routes/payment_routes.py:47-97` · `services/gatekeeper_service.py:524` و`:659`
( **حصة الدفع القسري نفسها** ) · `models/cash_register.py:64` · `services/report_service.py:1230`.
مع `ENABLE_SAAS_MODE` مطفأً **لا RLS ولا فلتر** ⇒ تسريب بين المستأجرين.

### 4.4 تشفير PHI وتصادم الفهارس
`national_id` و`phone` مُشفَّران AES-GCM **غير حتمي** مع فهرس أعمى (`*_hash`) فهرس فريد جزئي.
الاسم `EncryptedSearchableString` = AES-SIV حتمي. البحث الجزئي عبر trigram في `PatientSearchNgram`.
**التبقى:** 57 موقع `ILIKE` في 17 ملفاً **لم تُحوَّل** (`docs/DEEP_AUDIT_REPORT_2026-09-15:213` صريح).

---

## 5) النتيجة: خريطة الحقيقة

| المجال | الحالة الموثّقة |
|---|---|
| الفوترة | **الأكبر والأنضج** —Models + routes + خدمات + تهجيرات (`p3_001`، `p35_001`، `s3_001` …) |
| المختبر | **مكتمل** — `LabService` فيه كل نقاط التوسعة المقترحة سابقاً + FHIR/HL7 |
| الأشعة | **مكتمل** — `RadiologyService` + DICOM/PACS + مراجعة ثانية |
| الصيدلة | **مكتمل** — `ClinicalSafetyService` بـ`HARD_STOP` + قفل صف + مرتجعات |
| الدفتر المحاسبي | **مزدوج-entry صحيح** — 13 حساباً، رفض القيد غير المتوازن، حماية الفترة المغلقة |
| ADT | **الأساس فقط** — `AdmissionService` كامل، لكن بلا تسعير ليلي ولا ملخص خروج |
| التأمين | **نسبة مئوية فقط** — دورة مطالبات كاملة لكن **غير موصولة** بالفاتورة |
| الباقات | **غير موجودة سريرياً** |
| الجراحة | **الأضعف** — نموذج غني + صفر كاتب |
| التوثيق | **غير موجود** |

---

*أُجري هذا التقرير قبل توليد السيناريوهات، وكل رقم في مصفوفة التغطية مشتق منه.*
