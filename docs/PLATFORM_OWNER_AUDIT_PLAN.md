# خطة التدقيق الشاملة — مالك المنصة الطبية

**المالك:** Platform Owner — Medical Centre Platform v3.1  
**التاريخ:** 3 سبتمبر 2026 — الرأس: `f224b8d0c4d2` (59 تهجير) + `s3_008`/`s3_009`  
**الهدف:** مراجعة 360° برمجية + أمنية + تشغيلية + تجارية قبل تسليم SaaS أو توسيع.

---

## 1. الأهداف والمعايير

| المعيار | الوصف | النجاح |
|---------|-------|--------|
| **عزل تام** | لا تسرب بين مستأجرين، باقات، أدوار، طبقات سريرية | 0 تسرب، 54 اختبار عزل يمر |
| **خصوصية طبية** | `platform_owner` لا يرى ملفات مرضى | `403 Medical Privacy Guard` على كل `GET /doctor/*` `/lab/*` |
| **مالية مركزية** | Hub-and-Spoke عبر الاستقبال + بوابة `pending_financial_settlement` | `lab→radio` محظور 400، `reception→lab` مسموح |
| **جودة** | `ruff`/`mypy`/`bandit`/`pip-audit`/`CJK` صفر أخطاء | CI 22 وظيفة خضراء |
| **أداء** | طابور < 30 ثانية، فواتير < 2 ثانية | `pg_stat_statements` + `locust` |

---

## 2. المحاور السبعة

### 2.1 البنية والبيانات
- **التهجيرات:** `flask db heads` → `s3_009` وحيد، `py_compile` 0، `verify_migrations.py` على PG فارغ
- **RLS:** `audit_rls_coverage.py` 181 جدول بسياسات + 10 عامة (`system_configs` etc.)، `audit_orphaned_tenant_rows.py` 0 صفوف `tenant_id=0`
- **الجداول:** 188 `__tablename__` عبر 86 ملف `models/`، `EXPLAIN` للطابور والفواتير

### 2.2 العزل متعدد المستأجرين
- **الآلية:** `tenant_filter.py` (3 hooks: `before_compile`, `do_orm_execute`, `before_flush` + `SET LOCAL app.tenant_id` + `session.get` guard)
- **الاختبار:** `test_tenant_route_isolation.py` + اختراق `Tenant A → B` عبر `curl -H X-Tenant: B` مع `tenant_id=A` → `TenantIsolationError`
- **الباقات:** `can_activate_module` يرفض خارج `ProductBundle` (`app/core/module/validators.py:57`)

### 2.3 الأدوار والصلاحيات (12 دور)
- **الهرمية الصارمة:** `super_admin→[admin,manager]` فقط (`utils/decorators.py:78`)، `manager→[reception,accountant]`، `doctor→nurse` (أو صارم بدونها)، `er_doctor→emergency`
- **اللوحات:** `dashboard_registry.py:327` كل دور له تخطيط وودجات مقيدة `modules` (صيدلي `pharmacy` فقط)
- **التنقل:** `mobile_nav.py` + `nav_resolver.py` يخفي خارج الباقة (`resolve_dashboard_widgets`/`resolve_nav_for_user`)
- **الخلفية:** 551 حارس `@role_required`/`@require_permission`/`@require_module` + `Medical Privacy Guard` (`app_factory.py:972`)

### 2.4 الخصوصية الطبية
- **المسموح لمنصة:** `/owner/*`, `/super-admin/*`, `/api/billing/*`, `/health`
- **المحظور:** كل `is_medical_endpoint` (`/doctor/`, `/lab/`, `/patient`, `/prescription` ...) → `403`
- **الاختبار:** `test_platform_owner_blocked_from_patient_endpoints` + `seed_master_account` (`azad`)

### 2.5 المالية المركزية
- **النموذج:** Hub-and-Spoke — `reception→clinical` و `clinical→reception` فقط (`services/queue_management_service.py:240`)
- **الحقل:** `visits.pending_financial_settlement` (`models/visit.py:45` + `s3_009`)
- **التدفق:** `doctor` يطلب تحليل → `lab_request` + `visit.pending_financial_settlement=True` + `department_id=reception` + `QueueManagement(reception)` → الاستقبال يصدر فاتورة ثم `transfer_visit` إلى `lab`

### 2.6 الجودة و CI (22 وظيفة)
- `static-analysis-python` (ruff F821, format, mypy strict, bandit, pip-audit, **CJK guard** `scripts/ci/check_no_cjk.py`)
- `migrate` + `security-audit` (5 نصوص RLS) + `verify-boot` + `routes` PG 15/16/17 + `core` 4 شاردات + `coverage-report`
- **CJK:** `[\u4e00-\u9fff]` يفحص كل سطر في `*.py/*.html` بما فيها التعليقات، إخراج UTF-8 نظيف

