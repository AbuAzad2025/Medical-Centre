# حالة المنصة — مصدر الحقيقة التقنية

**آخر تحقق من الكود وقاعدة البيانات:** 25 أكتوبر 2026 — تم التحقق من كل رقم في هذا الملف على قاعدة بيانات PostgreSQL 16 حيّة (قاعدة مخصّصة، دور `med_app` بـ `NOSUPERUSER NOBYPASSRLS`، أي أن RLS مفروض فعليًا).
**الإصدار:** 3.3 — رأس التهجيرات `s3_015_patient_search_ngrams`
**هاش الالتزام:** `e69c81c0` (fix(routing): an ER doctor now lands on the emergency dashboard)

> هذا الملف يُحدَّث عند تغيير البنية أو CI. لا تعتمد على خطط أو تقارير قديمة محذوفة.

---

## التشغيل (مسار واحد)

```bash
cp .env.example .env
docker compose up -d --build
```

| الخطوة | الأمر / المكوّن |
|--------|------------------|
| 1 | `flask db upgrade` |
| 2 | `python -c "from app_factory import create_app; from app.core.tenant.models import seed_default_bundles; from app.bootstrap.rbac_seed import seed_rbac_and_catalogs; from seeds.production_baseline import platform_tenant_scope; from app.core.platform_bootstrap import ensure_module_definitions; app=create_app('production'); exec(open('scripts/ops/bootstrap_platform.py').read())"` |
| 3 | `gunicorn -c gunicorn.conf.py wsgi:app` |

**Bootstrap يُنشئ:** `module_definitions` (22) · `product_bundles` (23) · `packages`/`package_versions` للتسجيل الذاتي.

> **مهم — وضع single-install:** `ENABLE_SAAS_MODE=false` هو وضع "مركز طبي واحد" الموصوف في [USER_GUIDE.md](USER_GUIDE.md). يجب ضبط `TENANT_DEFAULT_SLUG` على slug العيادة التشغيلية (وليس `platform`)، وإلا فشل تسجيل الدخول. في هذا الوضع يُربط الـ tenant تلقائيًا بدون بادئة `/t/<slug>/`، وجدول `users` لا يُقرأ أبدًا خارج سياق tenant.

---

## البنية (متحقّق من قاعدة البيانات الحيّة)

| المكوّن | التفاصيل |
|---------|----------|
| Backend | Flask 3.1, SQLAlchemy 2.0, PostgreSQL **16** (متحقَّق أيضًا على 14/15/17 في CI) |
| Cache / Queue | Redis 7, Celery worker + beat |
| Multi-tenant | `ENABLE_SAAS_MODE`, ORM filter + RLS |
| رأس التهجيرات | `s3_015_patient_search_ngrams` |
| ملفات التهجيرات | 67 ملف في `migrations/versions/` |
| جداول ORM (`db.metadata`) | 224 |
| جداول في قاعدة البيانات | 227 (224 ORM + `alembic_version` + `shift_handovers` + `alembic_version` indices) |
| انحراف المخطط (ORM vs DB) | **0** جدول/عمود مفقود (`s3_013` أصلح كل الانحرافات) |
| قابلية البحث في PHI | **مُصلَح** (`s3_014` + `s3_015`): أسماء/عنوان بـ AES-SIV حتمي، هوية/هاتف بـ blind index HMAC، فهرس فريد `(tenant_id, national_id_hash)`، جدول `patient_search_ngrams` للبحث الجزئي (3 أحرف فأكثر) |
| **جداول RLS** | **202** مُفعَّلة و**مُجبَرة** (FORCE) · **210** سياسة إجمالاً |
| سياسات `tenant_isolation_*` | **206**، وكلها الـ 206 تحمل حارس `NULLIF` (`s3_012`) |
| جداول بلا سياسة / سياسة بلا ربط `app.tenant_id` | **0 / 0** |
| Blueprints مسجّلة | **61** في `app_factory.py` |
| قواعد المسارات | **845** قاعدة في `url_map` وقت التشغيل (GET 550 · POST 287 · PUT 4 · DELETE 4) |
| وحدات المنصة (`MODULE_REGISTRY`) | **22** |
| قوالب | **432** في `templates/` — كلها تُترجم بنجاح، 0 اسم غير معرّف |
| ملفات اختبارات | **212** ملف `test_*.py` — CI مع `ENABLE_SAAS_MODE=true` |
| اختبارات الواجهة (Vitest) | **67** ملف · **280** اختبار (`npx vitest run`) |
| قيود ومفاتيح | **629** مفتاح أجنبي · **1366** فهرس |

---

## SaaS (متحقّق من `product_bundles` و `packages`)

| الميزة | المسار / الملف |
|--------|----------------|
| تسجيل ذاتي | `GET/POST /saas/signup`, `POST /api/saas/register` |
| كتالوج الباقات | `product_bundles` → `packages` عبر `platform_bootstrap.ensure_default_packages()` |
| توفير tenant | `TenantProvisioningService` — Owner UI + API `/api/saas/register` |
| فوترة | Stripe — `STRIPE_SECRET_KEY`, webhook `/api/billing/stripe/webhook` |
| حالات tenant | `TRIAL`, `ACTIVE`, `PENDING`, `SUSPENDED`, `CANCELLED` |
| تفعيل الوحدة | `tenant_modules` + `tenant_module_settings` لكل باقة |

**23 باقة في الكتالوج الافتراضي** (22 قابلة للبيع + `custom` فارغة). التفاصيل:

