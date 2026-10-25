# نظرة عامة تنفيذية — Executive Overview

**آخر تحقق من الكود وقاعدة البيانات:** 25 أكتوبر 2026 — الإصدار **3.3** (commit `e69c81c0`)

---

## ما هي المنصة؟

منصة سحابية (SaaS) متعددة المستأجرين لإدارة المراكز الطبية: الاستقبال، الأطباء، المختبر، الأشعة، الصيدلية، الطوارئ، التمريض، الفوترة، المخزون، المواعيد، التقارير، بوابة المريض، لوحة المالك، التصوير بالذكاء الاصطناعي، والتكامل (FHIR/SSO/DICOM).

**نموذج العمل:** تشترك المراكز في باقات شهرية (22 باقة قابلة للبيع + باقة مخصصة `custom`). بيانات كل مركز معزولة تماماً (Row Level Security على مستوى قاعدة البيانات PostgreSQL 16).

---

## الأرقام السريعة (متحققة من الكود وقاعدة البيانات الحيّة)

| المؤشر | القيمة | المصدر |
|--------|--------|--------|
| **الوحدات الوظيفية** | **22** وحدة في `MODULE_REGISTRY` | `app/core/module/registry.py` |
| **الأدوار القابلة للتعيين** | **17** دور (`ASSIGNABLE_ROLES`) | `app/shared/user_role_policy.py` |
| **الباقات في الكتالوج** | **23** (22 قابلة للبيع + `custom`) | جدول `product_bundles` |
| **نماذج ORM** | **224** نموذج | `db.metadata` |
| **جداول في قاعدة البيانات** | **227** جدول عام | PostgreSQL `pg_class` |
| **جداول tenant-scoped تحت RLS** | **202** جدول (مفعّل + FORCE) | `audit_rls_coverage.py` |
| **سياسات RLS إجمالاً** | **210** سياسة | `pg_policy` |
| **سياسات `tenant_isolation_*`** | **206** سياسة (كلها بحارس `NULLIF`) | تهجيرات `s3_012` |
| **ملفات الاختبارات** | **212** ملف `test_*.py` | `tests/` |
| **التهجيرات (migrations)** | **67** ملف في `migrations/versions/` | Alembic |
| **Blueprints مسجلة** | **61** | `app_factory.py` |
| **قواعد المسارات (routes)** | **845** قاعدة | `url_map` وقت التشغيل |
| **الأمان** | تشفير PHI (AES-SIV + HMAC blind index)، سجل تتبع (audit logs)، MFA/WebAuthn/SSO | `s3_014`、`s3_015` |

---

## كتالوج الباقات (23 باقة — متحققة من `product_bundles`)

استعلام مباشر:

```sql
SELECT slug, name_ar, monthly_price FROM product_bundles WHERE is_active ORDER BY monthly_price;
```

| النطاق السعري (دولار/شهر) | الباقات (أمثلة) |
|---------------------------|------------------|
| **< 500** (منخفض) | `billing_only` (199) — فوترة ومواعيد فقط<br>`private_doctor_clinic` (299) — طبيب منفرد<br>`standalone_pharmacy` (499) — صيدلية مستقلة<br>`doctor_clinic_reception` (499) — طبيب باستقبال |
| **500–1,500** (متوسط) | `standalone_lab` (599) — مختبر مستقل<br>`standalone_radiology` (799) — أشعة مستقلة<br>`small_clinic` (799) — عيادة صغيرة<br>`lab_with_reception` (899) — مختبر مع استقبال<br>`clinic_with_lab` (1,199) — عيادة مع مختبر<br>`clinic_with_radiology` (1,299) — عيادة مع أشعة |
| **> 1,500** (عالي) | `doctor_clinic_full` (1,499) — عيادة طبيب متكاملة<br>`nursing_home` (1,599) — دار رعاية تمريضية<br>`clinic_with_lab_radiology` (1,799) — عيادة مع مختبر وأشعة<br>`community_clinic` (1,999) — مركز صحي مجتمعي<br>`multi_department_center` (2,499) — مركز طبي متعدد الأقسام<br>`polyclinic` (3,499) — مجمع عيادات مع بوابة مرضى<br>`hospital` (5,999) — مستشفى كامل |
| **خاص** | `custom` (سعر 0) — تُعد يدوياً عبر لوحة المالك |