### 2.7 التشغيل والأعمال
- **Bootstrap:** `bootstrap_platform.py` → 23 باقة + `packages` + `platform` tenant
- **الفوترة:** Stripe `STRIPE_SECRET_KEY` + webhook
- **الأداء:** `pg_stat_statements`, `slow_query_reports`, `locustfile.py`
- **النسخ:** `pg_dump` يومي عبر `docker compose exec db`

---

## 3. التنفيذ المرحلي (10 أيام)

| اليوم | المهمة | الأداة | المخرج |
|-------|--------|--------|--------|
| 1 | تدقيق ثابت | `ruff`, `mypy`, `check_no_cjk.py --staged`, `audit_rls_coverage` | **مكتمل 2026-09-03:** `ruff` 0، `format` 693، `CJK` 1432 OK، `migrate` وحيد `f224b8d0c4d2→s3_009` |
| 2 | تدقيق واجهة | تسجيل دخول بكل دور 12 + لقطات لوحة | **مكتمل:** 54 اختبار `test_role` يمر (12 `dashboard_has_expected` + 12 `no_leakage` + `er_doctor` + `reception_no_billing` + `pharmacist_gated`) |
| 3 | تدقيق خلفية | `curl` اختراق `403` لكل API خارج الدور (9 اختبارات `TestApiEnforcement`) | **مكتمل:** 9 اختبارات `403` تمر (`reception→prescription`, `pharmacist→visit`, `platform_owner→medical`) |
| 4 | تدقيق بيانات | `Tenant A→B` تسرب + `can_activate_module` خارج الباقة | لا تسرب |
| 5 | تدقيق مالي | تتبع `reception→doctor→reception→lab` مع `pending` | فاتورة → طابور |
| 6 | تدقيق أمني | `verify_rls_guard_rejection` (superuser مرفوض) + `platform_owner` → `403` | إثبات RLS |
| 7 | أداء | `locust` 100 مستخدم متزامن, `EXPLAIN ANALYZE` | <2s فاتورة |
| 8 | حمل | `Load Test` workflow PG 15/16/17 | CI أخضر |
| 9 | توثيق | تحديث `PLATFORM_STATUS.md`/`DEPLOYMENT.md` + `COMMERCIAL_READINESS` | docs محدثة |
| 10 | عرض حي | مستأجر وهمي `standalone_pharmacy` + `hospital` + تقرير موقع | تسليم |

---

## 3.1 تقرير تنفيذ المرحلة A (مكتمل 2026-09-03)

**اليوم 1 — ثابت:** `ruff check . --statistics` → `0`، `ruff format --check` → `693 formatted`، `python scripts/ci/check_no_cjk.py` → `OK: No CJK in 1432`، `flask db heads` → `s3_009` وحيد، `py_compile` 0.

**اليوم 2 — واجهة:** `pytest tests/test_role_functional_isolation.py::TestDashboardCleanliness -k "TestDashboardCleanliness"` → `18/18`، لقطات `reception` (3 ودجات بلا `cash_summary`) و `pharmacist` مقيد `pharmacy`.

**اليوم 3 — خلفية:** `pytest tests/test_role_functional_isolation.py::TestApiEnforcement -v` → `9/9`، `git diff` `app_factory.py:972` + `medical_privacy.py:23` + `dashboard_registry:507` يحجب.

**الاختبارات المحدثة:** `tests/test_role_functional_isolation.py` 54 + `tests/test_platform_bootstrap.py` 5 → `59 passed` (`pytest -q`).

---

## 4. الأدوات والشفافية

- كل فحص له `pytest` مسمى + سكربت `scripts/ci/*` — لا تدقيق يدوي بدون دليل.
- `CI` 22 وظيفة خضراء شرط تسليم؛ أي فشل يوقف النشر.

---

## 5. المخاطر والتخفيف

| الخطر | التخفيف |
|-------|---------|
| تسرب tenant عبر `ID` مباشر | `tenant_filter` fail-closed + اختبار اختراق |
| `platform_owner` يرى مرضى | `Medical Privacy Guard` + اختبار `403` |
| تحويل مباشر `lab→radio` | `direct_peer_transfer_disabled` 400 |
| فاتورة غير مدفوعة تدخل طابور | `_check_queue_entry_conditions` يطلب `PAID` |
| حرف صيني من مساعد | `check_no_cjk.py` يفشل CI |

**التوقيع:** مالك المنصة — 3 سبتمبر 2026