```sql
SELECT slug, name_ar, monthly_price FROM product_bundles WHERE is_active ORDER BY monthly_price;
```

---

## CI (`.github/workflows/ci.yml` — 23 وظيفة)

| # | الوظيفة | الوصف |
|---|----------|---------|
| 1 | `static-analysis-python` | ruff (format + F821/F823)، mypy strict، pip-audit، bandit `-lll` |
| 2 | `templates-i18n` | تحليل Jinja2 syntax لجميع القوالب + كشف النصوص غير المترجمة |
| 3 | `frontend-spelling-css` | stylelint + cspell (تدريجية) |
| 4 | `workflow-integrity` | actionlint لصحة YAML |
| 5 | `migrate` | `verify_migrations.py` (upgrade على PG فارغ + رأس واحد) ثم bootstrap ثم تدقيق RLS ثم فحص orphaned rows |
| 6 | `security-audit` | 5 نصوص: guard الرفض لـ superuser، enforcement، تغطية RLS، orphaned rows، stale action items |
| 7 | `static-quality` | flake8 (E9/F63/F7/F82) + YAML + JSON |
| 8 | `verify-boot` | إقلاع `create_app('testing')` + فحص `/health` و `/__health` |
| 9 | `routes` | اختبارات HTTP عبر مصفوفة PostgreSQL **15/16/17** |
| 10 | `unit` | اختبارات الوحدة — PG 16 مع تغطية |
| 11 | `integration` | اختبارات التكامل — PG 16 مع تغطية |
| 12 | `clinical` | اختبارات سريرية — PG 16 مع تغطية |
| 13 | `core` | **4 شاردات** لملفات الجذر — PG 16 |
| 14 | `coverage-report` | دمج التقارير (pytest-cov + coverage combine) |
| 15 | `frontend-asset-quality` | مراجعة أصول الواجهة (مرحلة 2/3 Directive) |

**حالة CI الحالية:** ✅ **23/23 وظيفة خضراء** على `e69c81c0` (تحقق API GitHub الحقيقي).

---

## ما ليس جزءاً من التشغيل (مستبعد)

| العنصر | الحكم |
|--------|--------|
| `scripts/dev/` | تطوير فقط (مُستبعد من `.dockerignore`) |
| `scripts/audit_*.py`, `lint_debt.py` | تدقيق يدوي |
| `migrations/manual_scripts/` | يدوي — لا يُشغَّل مع upgrade |
| `flask module-seed` | يفعّل كل الوحدات لكل tenants — **خطر في إنتاج** (استخدم توفير الباقة) |

---

## التحقق السريع بعد النشر

```bash
curl -f http://localhost:8080/health
curl -f http://localhost:8080/__health
python scripts/ci/verify_migrations.py
```

```sql
SELECT COUNT(*) FROM product_bundles;           -- 23
SELECT COUNT(*) FROM packages;                  -- 22 (قابلة للبيع)
SELECT version_num FROM alembic_version;        -- s3_015_patient_search_ngrams
SELECT COUNT(*) FROM pg_policy WHERE polname LIKE 'tenant_isolation_%';  -- 206
```

---

## المستندات الحية (محدّثة في هذا الالتزام)

| ملف | الغرض |
|-----|--------|
| [README.md](../README.md) | نظرة عامة شاملة |
| [DEPLOYMENT.md](DEPLOYMENT.md) | دليل النشر والإعداد للإنتاج |
| [USER_GUIDE.md](USER_GUIDE.md) | دليل مستخدمي المركز (أدوار، واجهات، سيناريوهات) |
| [CEO_OVERVIEW.md](CEO_OVERVIEW.md) | ملخص إداري تنفيذي بأرقام حقيقية |
| [ARCHITECTURE.md](ARCHITECTURE.md) | المعمارية، الأنماط، تدفقات البيانات |
| [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) | إعداد التطوير، الاختبارات، مساهمة |
| [API_REFERENCE.md](API_REFERENCE.md) | مرجع API (OpenAPI 3.0) |
| [OPERATIONS.md](OPERATIONS.md) | عمليات التشغيل والصيانة اليومية |
| [DYNAMIC_FORM_GOVERNANCE.md](DYNAMIC_FORM_GOVERNANCE.md) | عقد نماذج التخصص الديناميكية |
| [AUDIT_PAYMENTS_BILLING.md](AUDIT_PAYMENTS_BILLING.md) | تدقيق المدفوعات والفوترة |
| [AUDIT_PHARMACY_POS_FIXES.md](AUDIT_PHARMACY_POS_FIXES.md) | إصلاحات الصيدلية/البيع |
| [INCIDENT_LOG_ORPHANED_TENANT_ROWS.md](INCIDENT_LOG_ORPHANED_TENANT_ROWS.md) | سجل حادثة orphaned rows |

---

## سجل التغييرات في هذا الملف (منذ آخر تحقق)

| التاريخ | التغيير | الالتزام |
|---------|---------|---------|
| 2026-10-25 | تحديث أرقام RLS (202 جدول، 210 سياسة)، تصحيح عدد الجداول (227)، تحديث عدد المسارات (845)، إضافة التحقق من CI (23/23 خضراء على e69c81c0) | `e69c81c0` |
| 2026-10-23 | إضافة إصلاح `er_doctor` → `emergency` في `ROLE_TO_MODULE_MAP` | `e69c81c0` |
| 2026-10-23 | تصحيح عدد الوحدات (22)، الحزم (23)، سياسات RLS (210) | `c486189b` |