> الأسعار أعلاه هي القيم الافتراضية في كود البذرة `app/core/tenant/models.py` — قابلة للتعديل عبر لوحة المالك (`/owner/bundles`).

---

## الوضع الحالي (الإنتاج)

| المجال | الحالة | الدليل |
|--------|-------|--------|
| **الجاهزية التجارية** | ✅ مكتملة | `docs/reports/COMMERCIAL_READINESS_AUDIT.md` — 86 فحصاً تجاوزها النظام |
| **ما قبل التشغيل التجريبي** | ✅ مكتمل | `docs/reports/PRE_PILOT_VERIFICATION_REPORT.md` — v3.3 |
| **CI/CD** | ✅ **23/23 وظيفة خضراء** | GitHub Actions على `e69c81c0` (تحقق API حقيقي) |
| **RLS / العزل** | ✅ 202/202 جدول محمي | `scripts/ci/audit_rls_coverage.py` + 210 سياسة |
| **الوحدات والحدود** | ✅ 22 وحدة، 23 باقة | `test_module_table_ownership.py` (10/10) + bundle isolation (155/155) |
| **الأدوار والصلاحيات** | ✅ 17 دور، هرمية كاملة | `test_role_functional_isolation.py` (54/54) |
| **الأمان** | ✅ Bandit 0 high، mypy clean، pip-audit clean | CI `static-analysis-python` |
| **نوعيات الكود** | ✅ ruff format/check، mypy strict | CI gates |

---

## خطوات قبل Go-Live (قائمة تحقق)

| # | الخطوة | الحالة | المسؤول |
|---|--------|-------|---------|
| 1 | تفعيل Stripe (`STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET`) | ⬜ | DevOps |
| 2 | إعداد البريد (SMTP) + SMS (Twilio) + WhatsApp Business | ⬜ | DevOps |
| 3 | قرار `TENANT_RESOLUTION_MODE` (domain / subdomain / path) | ⬜ | Product |
| 4 | مراجعة `docs/DEPLOYMENT.md` — إغلاق منافذ DB/Redis على `127.0.0.1` | ⬜ | SecOps |
| 5 | التحقق من RLS: `python scripts/ci/audit_rls_coverage.py` | ✅ | QA |
| 6 | تشغيل `verify_migrations.py` على بيئة staging | ⬜ | QA |
| 7 | اختبار تسجيل مستأجر جديد عبر `/api/saas/register` | ⬜ | QA |
| 8 | التحقق من `er_doctor` → `/emergency/dashboard` في حزمة `standalone_emergency` | ✅ | QA |

---

## المراجع التقنية (محدّثة في هذا الإصدار)

| الوثيقة | الرابط |
|---------|--------|
| الحالة التقنية التفصيلية | [PLATFORM_STATUS.md](PLATFORM_STATUS.md) |
| دليل النشر والإعداد | [DEPLOYMENT.md](DEPLOYMENT.md) |
| دليل المستخدمين | [USER_GUIDE.md](USER_GUIDE.md) |
| المعمارية والأنماط | [ARCHITECTURE.md](ARCHITECTURE.md) |
| دليل المطور | [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) |
| مرجع API | [API_REFERENCE.md](API_REFERENCE.md) |
| عمليات التشغيل | [OPERATIONS.md](OPERATIONS.md) |
| عقد النماذج الديناميكية | [DYNAMIC_FORM_GOVERNANCE.md](DYNAMIC_FORM_GOVERNANCE.md) |
| تدقيق المدفوعات والفوترة | [AUDIT_PAYMENTS_BILLING.md](AUDIT_PAYMENTS_BILLING.md) |
| إصلاحات الصيدلية/البيع | [AUDIT_PHARMACY_POS_FIXES.md](AUDIT_PHARMACY_POS_FIXES.md) |
| سجل حادثة orphaned rows | [INCIDENT_LOG_ORPHANED_TENANT_ROWS.md](INCIDENT_LOG_ORPHANED_TENANT_ROWS.md) |

---

## التواصل

- **المستودع:** `https://github.com/AbuAzad2025/Medical-Centre`
- **CI:** GitHub Actions — 23 وظيفة، PostgreSQL 16، Matrix 15/16/17
- **التوثيق:** جميع المستندات أعلاه مُحدّثة ومتزامنة مع الكود (commit `e69c81c0`)