# حالة المنصة — مصدر الحقيقة التقنية

**آخر تحقق من الكود:** 2 سبتمبر 2026  
**الإصدار:** 3.1 — رأس تهجيرات `f224b8d0c4d2`

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
| 2 | `python scripts/ops/bootstrap_platform.py` |
| 3 | `gunicorn -c gunicorn.conf.py wsgi:app` |

**Bootstrap يُنشئ:** `module_definitions` · `product_bundles` (23) · `packages`/`package_versions` للتسجيل الذاتي.

---

## البنية

| المكوّن | التفاصيل |
|---------|----------|
| Backend | Flask 3.1, SQLAlchemy 2.0, PostgreSQL **16** |
| Cache / Queue | Redis 7, Celery worker |
| Multi-tenant | `ENABLE_SAAS_MODE`, ORM filter + RLS |
| رأس التهجيرات | `f224b8d0c4d2` (`s3_007_add_missing_system_configs` → `clean_old_rules`) |
| تهجيرات (revisions) | 59 (59 ملف في `migrations/versions/`) |
| جداول ORM | 188 (`__tablename__` عبر 86 ملف `models/`) |
| جداول RLS | 181 بسياسات + 10 دون سياسة (فهرس `s2_008`) |
| Blueprints | 55 مسجّلة في `app_factory.py` |
| وحدات المنصة | 15 في `MODULE_REGISTRY` |
| قوالب | 409 في `templates/` |
| اختبارات | 139 ملف `test_*.py` — CI مع `ENABLE_SAAS_MODE=true` |

---

## SaaS

| الميزة | المسار / الملف |
|--------|----------------|
| تسجيل ذاتي | `GET/POST /saas/signup`, `POST /api/saas/register` |
| كتالوج الباقات | `product_bundles` → `packages` عبر `platform_bootstrap` |
| توفير tenant | `TenantProvisioningService` — Owner + API |
| فوترة | Stripe — `STRIPE_SECRET_KEY`, webhook `/api/billing/stripe/webhook` |
| حالات tenant | `TRIAL`, `ACTIVE`, `PENDING`, `SUSPENDED`, `CANCELLED` |
| تفعيل الوحدة | `tenant_modules` + `tenant_module_settings` لكل باقة |

**23 باقة في الكتالوج الافتراضي** (22 قابلة للبيع + `custom` فارغة). التفاصيل: استعلام SQL في [CEO_OVERVIEW.md](CEO_OVERVIEW.md) أو:

```sql
SELECT slug, name_ar, monthly_price FROM product_bundles WHERE is_active ORDER BY monthly_price;
```

---

## CI (`.github/workflows/ci.yml`)

15 وظيفة، أغلبها تحتاج `migrate` وتشغَّل على PostgreSQL 16:

1. `static-analysis-python` — ruff (format + F821/F823), mypy strict, pip-audit, bandit `-lll`
2. `templates-i18n` — تحليل Jinja2 syntax لجميع القوالب + كشف النصوص غير المترجمة
3. `frontend-spelling-css` — stylelint + cspell (تدريجية)
4. `workflow-integrity` — actionlint لصحة YAML
5. `migrate` — `verify_migrations.py` (upgrade على PG فارغ + رأس واحد) ثم bootstrap ثم تدقيق RLS ثم فحص orphaned rows
6. `security-audit` — 5 نصوص: guard الرفض لـ superuser، enforcement، تغطية RLS، orphaned rows، stale action items
7. `static-quality` — flake8 (E9/F63/F7/F82) + YAML + JSON
8. `verify-boot` — إقلاع `create_app('testing')` + فحص `/health` و `/__health`
9. `routes` — اختبارات HTTP عبر مصفوفة PostgreSQL **15/16/17**
10. `unit` · `integration` · `clinical` — PG 16 مع تغطية
11. `core` — 4 شاردات لملفات الجذر
12. `coverage-report` — دمج التقارير (pytest-cov + coverage combine)

---

## ما ليس جزءاً من التشغيل

| العنصر | الحكم |
|--------|--------|
| `scripts/dev/` | تطوير فقط (مُستبعد من `.dockerignore`) |
| `scripts/audit_*.py`, `lint_debt.py` | تدقيق يدوي |
| `migrations/manual_scripts/` | يدوي — لا يُشغَّل مع upgrade |
| `flask module-seed` | يفعّل كل الوحدات لكل tenants — **خطر في إنتاج** |

---

## التحقق السريع بعد النشر

```bash
curl -f http://localhost:8080/health
curl -f http://localhost:8080/__health
python scripts/ci/verify_migrations.py
```

```sql
SELECT COUNT(*) FROM product_bundles;
SELECT COUNT(*) FROM packages;
SELECT version_num FROM alembic_version;
```

---

## المستندات الحية

| ملف | الغرض |
|-----|--------|
| [README.md](../README.md) | نظرة عامة |
| [DEPLOYMENT.md](DEPLOYMENT.md) | نشر ومتغيرات بيئة |
| [USER_GUIDE.md](USER_GUIDE.md) | مستخدمو المركز |
| [CEO_OVERVIEW.md](CEO_OVERVIEW.md) | ملخص إداري |
| [../scripts/ops/README.md](../scripts/ops/README.md) | أوامر التشغيل |
| [DYNAMIC_FORM_GOVERNANCE.md](DYNAMIC_FORM_GOVERNANCE.md) | عقد نماذج التخصص |
| [AUDIT_PAYMENTS_BILLING.md](AUDIT_PAYMENTS_BILLING.md) | تدقيق المدفوعات والفوترة |
| [AUDIT_PHARMACY_POS_FIXES.md](AUDIT_PHARMACY_POS_FIXES.md) | إصلاحات الصيدلية/البيع |
| [INCIDENT_LOG_ORPHANED_TENANT_ROWS.md](INCIDENT_LOG_ORPHANED_TENANT_ROWS.md) | سجل حادثة orphaned rows |
